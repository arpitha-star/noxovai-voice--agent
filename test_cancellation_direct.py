import asyncio
from backend.pipeline import PipecatVoiceEngine
from backend.database import init_db

async def test_direct_cancel(affirm_text):
    init_db(force_reset=True)
    events = []
    async def mock_send(evt):
        events.append(evt)

    engine = PipecatVoiceEngine(send_event=mock_send)
    await engine.start_call()

    # Step 1
    await engine.handle_user_speech("I would like to cancel my appointment")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    assert "phone number" in agent_msg.lower()

    # Step 2
    await engine.handle_user_speech("9876 543210")
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    assert "9 8 7 6 5 4 3 2 1 0" in agent_msg
    assert "confirm" in agent_msg.lower() or "correct" in agent_msg.lower()

    # Step 3
    await engine.handle_user_speech(affirm_text)
    agent_msg = [e for e in events if e.get("type") == "transcript" and e.get("speaker") == "agent"][-1]["text"]
    assert "cancelled" in agent_msg.lower(), f"Failed for '{affirm_text}': got '{agent_msg}'"
    cancelled_evts = [e for e in events if e.get("type") == "appointment_cancelled"]
    assert len(cancelled_evts) > 0

async def main():
    variations = [
        "yes",
        "yes, that's correct",
        "yes, it's correct",
        "yes, it's correct, my phone number is correct",
        "correct",
        "that's right",
        "sure, please cancel it",
        "yes please"
    ]
    for text in variations:
        await test_direct_cancel(text)
        print(f"[PASS] Direct cancellation succeeded with affirmation: '{text}'")

if __name__ == "__main__":
    asyncio.run(main())
