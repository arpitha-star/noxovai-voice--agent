import asyncio
from backend.pipeline import PipecatVoiceEngine

events = []
async def mock_send(evt):
    events.append(evt)

async def test():
    engine = PipecatVoiceEngine(send_event=mock_send)
    await engine.start_call()
    
    print("--- TURN 1: User asks to cancel ---")
    await engine.handle_user_speech("I would like to cancel my appointment")
    print("Agent reply:", [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"])

    print("\n--- TURN 2: User provides phone number ---")
    await engine.handle_user_speech("9876 543210")
    print("Agent reply:", [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"])

    print("\n--- TURN 3: User confirms ---")
    await engine.handle_user_speech("yes, it is correct")
    print("Agent reply:", [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"])
    
    cancelled_events = [e for e in events if e.get("type") == "appointment_cancelled"]
    print("\nAppointment Cancelled Event emitted:", len(cancelled_events) > 0)
    if cancelled_events:
        print("Data:", cancelled_events[0]["data"])

if __name__ == "__main__":
    asyncio.run(test())
