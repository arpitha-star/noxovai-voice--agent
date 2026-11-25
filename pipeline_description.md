# NexovAI Voice AI Doctor Appointment Assistant – Pipeline Description

### Architecture Overview
I built an end-to-end real-time voice conversational pipeline designed around **Pipecat**, **ElevenLabs**, and **Google Gemini (with function calling)**, integrated with a live clinic dashboard over bidirectional WebSockets.

```
Caller Voice (Browser Mic)
   │
   ▼
[Silero VAD] ──── (Detects speech boundaries & caller interruptions)
   │
   ▼
[ElevenLabs STT] ─── (Real-time speech-to-text transcription)
   │
   ▼
[Google Gemini 2.5 Flash] ─── (System prompt with business logic + Function Calling)
   │
   ├── Tools Executed:
   │    ├── `check_doctor_availability(doctor_name, specialty, date)`
   │    ├── `book_appointment(patient_phone, doctor_name, date, time_slot)`
   │    └── `cancel_appointment(patient_phone, appointment_id)`
   │
   ▼
[ElevenLabs TTS (Turbo v2.5)] ─── (Low-latency audio synthesis)
   │
   ▼
Caller Audio Playback (Speaker) + Live Dashboard Synchronizer (WebSockets)
```

---

### Step-by-Step Flow

1. **Audio Capture & VAD (Silero)**:
   - Caller speaks via the browser microphone.
   - Silero VAD segments audio chunks, suppressing ambient noise and cleanly catching when the caller starts and finishes speaking.

2. **Speech-to-Text (ElevenLabs STT)**:
   - Spoken audio stream is transcribed into text in near real-time.
   - The transcript is immediately broadcasted via WebSocket to the frontend dashboard phone screen.

3. **LLM Orchestration & Business Rules (Google Gemini)**:
   - Powered by `gemini-2.5-flash` with function schemas registered in Pipecat.
   - **Enforced Business Constraint 1**: Caller identity is anchored *strictly* to the spoken phone number (zero logins, zero OTPs, zero caller-ID spoofing).
   - **Enforced Business Constraint 2**: Before committing a booking or cancellation, the LLM is instruction-tuned to read the extracted phone number back to the user for explicit oral confirmation ("Just to confirm, your phone number is 9 8 7, 6 5 4, 3 2 1 0. Is that correct?").

4. **Deterministic Tool Execution (SQLite)**:
   - When confirmed, the LLM issues a structured function call (`book_appointment` or `cancel_appointment`).
   - The tool executes against the local SQLite database, atomically updating slot availability and the appointments ledger.
   - A real-time notification callback fires over WebSockets to trigger instantaneous UI row updates and flash animations on the admin dashboard.

5. **Text-to-Speech (ElevenLabs TTS)**:
   - The LLM's natural spoken response is stripped of formatting markdown and passed to ElevenLabs TTS using the `eleven_turbo_v2_5` model.
   - Audio chunks stream back to the client for playback, accompanied by a dynamic canvas audio waveform visualizer.

### Why this design works well in production:
It separates conversational flexibility from deterministic database actions. The caller feels like they are talking to a warm, attentive clinic receptionist, while the clinic receives strictly validated, conflict-free appointment bookings on their live ledger.
