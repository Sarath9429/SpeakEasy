# SynthSpeak — AI-Powered Presentation & Interview Coach

> **Your personal AI speaking coach. Master presentations and ace your interviews with real-time feedback on your speech, posture, and body language.**

---

## Demo

<!-- Add your demo video or screenshot below -->
> 🎬 **Project Demo Video**
>
> ![Demo Video](demo.gif)

<!-- Or use a screenshot:
> ![Dashboard Screenshot](screenshot.png)
-->

---

## What is SynthSpeak?

SynthSpeak is a real-time AI coaching platform that helps you master public speaking and job interviews. It silently acts as your personal coach — analyzing your body language, eye contact, and speech clarity while you talk, and giving you instant feedback to improve your delivery.

### What it coaches you on:
| Dimension | What's Measured |
|---|---|
| **Speech Content** | Relevance to your chosen topic, transcript quality |
| **Speech Quality** | Filler words (`um`, `uh`, `like`, ...), words-per-minute, long pauses |
| **Body Language** | Eye contact, posture, head orientation, hand gestures |
| **Interview Skills** | Per-question LLM feedback, follow-up question generation |

---

## Key Features

- 🎤 **Real-time Speech-to-Text** — Deepgram Nova-2 transcribes your speech instantly with filler-word detection.
- 🧠 **Semantic Relevance Scoring** — NVIDIA Llama 3.1 grades how well your speech aligns with your topic in real time.
- 👁️ **Body Language Analysis** — MediaPipe tracks 478 facial landmarks + full-body pose to detect eye contact, posture, and hand gestures.
- 💼 **Interview Mode** — Upload your resume, get 5 AI-generated questions, and receive structured feedback for each answer.
- 🎙️ **Recordings Archive** — Every session is auto-saved. Upload any recording for a retroactive analysis.
- 🌐 **Live Web Dashboard** — A WebSocket-powered browser UI that streams live video, transcripts, and scores.

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Backend Server** | FastAPI + Uvicorn | Async REST + WebSocket server |
| **Speech-to-Text** | Deepgram Nova-2 | Live audio transcription |
| **Relevance Scoring** | NVIDIA Llama-3.1-405B | Grades speech relevance to topic |
| **Pose & Face** | MediaPipe (BlazePose + FaceMesh) | Eye contact, posture, gaze analysis |
| **Hand Tracking** | MediaPipe Hands | Gesture type and movement intensity |
| **Interview Coaching** | NVIDIA Llama-3.1-70B | Generates questions and per-answer feedback |
| **Database** | SQLite | Session history storage |
| **Frontend** | Vanilla HTML / CSS / JS | WebSocket dashboard UI |

---

## Setup & Running Locally

### Prerequisites
- Python 3.10+
- A webcam and microphone
- API keys from [Deepgram](https://deepgram.com) and [NVIDIA](https://build.nvidia.com)

### 1. Clone & Install
```bash
git clone https://github.com/yourname/SynthSpeak.git
cd SynthSpeak
pip install -r requirements.txt
```

### 2. Set your API Keys
```bash
# Windows
set NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
set DEEPGRAM_API_KEY=your_deepgram_key_here

# Linux / macOS
export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
export DEEPGRAM_API_KEY=your_deepgram_key_here
```

### 3. Run
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```
Open your browser at: **http://localhost:8000**

---

## Deploying to Render.com

SynthSpeak includes a `render.yaml` blueprint for one-click cloud deployment.

1. Push your code to GitHub (make sure `.gitignore` excludes your virtual environment and recordings folder).
2. Log into [Render.com](https://render.com), click **New > Web Service**.
3. Connect your GitHub repository — Render auto-detects the configuration.
4. Add `NVIDIA_API_KEY` and `DEEPGRAM_API_KEY` as Environment Variables in the dashboard.
5. Click **Deploy**. Your app is now live with full HTTPS camera/mic support. ✅

---

## Modes of Operation

### Presentation Mode
Type in your slide topic and SynthSpeak will coach you on staying on topic, reducing filler words, maintaining good posture, and speaking at the right pace — all in real time.

### Interview Mode
1. Upload your **resume** (PDF, DOCX, or TXT).
2. The AI generates **5 tailored interview questions**.
3. Answer each question out loud — your speech is transcribed live.
4. After each answer, receive AI feedback:
   - **Growth Area** — what to improve
   - **Missing Points** — key things you forgot to mention
   - **Better Version** — a model ideal answer
   - **Follow-up Questions** — what an interviewer might ask next

---

## Session History

Every session result is logged to a local SQLite database (`synthspeak.db`) including:
- Overall score, relevance score, speech quality, and body language score
- Session duration and type (presentation or interview)
- Timestamp of each session

---

*Built with ❤️ using FastAPI, MediaPipe, Deepgram, and NVIDIA NIM.*
