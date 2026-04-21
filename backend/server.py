"""
SynthSpeak Backend Application Server.
Hosts the real-time WebSocket connection to the front-end dashboard, 
orchestrates the Audio, Visual, and Fusion pipelines, and manages 
the lifecycle of active training, presentation, and interview sessions.
"""

import asyncio
import base64
import json
import os
import secrets
import threading
import time
import traceback
import datetime
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .visual_pipeline import VisualPipeline
from .audio_pipeline import AudioPipeline
from .fusion_layer import FusionLayer, SharedState

import sqlite3

DB_FILE = "synthspeak.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS session_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            session_type TEXT,
            overall_score INTEGER,
            relevance_score INTEGER,
            speech_quality INTEGER,
            body_language INTEGER,
            duration INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

from pydantic import BaseModel
class SessionData(BaseModel):
    session_type: str
    overall_score: int
    relevance_score: int
    speech_quality: int
    body_language: int
    duration: int
app = FastAPI(title="SynthSpeak API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)
class AppState:
    """
    Manages the global state of all threaded AI pipelines. Facilitates 
    controlled starts, stops, and state extraction for dashboard synchronization.
    """

    def __init__(self):
        self.shared_state: SharedState | None = None
        self.visual_pipeline: VisualPipeline | None = None
        self.audio_pipeline: AudioPipeline | None = None
        self.fusion_layer: FusionLayer | None = None
        self.threads: list[threading.Thread] = []
        self.running = False
        self.lock = threading.Lock()

    def start_pipelines(self):
        """Initializes and anchors the Visual, Audio, and Fusion pipelines into parallel daemon threads."""
        with self.lock:
            if self.running:
                return  # already running

            print("🚀 Starting SynthSpeak pipelines...")

            self.shared_state = SharedState()
            self.visual_pipeline = VisualPipeline(self.shared_state)
            self.audio_pipeline = AudioPipeline(self.shared_state)
            self.fusion_layer = FusionLayer(self.shared_state)

            self.threads = []

            vt = threading.Thread(
                target=self.visual_pipeline.run, daemon=True, name="VisualPipeline"
            )
            at = threading.Thread(
                target=self.audio_pipeline.run, daemon=True, name="AudioPipeline"
            )
            ft = threading.Thread(
                target=self.fusion_layer.run, daemon=True, name="FusionLayer"
            )

            for t in (vt, at, ft):
                t.start()
                self.threads.append(t)

            self.running = True
            print("✅ All pipelines started")

    def stop_pipelines(self):
        """Gracefully stop all AI pipelines."""
        with self.lock:
            if not self.running:
                return

            print("🛑 Stopping SynthSpeak pipelines...")
            if self.shared_state:
                self.shared_state.stop()
            if self.visual_pipeline:
                self.visual_pipeline.stop()
            if self.audio_pipeline:
                self.audio_pipeline.stop()
            if self.fusion_layer:
                self.fusion_layer.stop()

            for t in self.threads:
                t.join(timeout=2.0)
            self.threads.clear()

            self.running = False
            print("✅ Pipelines stopped")

    def get_state_dict(self) -> dict:
        """Compiles a flat, JSON-serializable dictionary of all cross-pipeline metrics for the frontend."""
        if not (self.shared_state and self.running):
            return {"type": "state", "running": False}

        data = self.shared_state.get_all_data()
        data.pop("pose_landmarks", None)
        data.pop("video_frame", None)  # browser has live stream — no need to echo back
        gesture = data.pop("gesture_analysis", {})
        payload = {
            "type": "state",
            "running": self.running,
            "slide_topic": data.get("slide_topic", ""),
            "confirmed_topic": data.get("confirmed_topic", ""),
            "topic_confirmed": data.get("topic_confirmed", False),
            "transcription": data.get("transcription", ""),
            "latest_transcription": data.get("latest_transcription", ""),
            "similarity": round(data.get("similarity", 0.0), 4),
            "is_on_topic": data.get("is_on_topic", True),
            "status": data.get("status", ""),
            "mode": data.get("mode", "auto"),
            "filler_word_count": data.get("filler_word_count", 0),
            "total_word_count": data.get("total_word_count", 0),
            "filler_percentage": round(data.get("filler_percentage", 0.0), 2),
            "wpm": round(data.get("wpm", 0.0), 1),
            "long_pause_count": data.get("long_pause_count", 0),
            "last_pause_duration": round(data.get("last_pause_duration", 0.0), 2),
            "audio_level": round(data.get("audio_level", 0.0), 4),
            "pending_confirmation": bool(
                self.visual_pipeline and self.visual_pipeline.pending_confirmation
            ),
            "detected_topic": (
                self.visual_pipeline.detected_topic
                if self.visual_pipeline
                else ""
            ),
            "has_eye_contact": gesture.get("has_eye_contact", True),
            "eye_contact_direction": gesture.get("eye_contact_direction", "Unknown"),
            "eye_contact_percentage": round(
                gesture.get("eye_contact_percentage", 0.0), 1
            ),
            "good_posture": gesture.get("good_posture", True),
            "posture_score": round(gesture.get("posture_score", 100), 1),
            "posture_issues": gesture.get("posture_issues", []),
            "face_orientation": gesture.get("face_orientation", "Unknown"),
            "hand_gesture": gesture.get("hand_gesture", "No hands visible"),
            "hand_movement": round(gesture.get("hand_movement", 0.0), 2),
        }
        return payload

    def send_command(self, cmd: str, **kwargs):
        """Dispatch a command from the WebSocket to the correct pipeline method."""
        if not (self.running and self.visual_pipeline and self.audio_pipeline):
            return {"ok": False, "error": "Pipelines not running"}

        vp = self.visual_pipeline
        ap = self.audio_pipeline

        if cmd == "manual":
            topic = kwargs.get("topic", "").strip()
            if len(topic) < 3:
                return {"ok": False, "error": "Topic too short"}
            vp.set_manual_topic(topic)
            self.shared_state.set_mode("manual")
            ap.resume_processing()
            return {"ok": True, "msg": f"Manual topic set: {topic}"}

        elif cmd == "reset":
            vp.reset_topic()
            ap.pause_processing()
            return {"ok": True, "msg": "Topic reset"}

        elif cmd == "mode":
            mode = kwargs.get("mode", "auto")
            self.shared_state.set_mode(mode)
            return {"ok": True, "msg": f"Mode set to {mode}"}

        return {"ok": False, "error": f"Unknown command: {cmd}"}
app_state = AppState()
RECORDINGS_DIR = Path(__file__).parent / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)
API_KEYS_FILE = Path(__file__).parent / "api_keys.json"

