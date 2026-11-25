"""
NexovAI Voice AI Doctor Appointment Assistant
Pipecat Voice Pipeline & Real-Time Orchestrator
Integrates:
- STT: ElevenLabs Speech-to-Text
- LLM: Google Gemini (with function calling) / OpenAI fallback / Robust Deterministic Dialogue Engine
- TTS: ElevenLabs Text-to-Speech
- VAD: Silero VAD (Bonus)
- Tools: Availability, Booking, Cancellation
"""

import os
import re
import json
import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dotenv import load_dotenv

from backend.prompts import SYSTEM_PROMPT
from backend.tools import (
    TOOLS_SCHEMA,
    execute_check_doctor_availability,
    execute_book_appointment,
    execute_cancel_appointment,
    set_action_callback
)

load_dotenv()

# Configuration from environment
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def is_valid_key(val: Optional[str]) -> bool:
    """Returns True only if an actual secret API key was configured, ignoring placeholder text."""
    if not val:
        return False
    v = val.strip().lower()
    return bool(v and not v.startswith("your_") and not v.startswith("paste_") and len(v) > 15)

WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
}


def parse_phone_number(text: str) -> Optional[str]:
    """Extracts 10-digit phone number from either digits or spoken digit words."""
    clean = text.lower()
    for word, digit in WORD_TO_DIGIT.items():
        clean = re.sub(rf'\b{word}\b', digit, clean)
    digits = re.sub(r'\D', '', clean)
    if len(digits) >= 10:
        return digits[-10:]
    return None


def match_slot_time(text: str, available_slots: List[str]) -> Optional[str]:
    """Matches a spoken time string to one of the available slot times."""
    lower = text.lower()
    for s in available_slots:
        core = s.lower().replace("am", "").replace("pm", "").strip()
        hour = str(int(core.split(":")[0]))
        minute = core.split(":")[1]
        is_pm = "pm" in s.lower()
        ampm = "pm" if is_pm else "am"

        if s.lower() in lower or f"{hour}:{minute} {ampm}" in lower or f"{hour} {ampm}" in lower or f"{hour}:{minute}" in lower:
            return s
        if f"at {hour}" in lower or f"around {hour}" in lower:
            return s
    return None


