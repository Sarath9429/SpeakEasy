<p align="center">
  <img src="https://img.shields.io/badge/SpeakEasy-AI%20Coaching%20Platform-blueviolet?style=for-the-badge&logo=microphone&logoColor=white" alt="SpeakEasy Badge"/>
</p>

<h1 align="center">🎙️ SpeakEasy</h1>

<p align="center">
  <b>AI-Powered Presentation Coach & Interview Simulator</b><br/>
  <i>Master public speaking. Ace your interviews. Get real-time feedback on speech, posture, and body language — all from your browser.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/MediaPipe-4285F4?style=flat-square&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Deepgram-Nova--2-13EF93?style=flat-square&logo=deepgram&logoColor=white" />
  <img src="https://img.shields.io/badge/NVIDIA-Llama--3.1-76B900?style=flat-square&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/WebSocket-Live-orange?style=flat-square&logo=socketdotio&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" />
</p>

---

## 📽️ Demo

<!-- ╔══════════════════════════════════════════════════════════════════╗ -->
<!-- ║  HOW TO ADD YOUR DEMO VIDEO                                     ║ -->
<!-- ║                                                                  ║ -->
<!-- ║  Option 1 — Embedded Video (MP4/WebM):                          ║ -->
<!-- ║    Replace the placeholder below with:                           ║ -->
<!-- ║                                                                  ║ -->
<!-- ║    <video src="demo.mp4" controls width="100%"></video>          ║ -->
<!-- ║                                                                  ║ -->
<!-- ║  Option 2 — YouTube / Google Drive Link:                        ║ -->
<!-- ║    Replace the placeholder below with:                           ║ -->
<!-- ║                                                                  ║ -->
<!-- ║    [![Demo Video](https://img.youtube.com/vi/VIDEO_ID/0.jpg)]   ║ -->
<!-- ║    (https://www.youtube.com/watch?v=VIDEO_ID)                    ║ -->
<!-- ║                                                                  ║ -->
<!-- ║  Option 3 — GIF Preview:                                        ║ -->
<!-- ║    ![SpeakEasy Demo](demo.gif)                                 ║ -->
<!-- ╚══════════════════════════════════════════════════════════════════╝ -->

<p align="center">

  <!-- 🔽 REPLACE THIS BLOCK WITH YOUR ACTUAL DEMO VIDEO / GIF 🔽 -->

  <img src="https://via.placeholder.com/800x450/1a1a2e/16c79a?text=🎬+Demo+Video+Coming+Soon" alt="Demo Placeholder" width="80%"/>

  <!-- 🔼 REPLACE THIS BLOCK WITH YOUR ACTUAL DEMO VIDEO / GIF 🔼 -->

</p>

<p align="center"><i>⬆️ Replace this placeholder with your recorded demo (see comments above for instructions)</i></p>

---

## 🧐 What is SpeakEasy?

**SpeakEasy** is a real-time AI coaching platform that turns your browser into a professional-grade speaking lab. Whether you're rehearsing a keynote, practicing for a job interview, or simply trying to become a more confident speaker — SpeakEasy watches, listens, and coaches you silently in the background.

No downloads. No installations. Just open the browser, hit **Start**, and begin speaking.

### How It Works (High Level)

```
┌─────────────┐    WebSocket     ┌──────────────────────────────────────────┐
│   Browser    │ ◄══════════════►│            FastAPI Backend               │
│  (Camera +   │   Video frames  │                                          │
│   Mic feed)  │   Audio chunks  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│              │   ◄──────────── │  │  Visual   │ │  Audio   │ │  Fusion  │ │
│  Live Dashboard  JSON state    │  │ Pipeline  │ │ Pipeline │ │  Layer   │ │
│  (scores,    │                 │  │(MediaPipe)│ │(Deepgram)│ │ (Llama)  │ │
│   feedback)  │                 │  └──────────┘ └──────────┘ └──────────┘ │
└─────────────┘                  └──────────────────────────────────────────┘
```

1. **You speak** into your webcam & mic — the browser streams video frames and audio chunks over a WebSocket.
2. **Three AI pipelines** run in parallel on the server:
   - 👁️ **Visual Pipeline** — MediaPipe analyzes your face, eyes, posture, and hand gestures every frame.
   - 🎤 **Audio Pipeline** — Deepgram Nova-2 transcribes your speech in real-time with filler-word detection.
   - 🧠 **Fusion Layer** — NVIDIA Llama 3.1 scores how relevant your speech is to your chosen topic.
3. **The dashboard updates live** at 10 Hz, showing you exactly what to improve — right now.

---

## ✨ Features at a Glance

### 🎤 Presentation Mode

| Feature | Description |
|:---|:---|
| **Live Transcription** | Your speech is transcribed word-by-word using Deepgram Nova-2, with smart punctuation and formatting. |
| **Topic Relevance Scoring** | Type your slide topic and the AI grades (0–100%) how well your speech aligns — powered by NVIDIA Llama 3.1. |
| **Filler Word Detection** | Detects `um`, `uh`, `like`, `you know`, `basically`, and 10+ other filler patterns. Shows count and percentage. |
| **Words-Per-Minute (WPM)** | Live speaking pace tracking. Ideal range: 120–150 WPM for presentations. |
| **Long Pause Alerts** | Detects uncomfortable silences longer than 2 seconds. Counts and timestamps them. |
| **Audio Level Meter** | Visual microphone input level so you know if you're speaking too softly. |

### 👁️ Body Language Analysis

| Feature | Description |
|:---|:---|
| **Eye Contact Tracking** | Uses 478-point FaceMesh to detect iris position relative to eye corners. Tells you if you're looking at the camera or away. |
| **Eye Contact Percentage** | Rolling window average of how often you maintain eye contact during the session. |
| **Posture Detection** | Checks shoulder alignment, head-forward slouching, lateral leaning, and body centering using BlazePose skeleton tracking. |
| **Posture Score** | A 0–100 posture score updated every frame with specific issue callouts (e.g., "Uneven shoulders", "Leaning to side"). |
| **Face Orientation** | Tracks pitch, yaw, and roll angles of your head to determine if you're facing the camera. |
| **Hand Gesture Analysis** | Detects hand visibility, position (raised vs. at sides), and movement intensity. Classifies gestures like "Both hands raised (Enthusiastic!)". |

### 💼 Interview Mode

| Step | What Happens |
|:---|:---|
| **1. Upload Resume** | Upload your resume as PDF, DOCX, or plain text. |
| **2. AI Generates Questions** | NVIDIA Llama 3.1 reads your resume and creates 5 tailored, challenging interview questions based on your skills and experience. |
| **3. Answer Out Loud** | Speak your answer naturally — your voice is transcribed live. |
| **4. Get AI Feedback** | For each answer, the AI provides structured coaching: |
| | → **Growth Area** — What to improve in your answer |
| | → **Missing Points** — Key things you forgot to mention |
| | → **Better Version** — A model ideal answer for reference |
| | → **Follow-up Questions** — What an interviewer might ask next |

### 🎙️ Session Recordings & History

| Feature | Description |
|:---|:---|
| **Auto-Save** | Every session is automatically recorded as a WAV file when you hit Stop. |
| **Browser Recording** | Record your webcam video directly from the browser (WebM/MP4). Upload it to the server for archival. |
| **Retroactive Analysis** | Upload any past recording and get a full analysis: transcript, filler count, WPM, and topic relevance score. |
| **Session History** | All sessions are logged to a local SQLite database with scores, duration, and type. View past performance over time. |
| **Rename & Delete** | Manage your recordings from the dashboard — rename for clarity or delete old sessions. |

### 🔐 API Access (For Organizations)

| Feature | Description |
|:---|:---|
| **API Key Management** | Generate API keys for external integrations. Keys are tied to a company name and track usage. |
| **REST Endpoint** | `POST /api/analyze` returns a JSON snapshot of the current session metrics (speech, posture, relevance). |
| **Bearer Auth** | Standard `Authorization: Bearer <key>` authentication for secure programmatic access. |

---

## 🏗️ Architecture & Technology

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BROWSER (Frontend)                        │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │ getUserMedia │  │  MediaRecorder│  │  WebSocket Client│  │
│   │ (cam + mic) │  │  (recording) │  │  (bidirectional) │  │
│   └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘  │
│          │                │                    │             │
│          └───── Video frames + Audio chunks ───┘             │
│                           │                                  │
│   ┌───────────────────────┴──────────────────────────────┐  │
│   │         Live Dashboard (HTML/CSS/JS)                  │  │
│   │   Scores • Transcript • Gauges • Feedback Cards      │  │
│   └──────────────────────────────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────┘
                               │ WebSocket (ws://)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   FASTAPI SERVER (Backend)                    │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Visual Pipeline│  │ Audio Pipeline │  │ Fusion Layer  │  │
│  │                │  │                │  │               │  │
│  │ • MediaPipe    │  │ • Deepgram     │  │ • NVIDIA      │  │
│  │   FaceMesh     │  │   Nova-2 API   │  │   Llama 3.1   │  │
│  │   (478 pts)    │  │ • Filler word  │  │ • Semantic     │  │
│  │ • BlazePose    │  │   detection    │  │   relevance   │  │
│  │   (33 joints)  │  │ • WPM calc     │  │   scoring     │  │
│  │ • Hand Tracker │  │ • Pause detect │  │ • TF-IDF      │  │
│  │   (21 pts/hand)│  │ • WAV export   │  │   fallback    │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │   SharedState (Thread-safe data store)                │    │
│  │   Synchronizes all pipelines at 10 Hz broadcast rate  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │  SQLite DB │  │  Recordings  │  │  REST API + Auth    │  │
│  │  (history) │  │  (WAV/WebM)  │  │  (API key mgmt)    │  │
│  └────────────┘  └──────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                        │               │
                        ▼               ▼
              ┌─────────────┐  ┌──────────────┐
              │  Deepgram   │  │  NVIDIA NIM  │
              │  Cloud API  │  │  Cloud API   │
              └─────────────┘  └──────────────┘
```

### Technology Stack

| Layer | Technology | Role |
|:---|:---|:---|
| **Backend Framework** | FastAPI + Uvicorn | Async HTTP + WebSocket server with automatic OpenAPI docs |
| **Speech-to-Text** | Deepgram Nova-2 | Cloud-based live audio transcription with filler word detection |
| **Relevance Scoring** | NVIDIA Llama-3.1-70B-Instruct | Grades speech-to-topic alignment via NIM API |
| **Interview Coaching** | NVIDIA Llama-3.1-70B-Instruct | Generates resume-based questions and structured answer feedback |
| **Face Analysis** | MediaPipe FaceMesh | 478 facial landmarks for eye contact and gaze direction |
| **Pose Estimation** | MediaPipe BlazePose | 33 skeletal joint tracking for posture and body centering |
| **Hand Tracking** | MediaPipe Hands | 21 landmarks per hand for gesture classification |
| **Embeddings (Fallback)** | NVIDIA Llama-3.2-NV-EmbedQA-1B | Semantic embeddings with local TF-IDF cosine fallback |
| **Database** | SQLite | Lightweight session history persistence |
| **Frontend** | Vanilla HTML / CSS / JavaScript | WebSocket-powered real-time dashboard |
| **Deployment** | Render.com | One-click cloud deployment via `render.yaml` blueprint |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10** or higher
- A **webcam** and **microphone**
- API keys:
  - 🔑 [Deepgram](https://deepgram.com) — for speech-to-text (free tier available)
  - 🔑 [NVIDIA NIM](https://build.nvidia.com) — for LLM relevance scoring (free tier available)

### 1. Clone the Repository

```bash
git clone https://github.com/yourname/SpeakEasy.git
cd SpeakEasy
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Your API Keys

**Windows (Command Prompt):**
```cmd
set NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
set DEEPGRAM_API_KEY=your_deepgram_key_here
```

**Windows (PowerShell):**
```powershell
$env:NVIDIA_API_KEY = "nvapi-xxxxxxxxxxxxxxxxxxxx"
$env:DEEPGRAM_API_KEY = "your_deepgram_key_here"
```

**Linux / macOS:**
```bash
export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
export DEEPGRAM_API_KEY=your_deepgram_key_here
```

### 4. Run the Server

```bash
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

### 5. Open the App

Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.

> **Note:** Grant camera and microphone permissions when prompted. SpeakEasy needs both to function.

---

## ☁️ Cloud Deployment (Render.com)

SpeakEasy ships with a `render.yaml` blueprint for one-click deployment:

1. Push your code to a GitHub repository.
2. Log into [Render.com](https://render.com) → **New** → **Blueprint**.
3. Connect your GitHub repo — Render auto-detects the configuration.
4. Add `NVIDIA_API_KEY` and `DEEPGRAM_API_KEY` as **Environment Variables** in the Render dashboard.
5. Click **Deploy** — your app goes live with full HTTPS and camera/mic support.

---

## 📂 Project Structure

```
SpeakEasy/
├── backend/
│   ├── server.py              # FastAPI app — routes, WebSocket, REST API
│   ├── visual_pipeline.py     # MediaPipe face/pose/hand analysis
│   ├── audio_pipeline.py      # Deepgram transcription + filler detection
│   ├── fusion_layer.py        # NVIDIA LLM relevance scoring + shared state
│   └── config.py              # All tunable parameters in one place
├── frontend/
│   ├── index.html             # Main dashboard page
│   ├── style.css              # UI styling
│   └── app.js                 # WebSocket client + dashboard logic
├── recordings/                # Auto-saved session recordings (WAV/WebM)
├── requirements.txt           # Python dependencies
├── render.yaml                # Render.com deployment blueprint
├── runtime.txt                # Python version for cloud deployment
├── synthspeak.db              # SQLite session history database
└── README.md                  # You are here
```

---

## ⚙️ Configuration

All pipeline parameters are centralized in [`config.py`](backend/config.py). You can fine-tune:

| Category | Examples |
|:---|:---|
| **Camera** | Resolution (1280×720), FPS (30), camera index |
| **Pose Detection** | Model complexity (0=lite, 1=full, 2=heavy), confidence thresholds |
| **Audio** | Sample rate (16kHz), chunk duration, silence threshold |
| **Relevance** | Similarity threshold (default 0.4 = 40%), embedding cache size |
| **UI** | Window dimensions, font scales, overlay transparency |

### Performance Presets

Choose a preset based on your hardware:

```python
from backend.config import apply_preset

apply_preset('high_accuracy')     # Best quality, slower (strong GPU/CPU)
apply_preset('balanced')          # Default — good balance
apply_preset('high_performance')  # Fastest, lower accuracy (weak hardware)
```

---

## 🛠️ API Reference

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/` | Serve the main dashboard |
| `GET` | `/health` | Health check (used by Render) |
| `POST` | `/start` | Start all AI pipelines |
| `POST` | `/stop` | Stop all AI pipelines |
| `POST` | `/manual` | Set a manual topic `{ "topic": "..." }` |
| `POST` | `/reset` | Reset the current topic |
| `GET` | `/status` | Current session status |
| `GET` | `/recordings` | List all saved recordings |
| `POST` | `/recordings/upload` | Upload a browser recording |
| `POST` | `/analyze-upload` | Retroactive analysis of a recording |
| `POST` | `/api/generate-questions-from-resume` | Generate interview questions from resume |
| `POST` | `/interview/feedback` | Get AI feedback on an interview answer |
| `POST` | `/api/keys` | Create an API key |
| `GET` | `/api/keys` | List all API keys |
| `POST` | `/api/analyze` | External analysis endpoint (Bearer auth) |
| `WebSocket` | `/ws/stream` | Real-time video + audio streaming |

---

## 📊 What SpeakEasy Measures

| Dimension | Metrics | How |
|:---|:---|:---|
| **Speech Content** | Topic relevance (0–100%), on/off-topic alerts | NVIDIA Llama 3.1 LLM grading |
| **Speech Quality** | Filler word count & %, WPM, long pause count, pause duration | Deepgram Nova-2 + custom analysis |
| **Eye Contact** | Looking at camera (yes/no), direction, contact percentage | MediaPipe FaceMesh iris tracking |
| **Posture** | Score (0–100), specific issues (slouching, leaning, off-center) | MediaPipe BlazePose skeleton |
| **Hand Gestures** | Gesture type, movement intensity, hand position | MediaPipe Hands tracking |
| **Face Orientation** | Pitch, yaw, roll angles; facing camera detection | FaceMesh 3D landmark geometry |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to open an issue or submit a pull request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with ❤️ using FastAPI • MediaPipe • Deepgram • NVIDIA NIM</b><br/>
  <sub>SpeakEasy — Because great speakers aren't born, they're coached.</sub>
</p>