def _load_api_keys() -> dict:
    if API_KEYS_FILE.exists():
        try:
            return json.loads(API_KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_api_keys(keys: dict):
    API_KEYS_FILE.write_text(json.dumps(keys, indent=2), encoding="utf-8")

API_KEYS: dict = _load_api_keys()  # { key_str: { company, created_at, usage_count } }
connected_clients: set[WebSocket] = set()
clients_lock = asyncio.Lock()
class _NumpyEncoder(json.JSONEncoder):
    """Convert numpy scalar/array types to native Python so json.dumps works."""
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
        if isinstance(obj, np.bool_): return bool(obj)
        return super().default(obj)
async def broadcast_loop():
    global connected_clients
    """
    Continuous background worker that polls the shared system state and 
    pushes near-instant telemetry (10 Hz) down to all active UI clients.
    """
    while True:
        await asyncio.sleep(0.10)  # 10 Hz

        if not connected_clients:
            continue

        try:
            payload = app_state.get_state_dict()
            message = json.dumps(payload, cls=_NumpyEncoder)
        except Exception as exc:
            print(f"⚠️  State serialisation error: {exc}")
            continue
        dead: set[WebSocket] = set()
        async with clients_lock:
            for ws in list(connected_clients):
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)

        if dead:
            async with clients_lock:
                connected_clients.difference_update(dead)   # in-place, avoids UnboundLocalError
@app.on_event("startup")
async def on_startup():
    """Start the background broadcaster when the server starts."""
    asyncio.create_task(broadcast_loop())
    print("📡 WebSocket broadcaster started")
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page."""
    html_path = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/style.css")
async def serve_css():
    return FileResponse(str(FRONTEND_DIR / "style.css"), media_type="text/css")


@app.get("/app.js")
async def serve_js():
    return FileResponse(
        str(FRONTEND_DIR / "app.js"), media_type="application/javascript"
    )

@app.post("/start")
async def start_session():
    """Start all AI pipelines."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, app_state.start_pipelines)
    return {"ok": True, "msg": "Pipelines started"}


