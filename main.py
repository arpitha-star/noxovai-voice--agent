"""
NexovAI Voice AI Doctor Appointment Assistant
Main Application Entrypoint (FastAPI + WebSockets)
"""

import os
import json
import asyncio
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database import (
    init_db,
    get_doctors_with_slots,
    get_all_appointments,
    book_appointment as db_book,
    cancel_appointment as db_cancel
)
from backend.tools import set_action_callback
from backend.pipeline import (
    PipecatVoiceEngine,
    ELEVENLABS_API_KEY,
    GEMINI_API_KEY,
    OPENAI_API_KEY
)

# Initialize FastAPI App
app = FastAPI(
    title="NexovAI Voice Doctor Appointment Assistant",
    description="Real-time Voice AI Virtual Receptionist using Pipecat, ElevenLabs, and Gemini",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSockets for dashboard broadcast
active_connections: List[WebSocket] = []


async def broadcast_event(message: Dict[str, Any]):
    """Broadcast real-time events to all active connected browser clients."""
    for ws in list(active_connections):
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            if ws in active_connections:
                active_connections.remove(ws)


# Connect backend tool callback to frontend WebSocket broadcaster
set_action_callback(broadcast_event)


@app.on_event("startup")
def startup_event():
    """Ensure database and seed data are ready on launch."""
    init_db()
    print("=" * 60)
    print(" NexovAI Voice AI Doctor Appointment Assistant is running!")
    print(f" LLM Status: {'Gemini Active' if GEMINI_API_KEY else 'OpenAI Active' if OPENAI_API_KEY else 'Rule Engine Active'}")
    print(f" Voice Status: {'ElevenLabs Active' if ELEVENLABS_API_KEY else 'Browser Voice Active'}")
    print(" Open dashboard: http://localhost:8000")
    print("=" * 60)


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@app.get("/api/health")
def get_health():
    return {
        "status": "healthy",
        "service": "NexovAI Voice Assistant",
        "llm_provider": "Google Gemini" if GEMINI_API_KEY else "OpenAI" if OPENAI_API_KEY else "Local Engine",
        "stt_provider": "ElevenLabs" if ELEVENLABS_API_KEY else "Web Speech API",
        "tts_provider": "ElevenLabs" if ELEVENLABS_API_KEY else "Web Speech Synthesis",
        "framework": "Pipecat",
        "vad": "Silero VAD"
    }


@app.get("/api/doctors")
def api_get_doctors():
    """Return doctors and their available slots."""
    return {"doctors": get_doctors_with_slots()}


@app.get("/api/appointments")
def api_get_appointments():
    """Return all appointments for the dashboard."""
    return {"appointments": get_all_appointments()}


class DirectBookRequest(BaseModel):
    patient_phone: str
    doctor_name: str
    date: str
    time_slot: str
    patient_name: str = "Caller"


@app.post("/api/appointments/book")
async def api_book_appointment(req: DirectBookRequest):
    res = db_book(
        patient_phone=req.patient_phone,
        doctor_name=req.doctor_name,
        date=req.date,
        time_slot=req.time_slot,
        patient_name=req.patient_name
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    await broadcast_event({"type": "appointment_booked", "data": res})
    return res


class DirectCancelRequest(BaseModel):
    patient_phone: str
    appointment_id: int = None


@app.post("/api/appointments/cancel")
async def api_cancel_appointment(req: DirectCancelRequest):
    res = db_cancel(patient_phone=req.patient_phone, appointment_id=req.appointment_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    await broadcast_event({"type": "appointment_cancelled", "data": res})
    return res


@app.post("/api/reset")
async def api_reset_database():
    """Reset database to initial state (handy for demos and video recording)."""
    init_db(force_reset=True)
    await broadcast_event({"type": "database_reset"})
    return {"success": True, "message": "Database successfully reset to seed state."}


# ==============================================================================
# WebSocket Call Session Endpoint
# ==============================================================================

@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    async def send_to_this_client(event: Dict[str, Any]):
        try:
            await websocket.send_text(json.dumps(event))
        except Exception:
            pass

    engine = PipecatVoiceEngine(send_event=send_to_this_client)

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            action = data.get("action")

            if action == "start_call":
                print(f"[WS] Action start_call received")
                await engine.start_call()

            elif action == "user_speech":
                user_text = data.get("text", "")
                print(f"[WS user_speech received]: '{user_text}'")
                await engine.handle_user_speech(user_text)

            elif action == "end_call":
                print(f"[WS] Action end_call received")
                await engine.end_call()
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket session error: {e}")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


# Mount Static Files and Root Route
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/download")
def download_project_zip():
    zip_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nexovai-voice-agent.zip")
    if not os.path.exists(zip_path):
        zip_path = os.path.join(os.path.dirname(__file__), "nexovai-voice-agent.zip")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="nexovai-voice-agent.zip"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
