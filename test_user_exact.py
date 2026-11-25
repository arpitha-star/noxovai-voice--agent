import asyncio
from backend.pipeline import PipecatVoiceEngine
from backend.database import init_db

async def test_user_exact_words():
    print("=" * 60)
    print("TESTING USER'S EXACT SPOKEN WORDS")
    print("=" * 60)
    init_db(force_reset=True)

    events = []
    async def mock_send(evt):
        events.append(evt)

    engine = PipecatVoiceEngine(send_event=mock_send)
    await engine.start_call()

    # Turn 1
    t1 = "hide can you check for the doctor availability for cardiology"
    print(f"\nUser 1: {t1}")
    await engine.handle_user_speech(t1)
    agent_msg1 = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent 1: {agent_msg1}")

    # Turn 2
    t2 = "okay Buddha apartment for the 2:00 p.m. and my phone number is 9876 543210"
    print(f"\nUser 2: {t2}")
    await engine.handle_user_speech(t2)
    agent_msg2 = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent 2: {agent_msg2}")

    # Turn 3: User says "it's correct"
    t3 = "it's correct"
    print(f"\nUser 3: {t3}")
    await engine.handle_user_speech(t3)
    agent_msg3 = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    print(f"Agent 3: {agent_msg3}")

    booked_evts = [e for e in events if e.get("type") == "appointment_booked"]
    print(f"\nAppointment Booked Event Emitted: {len(booked_evts) > 0}")
    if booked_evts:
        print("Data:", booked_evts[0]["data"])

if __name__ == "__main__":
    asyncio.run(test_user_exact_words())