@app.post("/stop")
async def stop_session():
    """Stop all AI pipelines."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, app_state.stop_pipelines)
    return {"ok": True, "msg": "Pipelines stopped"}


@app.post("/scan")
async def scan():
    return app_state.send_command("scan")


@app.post("/confirm")
async def confirm():
    return app_state.send_command("confirm")


@app.post("/rescan")
async def rescan():
    return app_state.send_command("rescan")


@app.post("/reset")
async def reset():
    return app_state.send_command("reset")


@app.post("/manual")
async def manual(body: dict):
    """Set a manual topic.  Body: { "topic": "..." }"""
    return app_state.send_command("manual", topic=body.get("topic", ""))


@app.post("/mode")
async def set_mode(body: dict):
    """Switch auto/manual mode.  Body: { "mode": "auto"|"manual" }"""
    return app_state.send_command("mode", mode=body.get("mode", "auto"))


@app.get("/status")
async def status():
    """Health-check / current running state."""
    return {
        "running": app_state.running,
        "clients": len(connected_clients),
    }
_MEDIA_GLOB = ["*.wav", "*.webm", "*.mp4", "*.ogg"]


def _collect_recordings():
    """Collect all media files from RECORDINGS_DIR sorted newest-first."""
    files = []
    for pat in _MEDIA_GLOB:
        for f in RECORDINGS_DIR.glob(pat):
            stat = f.stat()
            size_kb = round(stat.st_size / 1024, 1)
            if f.suffix == ".wav":
                try:
                    n_samples = (stat.st_size - 44) / 2
                    dur = round(n_samples / 16000, 1)
                except Exception:
                    dur = 0
            else:
                dur = 0  # browser recorded, no easy calc
            media_type = (
                "audio/wav"  if f.suffix == ".wav"  else
                "video/webm" if f.suffix == ".webm" else
                "video/mp4"  if f.suffix == ".mp4"  else
                "audio/ogg"
            )
            files.append({
                "filename" : f.name,
                "size_kb"  : size_kb,
                "duration_s": dur,
                "created_at": datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "url"      : f"/recordings/{f.name}",
                "media_type": media_type,
                "is_video" : f.suffix in (".webm", ".mp4"),
            })
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files


@app.get("/recordings")
async def list_recordings():
    """Return metadata for all saved recordings (WAV + WebM/MP4)."""
    return {"recordings": _collect_recordings()}


@app.get("/recordings/{filename}")
async def download_recording(filename: str):
    """Serve any recording file."""
    path = RECORDINGS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")
    suffixes = {".wav":"audio/wav", ".webm":"video/webm",
                ".mp4":"video/mp4", ".ogg":"audio/ogg"}
    media_type = suffixes.get(path.suffix, "application/octet-stream")
    return FileResponse(str(path), media_type=media_type, filename=filename)



@app.post("/recordings/upload")
async def upload_recording(file: UploadFile = File(...)):
    """
    Receive a recorded video/audio Blob from the browser MediaRecorder.
    The browser sends it as multipart/form-data with field name 'file'.
    """
    ext_map = {
        "video/webm"       : ".webm",
        "video/mp4"        : ".mp4",
        "audio/wav"        : ".wav",
        "audio/ogg"        : ".ogg",
        "audio/webm"       : ".webm",
        "audio/mpeg"       : ".mp3",
        "audio/mp3"        : ".mp3",
    }
    ext = ext_map.get(file.content_type or "", ".webm")
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{ts}{ext}"
    out = RECORDINGS_DIR / filename
    content = await file.read()
    out.write_bytes(content)
    size_kb = round(len(content) / 1024, 1)
    print(f"💾 Upload saved → {out.name} ({size_kb} KB)")
    return {"ok": True, "filename": filename, "size_kb": size_kb}


@app.post("/analyze-upload")
async def analyze_upload(file: UploadFile = File(...), topic: str = Form("")):
    """
    Offline/retroactive evaluation of a recording. Leverages the Deepgram 
    and Llama pipelines to grade speech pace, fillers, and topic relevance.
    """
    import tempfile, os
    ext_map = {
        "audio/wav":  ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3":  ".mp3",
        "audio/webm": ".webm",
        "video/webm": ".webm",
        "audio/ogg":  ".ogg",
    }
    ext = ext_map.get(file.content_type or "", ".wav")
    tmp_path = os.path.join(tempfile.gettempdir(), f"ss_upload_{int(time.time() * 1000)}{ext}")
    content  = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    try:
        from .audio_pipeline import AudioPipeline
        from .fusion_layer   import FusionLayer, SharedState
        ss   = SharedState()
        ap   = AudioPipeline(ss)
        fl   = FusionLayer(ss)
        transcript = ap.transcribe_audio(tmp_path, initial_prompt=topic)
        filler_count, filler_found, total_words = ap.detect_filler_words(transcript)
        filler_pct = round((filler_count / total_words * 100) if total_words > 0 else 0.0, 1)
        similarity  = 0.0
        is_on_topic = True
        if topic and len(topic.strip()) >= 3 and transcript:
            similarity, is_on_topic, _ = fl.calculate_similarity(topic, transcript)
        try:
            duration_s = len(content) / (16000 * 2)
        except Exception:
            duration_s = 60.0
        wpm = round((total_words / (duration_s / 60.0)) if duration_s > 1 else 0.0, 1)

        return {
            "ok": True,
            "transcript":    transcript,
            "similarity":    round(float(similarity), 4),
            "is_on_topic":   bool(is_on_topic),
            "filler_count":  filler_count,
            "filler_found":  filler_found[:20],   # cap list
            "filler_pct":    filler_pct,
            "total_words":   total_words,
            "wpm":           wpm,
            "duration_s":    round(duration_s, 1),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass





@app.patch("/recordings/{old_name}/{new_name}")
async def rename_recording(old_name: str, new_name: str):
    """Rename a recording file."""
    old = RECORDINGS_DIR / old_name
    if not old.exists():
        raise HTTPException(status_code=404, detail="Not found")
    stem = Path(new_name).stem or new_name.rstrip(".")
    new  = RECORDINGS_DIR / (stem + old.suffix)
    if new.exists() and new != old:
        raise HTTPException(status_code=409, detail="A file with that name already exists")
    old.rename(new)
    return {"ok": True, "new_filename": new.name}


@app.delete("/recordings/{filename}")
async def delete_recording(filename: str):
    """Delete a recording."""
    path = RECORDINGS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    path.unlink()
    return {"ok": True, "deleted": filename}
@app.post("/api/keys")
async def create_api_key(body: dict):
    """
    Generate a new API key.
    Body: { "company": "Acme Corp", "contact": "hr@acme.com" }
    """
    company = body.get("company", "").strip()
    contact = body.get("contact", "").strip()
    if not company:
        raise HTTPException(status_code=400, detail="company name required")
    key = "ss_" + secrets.token_urlsafe(32)
    API_KEYS[key] = {
        "company": company,
        "contact": contact,
        "created_at": datetime.datetime.now().isoformat(),
        "usage_count": 0,
    }
    _save_api_keys(API_KEYS)
    return {"api_key": key, "company": company}


@app.get("/api/keys")
async def list_api_keys():
    """List all issued API keys (admin view)."""
    return {
        "keys": [
            {"key": k, **v} for k, v in API_KEYS.items()
        ]
    }


@app.post("/api/analyze")
async def api_analyze(authorization: str = Header(None)):
    """
    Public-facing analysis endpoint for companies.
    Header:  Authorization: Bearer <api_key>
    Returns a JSON snapshot of the latest session metrics.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    key = authorization[len("Bearer "):].strip()
    if key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    API_KEYS[key]["usage_count"] += 1
    _save_api_keys(API_KEYS)

    if not app_state.running:
        return {"error": "No active session", "metrics": None}

    data = app_state.get_state_dict()
    data.pop("frame_b64", None)   # strip video frame
    data["api_key_company"] = API_KEYS[key]["company"]
    data["retrieved_at"] = datetime.datetime.now().isoformat()
    return {"metrics": data}


