"""
NexovAI Voice AI Doctor Appointment Assistant
Idiomatic Pipecat Voice Pipeline Definition

Pipeline flow:
Caller Audio -> Transport Input -> Silero VAD -> ElevenLabs STT -> Google Gemini LLM (with tools) -> ElevenLabs TTS -> Transport Output

Tools registered:
1. check_doctor_availability
2. book_appointment
3. cancel_appointment
"""

import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Try importing Pipecat packages with graceful fallback notice if dependencies are pending installation
try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.frames.llm import LLMContext
    from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
    from pipecat.services.llm_service import FunctionCallParams
    PIPECAT_AVAILABLE = True
except (ImportError, Exception) as e:
    PIPECAT_AVAILABLE = False

from backend.prompts import SYSTEM_PROMPT
from backend.tools import (
    execute_check_doctor_availability,
    execute_book_appointment,
    execute_cancel_appointment,
)

load_dotenv()


def build_pipecat_tools():
    """
    Constructs the Pipecat function schemas and bindings for the 3 required tools.
    """
    async def handle_check_availability(params: "FunctionCallParams"):
        args = getattr(params, "arguments", {}) or {}
        res = execute_check_doctor_availability(
            doctor_name=args.get("doctor_name"),
            specialty=args.get("specialty"),
            date=args.get("date")
        )
        await params.result_callback(res)

    async def handle_book_appointment(params: "FunctionCallParams"):
        args = getattr(params, "arguments", {}) or {}
        res = execute_book_appointment(
            patient_phone=args.get("patient_phone", ""),
            doctor_name=args.get("doctor_name", ""),
            date=args.get("date", ""),
            time_slot=args.get("time_slot", ""),
            patient_name=args.get("patient_name", "Caller")
        )
        await params.result_callback(res)

    async def handle_cancel_appointment(params: "FunctionCallParams"):
        args = getattr(params, "arguments", {}) or {}
        res = execute_cancel_appointment(
            patient_phone=args.get("patient_phone", ""),
            appointment_id=args.get("appointment_id")
        )
        await params.result_callback(res)

    tools = [
        FunctionSchema(
            name="check_doctor_availability",
            description="Check available doctor appointment slots. Offer available times to the caller.",
            properties={
                "doctor_name": {"type": "string", "description": "Doctor name e.g. Dr. Sarah Chen"},
                "specialty": {"type": "string", "description": "Cardiology, Dermatology, etc."},
                "date": {"type": "string", "description": "Date YYYY-MM-DD"}
            },
            handler=handle_check_availability
        ),
        FunctionSchema(
            name="book_appointment",
            description="Books an appointment. MUST only be called after you have read the caller's phone number back to them and received confirmation.",
            properties={
                "patient_phone": {"type": "string", "description": "Confirmed caller phone number"},
                "doctor_name": {"type": "string", "description": "Doctor's name"},
                "date": {"type": "string", "description": "YYYY-MM-DD date"},
                "time_slot": {"type": "string", "description": "Slot time, e.g. '09:30 AM'"}
            },
            required=["patient_phone", "doctor_name", "date", "time_slot"],
            handler=handle_book_appointment
        ),
        FunctionSchema(
            name="cancel_appointment",
            description="Cancels an existing appointment. MUST only be called after confirming caller's phone number.",
            properties={
                "patient_phone": {"type": "string", "description": "Confirmed caller phone number"}
            },
            required=["patient_phone"],
            handler=handle_cancel_appointment
        )
    ]
    return tools


async def create_pipecat_voice_pipeline(transport):
    """
    Assembles and starts the full Pipecat pipeline:
    caller audio -> STT (ElevenLabs) -> LLM (Google Gemini) -> TTS (ElevenLabs) -> caller audio
    with Silero VAD (Bonus).
    """
    if not PIPECAT_AVAILABLE:
        raise RuntimeError("Pipecat library is not installed. Please run `pip install -r requirements.txt`.")

    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

    # 1. Silero VAD (Bonus)
    vad = SileroVADAnalyzer()

    # 2. ElevenLabs Speech-to-Text
    stt = ElevenLabsRealtimeSTTService(
        api_key=elevenlabs_api_key
    )

    # 3. Google Gemini LLM with function calling
    tools = build_pipecat_tools()
    llm = GoogleLLMService(
        api_key=gemini_api_key,
        model="gemini-2.5-flash"
    )

    # 4. Context with system instructions and tools
    context = LLMContext(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        tools=tools
    )
    context_aggregator = llm.create_context_aggregator(context)

    # 5. ElevenLabs Text-to-Speech
    tts = ElevenLabsTTSService(
        api_key=elevenlabs_api_key,
        voice_id=voice_id
    )

    # 6. Assemble Pipecat pipeline
    pipeline = Pipeline([
        transport.input(),
        vad,
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant()
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000
        )
    )

    runner = PipelineRunner()
    return runner, task
