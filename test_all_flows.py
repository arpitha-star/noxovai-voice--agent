import asyncio
from backend.pipeline import PipecatVoiceEngine
from backend.database import init_db

async def run_full_flow_test():
    print("=" * 60)
    print("RUNNING COMPLETE DIALOGUE FLOW TEST")
    print("=" * 60)
    init_db(force_reset=True)

    events = []
    async def mock_send(evt):
        events.append(evt)

    engine = PipecatVoiceEngine(send_event=mock_send)
    await engine.start_call()

    # Step 1: User asks for cardiology availability
    print("\n[Step 1] User: Hi, I'd like to check availability for cardiology.")
    await engine.handle_user_speech("Hi, I'd like to check availability for cardiology.")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent: {agent_msg}")
    assert "Dr. Sarah Chen" in agent_msg, "Failed to offer Dr. Sarah Chen"
    assert "Which time works best for you" in agent_msg, "Failed to ask for time and phone"

    # Step 2: User provides time and phone
    print("\n[Step 2] User: Let's do 2:00 PM. My phone number is 9876543210.")
    await engine.handle_user_speech("Let's do 2:00 PM. My phone number is 9876543210.")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent: {agent_msg}")
    assert "9 8 7 6 5 4 3 2 1 0" in agent_msg, "Failed to read back phone number"
    assert "Is that correct" in agent_msg, "Failed to ask confirmation"

    # Step 3: User confirms booking
    print("\n[Step 3] User: Yes, that's correct.")
    await engine.handle_user_speech("Yes, that's correct.")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent: {agent_msg}")
    assert "confirmed" in agent_msg.lower(), "Booking confirmation failed"
    booked_evts = [e for e in events if e.get("type") == "appointment_booked"]
    assert len(booked_evts) > 0, "No appointment_booked event emitted"
    print(f"-> Appointment booked: ID {booked_evts[0]['data']['appointment_id']}")

    # Step 4: User wants to cancel in the same call
    print("\n[Step 4] User: I would like to cancel my appointment.")
    await engine.handle_user_speech("I would like to cancel my appointment.")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent: {agent_msg}")
    assert "9 8 7 6 5 4 3 2 1 0" in agent_msg or "phone number" in agent_msg, "Failed readback for cancellation"

    # Step 5: User confirms cancellation
    print("\n[Step 5] User: Yes, it's correct.")
    await engine.handle_user_speech("Yes, it's correct.")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent: {agent_msg}")
    assert "cancelled" in agent_msg.lower(), "Cancellation confirmation failed"
    cancelled_evts = [e for e in events if e.get("type") == "appointment_cancelled"]
    assert len(cancelled_evts) > 0, "No appointment_cancelled event emitted"
    print(f"-> Appointment cancelled: ID {cancelled_evts[0]['data']['appointment_id']}")

    print("\n" + "=" * 60)
    print("ALL 5 STEPS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_full_flow_test())