@app.post("/api/generate-questions-from-resume")
async def generate_questions_from_resume(file: UploadFile = File(None), text: str = Form(None)):
    """
    Takes an uploaded resume (PDF/DOCX) or raw text and generates tailored questions.
    """
    try:
        content = ""
        if text:
            content += text + "\n"
            
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext == ".pdf":
                try:
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(file.file)
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            content += page_text + "\n"
                except ImportError:
                    return {"ok": False, "error": "PyPDF2 is not installed on this server. Please paste text instead."}
                except Exception as e:
                    return {"ok": False, "error": f"Could not read PDF: {e}"}
            elif ext == ".docx":
                try:
                    import docx
                    doc = docx.Document(file.file)
                    for para in doc.paragraphs:
                        content += para.text + "\n"
                except ImportError:
                    return {"ok": False, "error": "python-docx is not installed on this server. Please paste text instead."}
                except Exception as e:
                    return {"ok": False, "error": f"Could not read DOCX: {e}"}
            elif ext == ".txt":
                content += (await file.read()).decode('utf-8')
            else:
                return {"ok": False, "error": "Unsupported file format. Please upload PDF, DOCX, or TXT."}

        content = content.strip()
        if not content or len(content) < 50:
            return {"ok": False, "error": "Could not extract sufficient text from resume."}
        prompt = (
            "You are an expert technical interviewer. Extract the candidate's experience, skills, "
            "and projects from the following resume text. Then, generate exactly 5 specific, "
            "challenging interview questions that test the claims and technologies mentioned. "
            "Return ONLY a valid JSON array of strings, with no additional text or formatting. "
            "Example: [\"Question 1?\", \"Question 2?\"]\n\n"
            f"Resume Text:\n{content[:5000]}"
        )

        from .fusion_layer import NVIDIA_API_KEY
        
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "top_p": 1,
            "max_tokens": 1024,
            "stream": False
        }

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            resp.raise_for_status()
            data = resp.json()

        reply = data["choices"][0]["message"]["content"].strip()
        import json
        
        if reply.startswith("```json"):
            reply = reply[7:]
        if reply.endswith("```"):
            reply = reply[:-3]
        if reply.startswith("```"):
            reply = reply[3:]
            
        try:
            questions = json.loads(reply.strip())
            if isinstance(questions, list) and len(questions) > 0:
                return {"ok": True, "questions": questions[:5]}
        except json.JSONDecodeError:
            pass
        lines = [line.strip() for line in reply.split("\n") if line.strip() and not line.strip().startswith("[") and not line.strip().endswith("]")]
        cleaned_questions = []
        import re
        for line in lines:
            m = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
            if m.startswith('"') and m.endswith('"'):
                m = m[1:-1]
            if len(m) > 10:
                cleaned_questions.append(m)
                if len(cleaned_questions) == 5:
                    break
                    
        if len(cleaned_questions) >= 3:
            return {"ok": True, "questions": cleaned_questions[:5]}
        
        return {"ok": False, "error": "LLM returned unparseable output.", "raw": reply}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}