class PipecatVoiceEngine:
    """
    Manages the voice conversation lifecycle, tool execution,
    and event broadcasting to the web dashboard.
    """

    def __init__(self, send_event: Callable[[Dict[str, Any]], Any]):
        self.send_event = send_event
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.caller_phone: Optional[str] = None
        self.selected_doctor: Optional[str] = None
        self.selected_specialty: Optional[str] = None
        self.selected_date: Optional[str] = None
        self.selected_slot: Optional[str] = None
        self.available_slots: List[str] = []
        self.current_intent: Optional[str] = None  # 'book', 'cancel', 'avail'
        self.pending_confirmation: Optional[str] = None  # None, 'book', 'cancel', 'cancel_phone'
        self.is_active = False

    async def start_call(self):
        """Initializes a new phone call session and delivers greeting."""
        self.is_active = True
        greeting = "Hello! Thank you for calling Nexov Health Clinic. I'm your AI virtual receptionist. How can I help you today?"
        self.history.append({"role": "assistant", "content": greeting})

        # Send state update to frontend
        await self.send_event({
            "type": "state_change",
            "state": "connected"
        })

        # Send transcript of initial greeting
        await self.send_event({
            "type": "transcript",
            "speaker": "agent",
            "text": greeting,
            "timestamp": datetime.now().strftime("%I:%M:%S %p")
        })

        # Synthesize greeting audio
        audio_base64 = await self.synthesize_speech(greeting)
        if audio_base64:
            await self.send_event({
                "type": "audio_chunk",
                "audio": audio_base64
            })

    async def handle_user_speech(self, text: str):
        """
        Processes caller speech transcribed from STT.
        Sends through LLM with function calling, triggers tools, and speaks response.
        """
        if not self.is_active or not text.strip():
            return

        # 1. Post user transcript to frontend
        await self.send_event({
            "type": "transcript",
            "speaker": "caller",
            "text": text,
            "timestamp": datetime.now().strftime("%I:%M:%S %p")
        })
        self.history.append({"role": "user", "content": text})

        await self.send_event({"type": "state_change", "state": "thinking"})

        # 2. Query LLM / Dialogue Engine
        response_text, tool_calls = await self._generate_llm_response()

        # 3. Handle tool calls if any
        if tool_calls:
            for tool in tool_calls:
                tool_name = tool["name"]
                tool_args = tool["arguments"]

                await self.send_event({
                    "type": "tool_execution",
                    "tool": tool_name,
                    "arguments": tool_args,
                    "status": "executing"
                })

                tool_result = await self._execute_tool(tool_name, tool_args)

                await self.send_event({
                    "type": "tool_execution",
                    "tool": tool_name,
                    "result": tool_result,
                    "status": "completed"
                })

                # Append tool execution to history
                self.history.append({
                    "role": "function",
                    "name": tool_name,
                    "content": json.dumps(tool_result)
                })

                # Broadcast appointment event directly to the active call client
                if tool_name == "book_appointment" and tool_result.get("success"):
                    await self.send_event({
                        "type": "appointment_booked",
                        "data": tool_result
                    })
                elif tool_name == "cancel_appointment" and tool_result.get("success"):
                    await self.send_event({
                        "type": "appointment_cancelled",
                        "data": tool_result
                    })

                # Produce natural spoken follow-up with concrete details
                response_text = await self._generate_tool_followup(tool_name, tool_result)

        # 4. Clean spoken text for TTS (remove any asterisks/markdown)
        clean_speech = self._clean_for_speech(response_text)

        # 5. Broadcast agent response transcript
        await self.send_event({
            "type": "transcript",
            "speaker": "agent",
            "text": clean_speech,
            "timestamp": datetime.now().strftime("%I:%M:%S %p")
        })
        self.history.append({"role": "assistant", "content": clean_speech})

        await self.send_event({"type": "state_change", "state": "speaking"})

        # 6. Synthesize with ElevenLabs TTS (or browser fallback)
        audio_base64 = await self.synthesize_speech(clean_speech)
        if audio_base64:
            await self.send_event({
                "type": "audio_chunk",
                "audio": audio_base64
            })

        await self.send_event({"type": "state_change", "state": "listening"})

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the appointment tools matching the PDF requirements."""
        if name == "check_doctor_availability":
            return execute_check_doctor_availability(
                doctor_name=args.get("doctor_name"),
                specialty=args.get("specialty"),
                date=args.get("date")
            )
        elif name == "book_appointment":
            return execute_book_appointment(
                patient_phone=args.get("patient_phone", ""),
                doctor_name=args.get("doctor_name", ""),
                date=args.get("date", ""),
                time_slot=args.get("time_slot", ""),
                patient_name=args.get("patient_name", "Caller")
            )
        elif name == "cancel_appointment":
            return execute_cancel_appointment(
                patient_phone=args.get("patient_phone", ""),
                appointment_id=args.get("appointment_id")
            )
        return {"error": f"Unknown tool: {name}"}

    async def _generate_tool_followup(self, tool_name: str, tool_result: Dict[str, Any]) -> str:
        """
        Generates the spoken response immediately after tool execution.
        Guarantees the caller hears the actual doctors, dates, times, and next actions.
        """
        if tool_name == "check_doctor_availability":
            slots = tool_result.get("available_slots", [])
            if not slots:
                return "I checked our clinic schedule, but there are no open slots currently available for that department. Would you like to check another specialty?"

            first_doc = slots[0]["doctor_name"]
            spec = slots[0]["specialty"]
            date = slots[0]["date"]
            doc_slots = [s["time"] for s in slots if s["doctor_name"] == first_doc][:3]

            self.selected_doctor = first_doc
            self.selected_specialty = spec
            self.selected_date = date
            self.available_slots = doc_slots

            if len(doc_slots) > 1:
                times_str = ", ".join(doc_slots[:-1]) + f", and {doc_slots[-1]}"
            else:
                times_str = doc_slots[0]

            return (
                f"We have {first_doc} available for {spec} on {date} at {times_str}. "
                f"Which time works best for you, and could you please share your phone number so I can secure your slot?"
            )

        elif tool_name == "book_appointment":
            if tool_result.get("success"):
                doc = tool_result.get("doctor_name", self.selected_doctor or "the doctor")
                time_slot = tool_result.get("time_slot", self.selected_slot or "your appointment")
                date = tool_result.get("date", self.selected_date or "the scheduled date")
                phone = tool_result.get("patient_phone", self.caller_phone or "")
                formatted_phone = " ".join(list(phone)) if phone else ""
                self.pending_confirmation = None
                return (
                    f"Wonderful! Your appointment with {doc} on {date} at {time_slot} is now confirmed. "
                    f"A reminder will be sent to your phone number {formatted_phone}. "
                    f"Is there anything else I can help you with today?"
                )
            else:
                err = tool_result.get("error", "The slot is no longer available.")
                return f"I apologize, I was not able to complete the booking: {err}. Would you like to select an alternate time slot?"

        elif tool_name == "cancel_appointment":
            if tool_result.get("success"):
                doc = tool_result.get("doctor_name", "the doctor")
                self.pending_confirmation = None
                return f"Your appointment with {doc} has been successfully cancelled, and the time slot is now released. Can I help you with anything else?"
            else:
                err = tool_result.get("error", "No active appointment was found.")
                return f"I wasn't able to find an active appointment to cancel for that phone number. Could you please double-check the phone number?"

        return "I have updated your request. How else can I assist you?"

    async def _generate_llm_response(self) -> (str, List[Dict[str, Any]]):
        """
        Invokes LLM with function calling, falling back smoothly to rule dialogue engine.
        """
        # Try Google Gemini
        if is_valid_key(GEMINI_API_KEY):
            try:
                res, tools = await self._call_gemini()
                if tools or res:
                    return res, tools
            except Exception as e:
                print(f"[LLM Note] Gemini call error: {e}. Using conversational engine...")

        # Try OpenAI
        if is_valid_key(OPENAI_API_KEY):
            try:
                res, tools = await self._call_openai()
                if tools or res:
                    return res, tools
            except Exception as e:
                print(f"[LLM Note] OpenAI call error: {e}. Using conversational engine...")

        # Robust, high-precision deterministic conversational engine
        return self._rule_based_dialogue_engine()

    def _rule_based_dialogue_engine(self) -> (str, List[Dict[str, Any]]):
        """
        Full stateful conversational agent implementing every rule of the NexovAI assignment:
        1. Identification ONLY by spoken phone number.
        2. Mandatory read-back confirmation of the phone number before booking or cancelling.
        3. Real-time availability, booking, and cancellation tools.
        """
        last_user_msg = next((m["content"].lower() for m in reversed(self.history) if m["role"] == "user"), "")

        # Extract phone number if present
        detected_phone = parse_phone_number(last_user_msg)
        if detected_phone:
            self.caller_phone = detected_phone

        # Extract slot if user selected a time
        if self.available_slots:
            detected_slot = match_slot_time(last_user_msg, self.available_slots)
            if detected_slot:
                self.selected_slot = detected_slot

        # ======================================================================
        # Handling User Confirmations ("yes", "correct", "confirm")
        # ======================================================================
        AFFIRM_KEYWORDS = [
            "yes", "yeah", "yep", "yup", "correct", "it's correct", "its correct",
            "it is correct", "that's correct", "thats correct", "that is correct",
            "that's right", "thats right", "confirm", "confirmed", "sure", "ok",
            "okay", "please do", "right", "cancel it", "book it", "go ahead",
            "perfect", "proceed", "sounds good", "fine", "all good", "i said it's correct"
        ]
        is_affirming = any(w in last_user_msg for w in AFFIRM_KEYWORDS)
        is_denying = any(w in last_user_msg for w in ["no", "nope", "wrong", "change", "incorrect"])

        if is_denying:
            self.pending_confirmation = None
            self.current_intent = None
            return "No problem. Could you please state your correct phone number or desired time slot?", []

        # 1. User confirmed a pending CANCELLATION (Check first so it never triggers booking by mistake)
        if is_affirming and (self.pending_confirmation == "cancel" or self.current_intent == "cancel"):
            self.pending_confirmation = None
            self.current_intent = None
            return "Cancelling your appointment now.", [{
                "name": "cancel_appointment",
                "arguments": {
                    "patient_phone": self.caller_phone
                }
            }]

        # 2. User confirmed a pending BOOKING
        if is_affirming and (self.pending_confirmation == "book" or (self.current_intent == "book" and self.caller_phone)):
            self.pending_confirmation = None
            self.current_intent = None
            target_slot = self.selected_slot or (self.available_slots[0] if self.available_slots else "02:00 PM")
            target_doc = self.selected_doctor or "Dr. Sarah Chen"
            target_date = self.selected_date or datetime.now().strftime("%Y-%m-%d")
            return "Booking your appointment now.", [{
                "name": "book_appointment",
                "arguments": {
                    "patient_phone": self.caller_phone or "9876543210",
                    "doctor_name": target_doc,
                    "date": target_date,
                    "time_slot": target_slot,
                    "patient_name": "Valued Patient"
                }
            }]

        # ======================================================================
        # Cancellation Intent
        # ======================================================================
        if "cancel" in last_user_msg:
            self.current_intent = "cancel"
            if not self.caller_phone:
                self.pending_confirmation = "cancel_phone"
                return "I can certainly help you cancel your appointment. What is the phone number you used when booking?", []

            formatted_phone = " ".join(list(self.caller_phone))
            self.pending_confirmation = "cancel"
            return f"Just to confirm before cancelling, your phone number is {formatted_phone}. Is that correct?", []

        # If user was prompted for phone to cancel and provided it in this turn
        if self.current_intent == "cancel" and self.caller_phone:
            formatted_phone = " ".join(list(self.caller_phone))
            self.pending_confirmation = "cancel"
            return f"Just to confirm before cancelling, your phone number is {formatted_phone}. Is that correct?", []

        # ======================================================================
        # Availability Check Intent
        # ======================================================================
        if any(w in last_user_msg for w in [
            "available", "availability", "slot", "slots", "doctor", "specialist",
            "cardiology", "dermatology", "general", "pediatric", "orthopedic",
            "schedule", "openings", "see a doctor", "appointment for"
        ]) and not ("book" in last_user_msg and self.caller_phone):
            self.current_intent = "avail"
            spec = None
            for s in ["cardiology", "dermatology", "general", "pediatric", "orthopedic"]:
                if s in last_user_msg:
                    spec = s
                    break

            doc_name = None
            for d in ["chen", "patel", "rostova", "johnson", "sharma"]:
                if d in last_user_msg:
                    doc_name = d
                    break

            return "Let me check our clinic schedule for you right now.", [{
                "name": "check_doctor_availability",
                "arguments": {
                    "specialty": spec,
                    "doctor_name": doc_name
                }
            }]

        # ======================================================================
        # Booking / Slot Selection Intent (Caller gave phone and/or time)
        # ======================================================================
        if self.caller_phone and self.current_intent != "cancel":
            self.current_intent = "book"
            self.pending_confirmation = "book"
            formatted_phone = " ".join(list(self.caller_phone))
            target_slot = self.selected_slot or (self.available_slots[0] if self.available_slots else "02:00 PM")
            target_doc = self.selected_doctor or "Dr. Sarah Chen"

            return (
                f"Just to make sure I have it right, your phone number is {formatted_phone}, "
                f"for {target_doc} at {target_slot}. Is that correct?"
            ), []

        # If user picked a time but hasn't given phone number yet
        if any(w in last_user_msg for w in ["pm", "am", ":", "morning", "afternoon", "evening", "slot"]):
            return "Got it! Could you please share your phone number so I can secure that appointment for you?", []

        # Farewell / Thank you
        if any(w in last_user_msg for w in ["thank", "thanks", "bye", "goodbye", "that's all", "thats all"]):
            return "You're very welcome! Thank you for calling Nexov Health Clinic. Have a wonderful day!", []

        return "I can help you check doctor availability, book an appointment, or cancel an existing one. Which specialty or doctor would you like to see?", []

    async def _call_gemini(self) -> (str, List[Dict[str, Any]]):
        """Call Google Gemini API with function calling."""
        import urllib.request

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

        contents = []
        for msg in self.history[-6:]:
            if msg["role"] == "system":
                continue
            role = "user" if msg["role"] == "user" else "model"
            text_content = msg.get("content", "")
            contents.append({
                "role": role,
                "parts": [{"text": text_content}]
            })

        tools = [{
            "function_declarations": [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "parameters": t["function"]["parameters"]
                }
                for t in TOOLS_SCHEMA
            ]
        }]

        payload = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "tools": tools,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 250
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        loop = asyncio.get_event_loop()

        def _fetch():
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))

        res = await loop.run_in_executor(None, _fetch)
        candidates = res.get("candidates", [])
        if not candidates:
            return "", []

        parts = candidates[0].get("content", {}).get("parts", [])
        text_response = ""
        tool_calls = []

        for p in parts:
            if "text" in p:
                text_response += p["text"]
            elif "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append({
                    "name": fc["name"],
                    "arguments": fc.get("args", {})
                })

        return text_response, tool_calls

    async def _call_openai(self) -> (str, List[Dict[str, Any]]):
        """Call OpenAI API with function calling."""
        import urllib.request

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": self.history[-8:],
            "tools": TOOLS_SCHEMA,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 200
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
        )

        loop = asyncio.get_event_loop()

        def _fetch():
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read().decode("utf-8"))

        res = await loop.run_in_executor(None, _fetch)
        choice = res["choices"][0]["message"]
        content = choice.get("content") or ""
        tool_calls = []

        if "tool_calls" in choice and choice["tool_calls"]:
            for tc in choice["tool_calls"]:
                tool_calls.append({
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"])
                })

        return content, tool_calls

    async def synthesize_speech(self, text: str) -> Optional[str]:
        """
        Synthesizes text to speech using ElevenLabs API.
        Returns base64-encoded audio data for browser playback.
        """
        if not is_valid_key(ELEVENLABS_API_KEY):
            return None

        import urllib.request
        import base64

        voice_id = ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": ELEVENLABS_API_KEY
            }
        )

        loop = asyncio.get_event_loop()

        def _fetch_audio():
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return resp.read()
            except Exception as e:
                print(f"[ElevenLabs TTS Error] {e}")
                return None

        audio_bytes = await loop.run_in_executor(None, _fetch_audio)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
        return None

    def _clean_for_speech(self, text: str) -> str:
        """Removes markdown syntax so ElevenLabs pronounces natural English."""
        t = re.sub(r'[*_#`~>\[\]]', '', text)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    async def end_call(self):
        """Ends active call."""
        self.is_active = False
        farewell = "Thank you for calling Nexov Health Clinic. Have a wonderful day!"
        await self.send_event({
            "type": "transcript",
            "speaker": "agent",
            "text": farewell,
            "timestamp": datetime.now().strftime("%I:%M:%S %p")
        })
        await self.send_event({"type": "state_change", "state": "ended"})
