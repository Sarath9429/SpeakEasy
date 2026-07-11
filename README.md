# 🎙️ SynthSpeak — AI-Powered Presentation & Interview Coach

<p align="center">
    <a href="#"><img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-14354C.svg?logo=python&logoColor=white"></a>
    <a href="#"><img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white"></a>
    <a href="#"><img alt="MediaPipe" src="https://img.shields.io/badge/MediaPipe-4285F4.svg?logo=google&logoColor=white"></a>
    <a href="#"><img alt="Deepgram" src="https://img.shields.io/badge/Deepgram-Nova--2-13EF93.svg?logo=deepgram&logoColor=white"></a>
    <a href="#"><img alt="NVIDIA" src="https://img.shields.io/badge/NVIDIA-Llama--3.1-76B900.svg?logo=nvidia&logoColor=white"></a>
    <a href="#"><img alt="WebSocket" src="https://img.shields.io/badge/WebSocket-Live-orange.svg?logo=socketdotio&logoColor=white"></a>
</p>

A real-time **AI coaching platform** that helps you master public speaking and ace job interviews. SynthSpeak analyzes your **speech content**, **vocal quality**, **body language**, and **eye contact** simultaneously — delivering instant, actionable feedback through a live browser dashboard powered by WebSockets.

---

# ➤ Contents
1) [Project Showcase](#Project-Showcase)
2) [Features Explained](#Features-Explained)
3) [System Architecture](#System-Architecture)
4) [Technology Stack](#Technology-Stack)
5) [Requirements & Setup](#Requirements)
6) [API Reference](#API-Reference)
7) [License](#License)

---

<h1 id="Project-Showcase">📸 Project Showcase</h1>

### 🎬 Demo Video

<!-- ╔════════════════════════════════════════════════════════════════╗ -->
<!-- ║  HOW TO ADD YOUR DEMO VIDEO:                                  ║ -->
<!-- ║                                                                ║ -->
<!-- ║  Option 1 — Local MP4/WebM:                                   ║ -->
<!-- ║    <video src="demo.mp4" controls width="100%"></video>        ║ -->
<!-- ║                                                                ║ -->
<!-- ║  Option 2 — YouTube Link:                                     ║ -->
<!-- ║    [![Demo](https://img.youtube.com/vi/VIDEO_ID/0.jpg)]       ║ -->
<!-- ║    (https://www.youtube.com/watch?v=VIDEO_ID)                  ║ -->
<!-- ║                                                                ║ -->
<!-- ║  Option 3 — GIF:                                              ║ -->
<!-- ║    ![SynthSpeak Demo](demo.gif)                               ║ -->
<!-- ╚════════════════════════════════════════════════════════════════╝ -->

<p align="center">

  <!-- 🔽 REPLACE THIS BLOCK WITH YOUR ACTUAL DEMO VIDEO / GIF 🔽 -->

  <img src="https://via.placeholder.com/800x450/1a1a2e/16c79a?text=🎬+Demo+Video+Coming+Soon" alt="Demo Placeholder" width="80%"/>

  <!-- 🔼 REPLACE THIS BLOCK WITH YOUR ACTUAL DEMO VIDEO / GIF 🔼 -->

</p>

<p align="center"><i>⬆️ Replace this placeholder with your recorded demo</i></p>

### 🖼️ Screenshots
| **Presentation Mode** | **Interview Mode** |
| :---: | :---: |
| ![Presentation](https://via.placeholder.com/400x250/1a1a2e/16c79a?text=Presentation+Mode) | ![Interview](https://via.placeholder.com/400x250/1a1a2e/16c79a?text=Interview+Mode) |
| *Real-time speech & body language coaching* | *AI-generated questions with structured feedback* |

| **Recordings Archive** | **Live Dashboard** |
| :---: | :---: |
| ![Recordings](https://via.placeholder.com/400x250/1a1a2e/16c79a?text=Recordings+Archive) | ![Dashboard](https://via.placeholder.com/400x250/1a1a2e/16c79a?text=Live+Dashboard) |
| *Session playback and retroactive analysis* | *10 Hz WebSocket-powered live metrics* |

---

<h1 id="Features-Explained">🛡️ Features Explained</h1>

SynthSpeak operates in two primary modes, each backed by three parallel AI pipelines:

### 1. Presentation Mode
Type in your slide topic and SynthSpeak coaches you in real-time while you speak. It monitors **what you say** and **how you say it**, plus your **physical delivery** — all at once.

| Category | What's Tracked | Powered By |
| :--- | :--- | :--- |
| **Topic Relevance** | Scores (0–100%) how well your speech aligns with your topic | NVIDIA Llama 3.1 |
| **Filler Words** | Detects `um`, `uh`, `like`, `you know`, `basically`, and 10+ patterns | Deepgram Nova-2 |
| **Speaking Pace** | Live words-per-minute (WPM) tracking | Deepgram Nova-2 |
| **Long Pauses** | Flags silences longer than 2 seconds | Audio Pipeline |
| **Eye Contact** | Iris tracking to detect if you're looking at the camera or away | MediaPipe FaceMesh (478 pts) |
| **Posture Score** | 0–100 score checking slouching, shoulder alignment, leaning, centering | MediaPipe BlazePose (33 joints) |
| **Hand Gestures** | Classifies gesture type and movement intensity | MediaPipe Hands (21 pts/hand) |
| **Face Orientation** | Pitch, yaw, roll angles — detects if you're facing the camera | FaceMesh 3D geometry |

### 2. Interview Mode
Upload your resume and let the AI simulate a real interview experience:

1. **Upload Resume** — Supports PDF, DOCX, or plain text.
2. **AI Generates 5 Questions** — NVIDIA Llama 3.1 reads your resume and creates tailored, challenging questions based on your skills and projects.
3. **Answer Out Loud** — Speak naturally; your voice is transcribed live.
4. **Get Structured Feedback** — For each answer, the AI returns:
   - **Growth Area** — What to improve
   - **Missing Points** — Key things you forgot to mention
   - **Better Version** — A model ideal answer
   - **Follow-up Questions** — What an interviewer might ask next

### 3. Session Recordings & History
* Every session is **auto-saved** as a WAV file when you stop.
* **Upload any past recording** for retroactive analysis (transcript, filler count, WPM, relevance).
* All sessions are logged to a **SQLite database** with scores, duration, and timestamps.

---

<h1 id="System-Architecture">🏗️ System Architecture</h1>

Below is the high-level system flow from browser input to real-time coaching feedback.

```
┌─────────────────────────────────────────────────────────────┐
│                    BROWSER (Frontend)                        │
│                                                              │
│   getUserMedia ──► Camera + Mic ──► WebSocket Stream          │
│                                                              │
│   Live Dashboard ◄── JSON state @ 10 Hz ◄── Server           │
│   (Scores, Transcript, Gauges, Feedback Cards)               │
└──────────────────────────────┬───────────────────────────────┘
                               │ WebSocket (ws://)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   FASTAPI SERVER (Backend)                    │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Visual Pipeline│  │ Audio Pipeline │  │ Fusion Layer  │  │
│  │                │  │                │  │               │  │
│  │ • FaceMesh     │  │ • Deepgram     │  │ • NVIDIA      │  │
│  │   (478 pts)    │  │   Nova-2 API   │  │   Llama 3.1   │  │
│  │ • BlazePose    │  │ • Filler word  │  │ • Semantic     │  │
│  │   (33 joints)  │  │   detection    │  │   relevance   │  │
│  │ • Hand Tracker │  │ • WPM / Pause  │  │   scoring     │  │
│  │   (21 pts/hand)│  │ • WAV export   │  │ • TF-IDF      │  │
│  │                │  │                │  │   fallback    │  │
│  └───────┬────────┘  └───────┬────────┘  └───────┬───────┘  │
│          └───────────────────┼────────────────────┘           │
│                              ▼                               │
│           ┌──────────────────────────────────┐               │
│           │  SharedState (Thread-safe store)  │               │
│           │  Syncs all pipelines @ 10 Hz      │               │
│           └──────────────────────────────────┘               │
│                                                              │
│  SQLite DB (history)  •  Recordings (WAV/WebM)  •  REST API │
└──────────────────────────────────────────────────────────────┘
                        │               │
                        ▼               ▼
              ┌─────────────┐  ┌──────────────┐
              │  Deepgram   │  │  NVIDIA NIM  │
              │  Cloud API  │  │  Cloud API   │
              └─────────────┘  └──────────────┘
```

---

<h1 id="Technology-Stack">⚙️ Technology Stack</h1>

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Backend** | FastAPI + Uvicorn | Async HTTP + WebSocket server |
| **Speech-to-Text** | Deepgram Nova-2 | Live audio transcription with filler detection |
| **LLM Scoring** | NVIDIA Llama-3.1-70B | Topic relevance grading + interview coaching |
| **Face Analysis** | MediaPipe FaceMesh | 478-point facial landmarks for eye contact & gaze |
| **Pose Estimation** | MediaPipe BlazePose | 33-joint skeleton for posture detection |
| **Hand Tracking** | MediaPipe Hands | Gesture classification & movement intensity |
| **Database** | SQLite | Session history storage |
| **Frontend** | Vanilla HTML / CSS / JS | WebSocket-powered live dashboard |
| **Deployment** | Render.com | One-click deploy via `render.yaml` blueprint |

---

<h1 id="Requirements">🛠️ Setup & Installation</h1>

### 1. Requirements
* **Python 3.10+**
* A **webcam** and **microphone**
* API keys from:
  * 🔑 [Deepgram](https://deepgram.com) — for speech-to-text (free tier available)
  * 🔑 [NVIDIA NIM](https://build.nvidia.com) — for LLM scoring (free tier available)

### Install all required libraries from the requirements file
```powershell
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
# Create a virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 3. Set Your API Keys

```powershell
# Windows (PowerShell)
$env:NVIDIA_API_KEY = "nvapi-xxxxxxxxxxxxxxxxxxxx"
$env:DEEPGRAM_API_KEY = "your_deepgram_key_here"
```
```bash
# Linux / macOS
export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
export DEEPGRAM_API_KEY=your_deepgram_key_here
```

### 4. Run the Server
```powershell
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

Open your browser at: **http://localhost:8000**

> **Note:** Grant camera and microphone permissions when prompted. SynthSpeak needs both to function.

### 5. Cloud Deployment (Render.com)
SynthSpeak ships with a `render.yaml` blueprint for one-click deployment:
1. Push your code to GitHub.
2. Log into [Render.com](https://render.com) → **New** → **Blueprint**.
3. Connect your repo — Render auto-detects the configuration.
4. Add `NVIDIA_API_KEY` and `DEEPGRAM_API_KEY` as **Environment Variables**.
5. Click **Deploy** ✅

---

<h1 id="API-Reference">📡 API Reference</h1>

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serve the main dashboard |
| `GET` | `/health` | Health check |
| `POST` | `/start` | Start all AI pipelines |
| `POST` | `/stop` | Stop all AI pipelines |
| `POST` | `/manual` | Set a manual topic `{ "topic": "..." }` |
| `POST` | `/reset` | Reset the current topic |
| `GET` | `/recordings` | List all saved recordings |
| `POST` | `/recordings/upload` | Upload a browser recording |
| `POST` | `/analyze-upload` | Retroactive analysis of a recording |
| `POST` | `/api/generate-questions-from-resume` | Generate interview questions from resume |
| `POST` | `/interview/feedback` | Get AI feedback on an interview answer |
| `WebSocket` | `/ws/stream` | Real-time video + audio streaming |

---

<h1 id="License">📄 License</h1>

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with ❤️ using FastAPI • MediaPipe • Deepgram • NVIDIA NIM</b><br/>
  <sub>SynthSpeak — Because great speakers aren't born, they're coached.</sub>
</p>