class InterviewFeedbackRequest(BaseModel):
    question: str
    transcript: str
    interview_type: str = "general"

@app.post("/interview/feedback")
async def interview_feedback(req: InterviewFeedbackRequest):
    """
    Send the user's spoken answer to the LLM and get structured coaching feedback.
    Returns: growth_area, missing_points, better_version, followup_questions
    """
    try:
        if not req.transcript or len(req.transcript.strip()) < 10:
            return {"ok": False, "error": "Transcript too short to analyze."}

        from .fusion_layer import NVIDIA_API_KEY
        if not NVIDIA_API_KEY:
            return {"ok": False, "error": "No NVIDIA API key configured."}

        prompt = (
            f"You are an expert interview coach evaluating a candidate's answer.\n\n"
            f"Interview Type: {req.interview_type}\n"
            f"Question: {req.question}\n\n"
            f"Candidate's Answer:\n\"{req.transcript}\"\n\n"
            "Provide structured coaching feedback in the following JSON format ONLY. "
            "Return valid JSON with no extra text:\n"
            "{\n"
            '  "growth_area": "2-3 sentences on what to improve",\n'
            '  "missing_points": ["point 1 they should have mentioned", "point 2", "point 3"],\n'
            '  "better_version": "A concise ideal version of the answer in 3-4 sentences",\n'
            '  "followup_questions": ["follow-up Q 1?", "follow-up Q 2?", "follow-up Q 3?"]\n'
            "}"
        )

        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "top_p": 1,
            "max_tokens": 1024,
            "stream": False
        }

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            resp.raise_for_status()
            data = resp.json()

        reply = data["choices"][0]["message"]["content"].strip()
        import re as _re, json as _json
        reply = _re.sub(r'^```(?:json)?\s*', '', reply)
        reply = _re.sub(r'\s*```$', '', reply).strip()

        try:
            feedback = _json.loads(reply)
            return {"ok": True, "feedback": feedback}
        except _json.JSONDecodeError:
            return {"ok": False, "error": "LLM returned malformed JSON", "raw": reply}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}

