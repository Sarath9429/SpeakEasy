# SynthSpeak — Cloud Deployment Migration Plan

## Background

SynthSpeak currently runs entirely on your local PC:
- **Camera** is opened via `cv2.VideoCapture(0)` in `visual_pipeline.py`
- **Microphone** is captured via `sounddevice` in `audio_pipeline.py`
- **MediaPipe** (posture, eye contact, hands) runs in Python on localhost

To deploy to a public URL, both the camera and microphone captures must move into the **user's browser** via JavaScript Web APIs. The Python backend becomes a pure AI/logic processor.

---

## Answer to Your MediaPipe Question

> **"Will video from the browser work with MediaPipe for posture detection?"**

**Yes — with a change in approach.** There are two valid strategies:

| Strategy | Where MediaPipe runs | Pros | Cons |
|---|---|---|---|
| **A: Browser → Python frames via WebSocket** | Python server (current approach) | No code rewrite of analysis logic | Server needs GPU/CPU, latency ~100-300ms |
| **B: MediaPipe in the Browser (JS)** | User's browser | Zero server load, real-time, free | Need to rewrite analysis in JS |

**Recommended: Strategy A** — The browser captures video frames using `getUserMedia`, encodes them as JPEG, and sends them over WebSocket to Python. Python runs the exact same MediaPipe code and sends back the results. This is the **least invasive** change to your existing code.

---

## Architecture After Migration

```
USER'S BROWSER
├── getUserMedia() → webcam video stream
├── Sends JPEG frames over WebSocket → Python
├── MediaRecorder API → captures audio chunks
├── Sends audio chunks over WebSocket → Python
└── Receives JSON telemetry back from Python (10 Hz)

PYTHON BACKEND (Cloud Server)
├── Receives frames → MediaPipe (posture, eye, hands) → SharedState
├── Receives audio → Deepgram API → transcription → SharedState
├── FusionLayer → NVIDIA embeddings → relevance score → SharedState
└── Broadcasts state JSON to all WebSocket clients (10 Hz)
```

---

## Changes Required

### 1. `audio_pipeline.py` — Remove sounddevice, add WebSocket audio receiver

#### [MODIFY] [audio_pipeline.py](file:///d:/SynthSpeak/audio_pipeline.py)
- **Remove** `sounddevice` (sd) import, `find_input_device()`, `audio_callback()`, the `sd.InputStream` context manager, and all local mic capture logic
- **Add** a new `feed_audio_chunk(raw_bytes)` method — called by the server when WebSocket delivers browser audio
- **Keep** all Deepgram API calls, filler word detection, pause analysis, session save logic unchanged

---

### 2. `visual_pipeline.py` — Remove cv2.VideoCapture, add frame receiver

#### [MODIFY] [visual_pipeline.py](file:///d:/SynthSpeak/visual_pipeline.py)
- **Remove** `initialize_camera()`, `cap.read()`, the main camera loop
- **Add** `feed_frame(jpeg_bytes)` method — decodes JPEG from browser and runs MediaPipe on it
- **Add** `feed_frame` runs `process_frame_with_analysis()` (already exists — no change needed there)
- **Keep** all MediaPipe gesture/posture analysis code unchanged

---

### 3. `server.py` — Add WebSocket handler for browser camera/audio streams

#### [MODIFY] [server.py](file:///d:/SynthSpeak/server.py)
- **Add** `/ws/stream` WebSocket endpoint — the browser connects here to push frames and audio
- The WebSocket receives binary messages: a small JSON header byte prefix tells the server if it is a `frame` or `audio` payload
- Calls `visual_pipeline.feed_frame()` or `audio_pipeline.feed_audio_chunk()` accordingly
- **Remove** the thread that starts `visual_pipeline.run()` (which no longer has its own camera loop)
- **Keep** the broadcast loop, all REST endpoints, DB, recordings, interview logic unchanged

---

### 4. `app.js` — Add browser camera capture + WebSocket streaming

#### [MODIFY] [app.js](file:///d:/SynthSpeak/app.js)
- **Add** `navigator.mediaDevices.getUserMedia({ video: true, audio: true })` when Start is pressed
- **Add** `ImageCapture` / `OffscreenCanvas` to grab a video frame every 100ms, encode as JPEG blob, and send over WebSocket to `/ws/stream`
- **Add** `AudioWorkletNode` or `ScriptProcessorNode` to capture raw PCM audio chunks and send over WebSocket
- **Remove** the display of `frame_b64` base64 video (since the browser now has the live stream directly — no need to echo it back)
- **Keep** all dashboard panels, topic management, session handling, recordings tab unchanged

---

### 5. `index.html` — Add `<video>` element for live webcam preview

#### [MODIFY] [index.html](file:///d:/SynthSpeak/index.html)
- **Add** a `<video id="localVideo" autoplay muted playsinline>` element
- Assign `stream` from `getUserMedia` to `localVideo.srcObject` so the user sees themselves
- **Remove** the `<img>` or `<canvas>` that was displaying the base64 server-echoed frame

---

### 6. Deployment — Render.com (Python backend) + Vercel (Frontend)

The project has a single-server design (`server.py` serves `index.html`, `app.js`, `style.css`). We can keep this structure and deploy **just the Python backend** to **Render.com** (free tier available).

#### New file: `render.yaml`
```yaml
services:
  - type: web
    name: synthspeak
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: NVIDIA_API_KEY
        sync: false   # set via Render dashboard
      - key: DEEPGRAM_API_KEY
        sync: false
```

#### New file: `requirements.txt`
All current dependencies pinned (mediapipe, fastapi, uvicorn, httpx, deepgram-sdk, opencv-python-headless, scipy, numpy, etc.)

> [!IMPORTANT]
> `opencv-python-headless` must be used instead of `opencv-python` on cloud servers (no display).

---

## Deployment Platform Recommendation

| Platform | Pros | Cost |
|---|---|---|
| **Render.com** | Easy Python deploy, free tier, WebSocket support | Free (sleeps after 15 min idle) |
| **Railway.app** | Always-on, fast deploys | ~$5/month |
| **Google Cloud Run** | Scales to zero, pay-per-use | Near-zero for low traffic |

**Recommended: Render.com** for initial deployment.

---

## Verification Plan

### Automated
- Run `python -c "import server"` locally before pushing to confirm no import errors
- Test WebSocket frame streaming with a browser test page

### Manual
1. Deploy to Render
2. Open the public URL on any device (phone, another PC)
3. Grant camera/mic permission in the browser
4. Click Start — verify live video appears, transcription works, posture scores update

---

## Open Questions

> [!IMPORTANT]
> **Audio format from browser:** The browser's `AudioWorklet` outputs raw PCM float32. Deepgram's REST API expects a WAV file. We need a small conversion buffer in the server that accumulates 8 seconds of audio chunks, writes a WAV, and sends to Deepgram — this mirrors what `audio_pipeline.py` currently does with sounddevice.

> [!NOTE]
> **Render.com free tier sleeps** after 15 minutes of inactivity. This means the first load takes ~30 seconds to "wake up." For a production/demo scenario, Railway ($5/mo) or Google Cloud Run is better.
