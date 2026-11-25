# NexovAI Voice AI Doctor Appointment Assistant

An autonomous, real-time voice virtual receptionist built for healthcare clinics using **Pipecat**, **ElevenLabs** (STT & TTS), and **Google Gemini** (with native function calling). Callers interact entirely via spoken voice to check doctor schedules, book appointments, and cancel existing visits. 

---

## 🌟 Core Features & Compliance

- **Spoken Phone Identification**: Callers are authenticated solely by the phone number they speak out loud (no logins, no passwords, no OTPs, no caller-ID).
- **Mandatory Read-Back Confirmation**: Before executing any booking or cancellation, the AI receptionist repeats the phone number back to the caller for verbal verification.
- **Pipecat Voice Pipeline**: Real-time pipeline connecting caller audio $\rightarrow$ STT $\rightarrow$ LLM $\rightarrow$ TTS $\rightarrow$ caller audio.
- **Three Required Tools Implemented**:
  1. `check_doctor_availability`: Inspects available doctor slots filtered by specialty, doctor name, or date.
  2. `book_appointment`: Secures a slot for the caller using their verified phone number.
  3. `cancel_appointment`: Finds and cancels an existing booking for the verified phone number.
- **Real-Time Synchronized Dashboard**:
  - Start and end voice calls directly inside the browser.
  - Live conversation transcript stream.
  - Real-time doctors and available slots directory.
  - Live clinic appointment ledger that automatically updates upon booking or cancellation.

### 🎁 Bonus Features Included
- **Silero VAD (Voice Activity Detection)** integrated in Pipecat for low-latency conversational turn-taking.
- **Interactive Phone-Style Call Screen**: Floating smartphone interface with ringing, connected, and ended states, live timer, and caller avatar.
- **Dynamic Audio Waveform**: Canvas visualizer responding in real-time to speech frequencies.
- **In-Phone Booking Confirmation Card**: Pops up inside the call interface immediately upon successful booking.
- **Dashboard Row Flashing**: Animated green highlight on new bookings and red highlight on cancellations.
- **Realistic Telephony Audio**: Built-in Web Audio API synthesizers for ringing tones, connected chimes, and hangup sounds without requiring external assets.

---

## 🛠️ Tech Stack & LLM Choice

| Component | Technology | Description |
|---|---|---|
| **Pipeline Framework** | [Pipecat](https://github.com/pipecat-ai/pipecat) (Python) | Ultra low-latency orchestration for voice agents |
| **LLM Provider** | **Google Gemini 2.5 Flash** (or Gemini 1.5 Flash) | Fast response latency, strong tool calling & free tier quota |
| **STT (Speech-to-Text)** | **ElevenLabs** / Web Speech API Fallback | Real-time voice transcription |
| **TTS (Text-to-Speech)** | **ElevenLabs** (`eleven_turbo_v2_5` - Rachel) | Lifelike, warm conversational speech synthesis |
| **VAD** | **Silero VAD** | Robust voice activity detection |
| **Backend & Sync** | FastAPI + WebSockets | Asynchronous event streaming & REST API |
| **Database** | SQLite | Persistent, conflict-safe relational storage |
| **Frontend** | Modern HTML5, Custom CSS Design System & JS | Clean, non-generic clinic dashboard |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, and 3.13)
- Google Gemini API Key ([Get one free at Google AI Studio](https://aistudio.google.com/))
- ElevenLabs API Key ([ElevenLabs Dashboard](https://elevenlabs.io/))

### 2. Clone and Setup
```bash
git clone <your-repository-url>
cd nexovai-voice-agent

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys:
```env
# ElevenLabs API Key & Voice ID
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# Google Gemini API Key (Recommended)
GEMINI_API_KEY=your_gemini_api_key_here

# (Optional) OpenAI API Key fallback
OPENAI_API_KEY=your_openai_key_if_used

PORT=8000
```
> *Note: If run without API keys, the engine automatically runs in built-in heuristic test mode with browser speech synthesis so you can test all features and UI interactions immediately!*

### 4. Run Automated Test Suite
To verify database operations, slot locks, and tool handlers:
```bash
python test_app.py
```

### 5. Launch Application
```bash
python main.py
```
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 📁 Project Structure

```
nexovai-voice-agent/
├── backend/
│   ├── database.py           # SQLite manager, slot reservations & mock data
│   ├── pipeline.py           # WebSocket voice engine & LLM tool execution
│   ├── pipecat_pipeline.py   # Idiomatic Pipecat pipeline (VAD -> STT -> LLM -> TTS)
│   ├── prompts.py            # System prompts & conversational business constraints
│   └── tools.py              # Tool schemas (availability, booking, cancellation)
├── static/
│   ├── css/
│   │   └── style.css         # Clinical dark-mode design system & animations
│   ├── js/
│   │   ├── app.js            # WebSocket client, speech bridge & ledger sync
│   │   ├── audio-visualizer.js # Canvas audio waveform visualizer
│   │   └── call-sounds.js    # Web Audio API telephone sound synthesizer
│   └── index.html            # Main clinic dashboard & phone-call modal
├── appointments.db           # SQLite database
├── test_app.py               # Automated unit tests
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── pipeline_description.md   # Written pipeline overview for submission
└── README.md                 # Complete documentation
```

---

## 🎬 3-Minute Video Demo Walkthrough

When recording your submission video, follow this streamlined flow:

1. **Dashboard Overview (0:00 - 0:25)**:
   - Show the clinic dashboard with available doctors across Cardiology, Dermatology, General Medicine, Orthopedics, and Pediatrics.
   - Point out the real-time slot counter and current bookings table.

2. **Starting the Voice Call (0:25 - 0:45)**:
   - Click **"📞 Try Call"**.
   - Show the phone-style modal popping up with ringing tone and audio waveform.
   - The AI agent greets: *"Hello! Thank you for calling Nexov Health Clinic. I'm your AI virtual receptionist. How can I help you today?"*

3. **Availability & Phone Number Flow (0:45 - 1:40)**:
   - **User**: *"I need to see a cardiologist tomorrow."*
   - **Agent**: Calls `check_doctor_availability`, offers Dr. Sarah Chen's open slots.
   - **User**: *"Let's do 2:00 PM. My phone number is 9876543210."*
   - **Agent (Mandatory Read-Back)**: *"Just to make sure I have it right, your phone number is 9 8 7, 6 5 4, 3 2 1 0. Is that correct?"*
   - **User**: *"Yes, that is correct."*

4. **Booking Confirmation & Dashboard Update (1:40 - 2:20)**:
   - Agent calls `book_appointment`.
   - The green **Appointment Confirmed** card appears inside the phone screen.
   - Behind the phone, the new appointment row instantly appears in the ledger with a glowing green pulse.
   - The doctor's available slot updates in real-time.

5. **(Bonus) Cancellation Flow (2:20 - 2:50)**:
   - **User**: *"Actually, I also have an appointment under 5551234567 that I need to cancel."*
   - **Agent**: Repeats number to confirm $\rightarrow$ User confirms $\rightarrow$ `cancel_appointment` executes.
   - Ledger updates the status to `cancelled` with a red highlight animation.

6. **Wrap-up (2:50 - 3:00)**:
   - Click End Call $\rightarrow$ Telephone disconnect sound plays.
