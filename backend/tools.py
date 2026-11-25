"""
NexovAI Voice AI Doctor Appointment Assistant
Tool Definitions and Function Calling Handlers for Pipecat & LLMs
"""

import json
from typing import Dict, Any, Optional, Callable
from backend.database import (
    get_available_slots,
    book_appointment as db_book_appointment,
    cancel_appointment as db_cancel_appointment,
)

# Global callback hook to notify frontend dashboard in real-time
_on_action_callback: Optional[Callable[[Dict[str, Any]], Any]] = None


def set_action_callback(cb: Callable[[Dict[str, Any]], Any]):
    global _on_action_callback
    _on_action_callback = cb


def _notify_frontend(event_type: str, data: Dict[str, Any]):
    if _on_action_callback:
        try:
            import asyncio
            if asyncio.iscoroutinefunction(_on_action_callback):
                asyncio.create_task(_on_action_callback({"type": event_type, "data": data}))
            else:
                _on_action_callback({"type": event_type, "data": data})
        except Exception as e:
            print(f"Error notifying frontend callback: {e}")


# ==============================================================================
# Core Business Logic Handlers
# ==============================================================================

def execute_check_doctor_availability(
    doctor_name: Optional[str] = None,
    specialty: Optional[str] = None,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns available slots for a doctor and/or date so the agent can offer them.
    """
    slots = get_available_slots(doctor_name=doctor_name, specialty=specialty, date=date)
    result = {
        "count": len(slots),
        "available_slots": slots,
        "query": {
            "doctor_name": doctor_name,
            "specialty": specialty,
            "date": date
        }
    }
    _notify_frontend("availability_checked", result)
    return result


def execute_book_appointment(
    patient_phone: str,
    doctor_name: str,
    date: str,
    time_slot: str,
    patient_name: str = "Caller"
) -> Dict[str, Any]:
    """
    Books a selected slot for the caller using the phone number they spoke.
    """
    res = db_book_appointment(
        patient_phone=patient_phone,
        doctor_name=doctor_name,
        date=date,
        time_slot=time_slot,
        patient_name=patient_name
    )
    if res.get("success"):
        _notify_frontend("appointment_booked", res)
    return res


def execute_cancel_appointment(
    patient_phone: str,
    appointment_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Cancels the caller's existing appointment found using their spoken phone number.
    """
    res = db_cancel_appointment(
        patient_phone=patient_phone,
        appointment_id=appointment_id
    )
    if res.get("success"):
        _notify_frontend("appointment_cancelled", res)
    return res


# ==============================================================================
# Pipecat Tool Schema Declarations
# ==============================================================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": "Check available appointment slots for doctors by name, specialty, or date. Always call this when a caller inquires about open timings or doctor schedules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Doctor's name, e.g. Dr. Sarah Chen, Dr. Patel"
                    },
                    "specialty": {
                        "type": "string",
                        "description": "Medical specialty e.g. Cardiology, Dermatology, General Medicine, Pediatrics, Orthopedics"
                    },
                    "date": {
                        "type": "string",
                        "description": "Desired appointment date in YYYY-MM-DD format"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Books a doctor appointment. MUST only be called after you have read the caller's phone number back to them out loud and received their confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_phone": {
                        "type": "string",
                        "description": "The caller's confirmed phone number (e.g., 9876543210)"
                    },
                    "doctor_name": {
                        "type": "string",
                        "description": "The full name of the doctor"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of the appointment in YYYY-MM-DD format"
                    },
                    "time_slot": {
                        "type": "string",
                        "description": "Time of the slot, e.g. '09:30 AM', '02:00 PM'"
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Name of the caller if provided (optional)"
                    }
                },
                "required": ["patient_phone", "doctor_name", "date", "time_slot"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancels an existing appointment for the caller. MUST only be called after you have read the caller's phone number back to them out loud and received their confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_phone": {
                        "type": "string",
                        "description": "The caller's confirmed phone number used when booking"
                    },
                    "appointment_id": {
                        "type": "integer",
                        "description": "Optional specific appointment ID if known"
                    }
                },
                "required": ["patient_phone"]
            }
        }
    }
]


# ==============================================================================
# Pipecat Async Handlers
# ==============================================================================

async def pipecat_check_doctor_availability(params):
    """Pipecat function handler for availability checking."""
    args = getattr(params, "arguments", {}) or {}
    res = execute_check_doctor_availability(
        doctor_name=args.get("doctor_name"),
        specialty=args.get("specialty"),
        date=args.get("date")
    )
    if hasattr(params, "result_callback"):
        await params.result_callback(res)
    return res


async def pipecat_book_appointment(params):
    """Pipecat function handler for booking appointment."""
    args = getattr(params, "arguments", {}) or {}
    res = execute_book_appointment(
        patient_phone=args.get("patient_phone", ""),
        doctor_name=args.get("doctor_name", ""),
        date=args.get("date", ""),
        time_slot=args.get("time_slot", ""),
        patient_name=args.get("patient_name", "Caller")
    )
    if hasattr(params, "result_callback"):
        await params.result_callback(res)
    return res


async def pipecat_cancel_appointment(params):
    """Pipecat function handler for cancelling appointment."""
    args = getattr(params, "arguments", {}) or {}
    res = execute_cancel_appointment(
        patient_phone=args.get("patient_phone", ""),
        appointment_id=args.get("appointment_id")
    )
    if hasattr(params, "result_callback"):
        await params.result_callback(res)
    return res