@app.post("/api/sessions")
async def save_session(data: SessionData):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute('''
            INSERT INTO session_history (timestamp, session_type, overall_score, relevance_score, speech_quality, body_language, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            now, data.session_type, data.overall_score, data.relevance_score, data.speech_quality, data.body_language, data.duration
        ))
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/sessions")
async def get_sessions():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM session_history ORDER BY id DESC')
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}
@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """
    Streaming WebSocket — the browser pushes raw camera frames and audio here.

    Protocol: each binary message starts with a small JSON header terminated
    by a newline byte (\n), followed immediately by the raw payload bytes.

    Header examples:
        {"type":"frame"}\n<JPEG bytes>
        {"type":"audio"}\n<PCM float32 LE bytes>

    The server dispatches the payload to the appropriate pipeline method.
    """
    await ws.accept()
    print("📡 /ws/stream client connected")
    try:
        while True:
            data = await ws.receive_bytes()
            # Split header and payload at the first newline
            nl = data.find(b'\n')
            if nl == -1:
                continue
            try:
                header = json.loads(data[:nl].decode("utf-8"))
            except Exception:
                continue
            payload = data[nl + 1:]
            msg_type = header.get("type", "")
            if msg_type == "frame" and app_state.visual_pipeline:
                # Fire-and-forget — feed_frame's own _processing_frame flag
                # will drop the frame if MediaPipe is still busy with the last one.
                # Do NOT await: that would block receive_bytes() and cause a queue.
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, app_state.visual_pipeline.feed_frame, payload)
            elif msg_type == "audio" and app_state.audio_pipeline:
                # Audio is lightweight — await is fine (ensures ordering)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, app_state.audio_pipeline.feed_audio_chunk, payload)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"❌ /ws/stream error: {exc}")
    finally:
        print("📡 /ws/stream client disconnected")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Bidirectional WebSocket.

    Sends:  JSON state snapshots every 100 ms (via broadcaster)
    Receives: JSON command messages  { "cmd": "scan" | "confirm" | ... }
    """
    await ws.accept()
    async with clients_lock:
        connected_clients.add(ws)
    print(f"🔌 WebSocket client connected  (total: {len(connected_clients)})")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(
                    json.dumps({"type": "error", "error": "Invalid JSON"})
                )
                continue

            cmd = msg.get("cmd", "")
            if cmd == "start":
                loop = asyncio.get_event_loop()
                if app_state.shared_state:
                    app_state.shared_state.reset_session()
                if app_state.audio_pipeline:
                    app_state.audio_pipeline.reset_session()
                await loop.run_in_executor(None, app_state.start_pipelines)
                await ws.send_text(json.dumps({"type": "ack", "cmd": "start", "ok": True}))

            elif cmd == "stop":
                loop = asyncio.get_event_loop()
                await ws.send_text(json.dumps({"type": "status", "msg": "Transcribing entire session (this may take a moment)..."}))
                await loop.run_in_executor(None, app_state.stop_pipelines)
                def post_process_session():
                    import os
                    if app_state.audio_pipeline is None:
                        return
                    audio_file = getattr(app_state.audio_pipeline, 'last_saved_file', None)
                    if audio_file and os.path.exists(audio_file):
                        print(f"📝 Starting whole-session transcription on {audio_file}")
                        topic = app_state.shared_state.get_active_topic()
                        transcript, annotated, pause_count = app_state.audio_pipeline.transcribe_with_annotations(
                            audio_file, initial_prompt=topic, pause_threshold=2.0
                        )
                        
                        if transcript:
                            print(f"📄 Final Transcript: {transcript[:100]}…")
                            fc, ff, tw = app_state.audio_pipeline.detect_filler_words(transcript)
                            highlighted = app_state.audio_pipeline.build_highlighted_transcript(annotated, ff)
                            
                            sim, is_on = 0.0, True
                            status_msg = "No topic to compare"
                            if topic and app_state.fusion_layer:
                                sim, is_on, status_msg = app_state.fusion_layer.calculate_similarity(topic, transcript)
                                app_state.shared_state.update_similarity(sim, is_on, status_msg)
                            
                            try:
                                import wave
                                with wave.open(audio_file, 'rb') as w:
                                    duration_s = w.getnframes() / float(w.getframerate())
                            except Exception:
                                duration_s = 60.0
                            
                            wpm = (tw / (duration_s / 60.0)) if duration_s > 0 else 0.0
                            
                            app_state.shared_state.update_transcription(transcript, latest=transcript)
                            app_state.shared_state.update_speech_metrics(fc, tw, pause_count, 0.0, wpm)
                            app_state.shared_state.set_annotated_transcripts(annotated, highlighted)
                            print(f"✅ Final processing complete. WPM: {wpm:.1f}, Fillers: {fc}, Pauses: {pause_count}, Relevance: {sim:.2f}")
                        else:
                            print("⚠️  No speech detected in final session file.")
                await loop.run_in_executor(None, post_process_session)
                final_state = app_state.shared_state.get_json_snapshot()
                
                try:
                    await ws.send_text(json.dumps({"type": "snapshot", "data": final_state}))
                    await ws.send_text(json.dumps({"type": "ack", "cmd": "stop", "ok": True}))
                except RuntimeError:
                    pass  # client already closed

            else:
                result = app_state.send_command(cmd, **{k: v for k, v in msg.items() if k != "cmd"})
                result["type"] = "ack"
                result["cmd"] = cmd
                await ws.send_text(json.dumps(result))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"❌ WebSocket error: {exc}")
        traceback.print_exc()
    finally:
        async with clients_lock:
            connected_clients.discard(ws)
        print(f"🔌 WebSocket client disconnected  (total: {len(connected_clients)})")
class ConciseFeedbackRequest(BaseModel):
    transcript: str
    topic: str = ""

@app.post("/practice/conciseness")
async def practice_conciseness(req: ConciseFeedbackRequest):
    try:
        if not req.transcript or len(req.transcript.strip()) < 20:
            return {"ok": False, "error": "Transcript too short."}
        from .fusion_layer import NVIDIA_API_KEY
        if not NVIDIA_API_KEY:
            return {"ok": False, "error": "No API key configured."}
        topic_line = ("Topic: " + req.topic + "\n") if req.topic else ""
        prompt = (
            "You are an expert speech coach. Analyze the following spoken transcript "
            "and provide conciseness feedback.\n\n"
            + topic_line
            + "Transcript:\n\"" + req.transcript.strip() + "\"\n\n"
            + "Return ONLY this JSON, no extra text, no code fences:\n"
            + "{\"critique\":\"2-3 sentences on what made the speech verbose or unclear\","
            + "\"ideal_version\":\"A concise clear rewrite of the same ideas in 2-4 sentences\"}"
        )
        headers = {"Authorization": "Bearer " + NVIDIA_API_KEY, "Content-Type": "application/json"}
        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5, "max_tokens": 512, "stream": False
        }
        import httpx, re as _re, json as _json
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers, json=payload, timeout=30.0)
            resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        reply = _re.sub(r'^```(?:json)?\s*', '', reply)
        reply = _re.sub(r'\s*```$', '', reply).strip()
        try:
            return {"ok": True, "feedback": _json.loads(reply)}
        except Exception:
            return {"ok": False, "error": "Malformed JSON", "raw": reply}
    except Exception as e:
        return {"ok": False, "error": str(e)}
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════╗
║   SynthSpeak Backend Server                      ║
║   Open http://localhost:8000 in your browser     ║
╚══════════════════════════════════════════════════╝
""")
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,          # set True during development
        log_level="info",
    )
