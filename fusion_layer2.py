"""
Fusion Layer - The "Brain" of SynthSpeak
Synchronizes visual and audio streams and calculates semantic relevance.
Embedding backend: NVIDIA Llama-3.2-NV-EmbedQA-1B-v2 via REST API
(falls back to local SBERT if API key is unavailable).
"""

import threading
import time
import numpy as np
from scipy.spatial.distance import cosine

# ── NVIDIA embedding API ────────────────────────────────────────────────────
# Reads key from env var NVIDIA_API_KEY (set before launching server.py)
import os

NVIDIA_API_KEY  = os.environ.get("NVIDIA_API_KEY", "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")
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_MODEL    = "nvidia/llama-3.2-nv-embedqa-1b-v2"



class SharedState:
    """
    Thread-safe shared state for cross-pipeline communication
    CRITICAL: Now includes topic confirmation state
    """
    
    def __init__(self):
        """Initialize shared state with thread locks"""
        self.lock = threading.Lock()
        
        # Visual pipeline data
        self.current_slide_topic = ""
        self.slide_topic_timestamp = 0
        self.pose_landmarks = None
        self.video_frame = None
        
        # Audio pipeline data
        self.current_transcription = ""
        self.latest_transcription = ""
        self.transcription_timestamp = 0
        
        # Speech quality metrics
        self.filler_word_count = 0
        self.total_word_count = 0
        self.filler_percentage = 0.0
        self.long_pause_count = 0
        self.last_pause_duration = 0.0
        self.wpm = 0.0
        self.audio_level: float = 0.0   # live RMS (0.0 – 1.0)
        
        # Fusion results
        self.similarity_score = 0.0
        self.is_on_topic = True
        self.relevance_status = "Waiting for topic..."
        
        # Mode control
        self.mode = "auto"  # "auto" or "manual"
        self.manual_topic = ""
        
        # CRITICAL: Topic confirmation state
        self.topic_confirmed = False  # Whether topic is locked and confirmed
        self.confirmed_topic = ""  # The locked topic string
        
        # Gesture analysis data (NEW)
        self.gesture_analysis = {
            'has_eye_contact': True,
            'eye_contact_direction': 'Unknown',
            'eye_contact_percentage': 0.0,
            'good_posture': True,
            'posture_score': 100,
            'posture_issues': [],
            'face_orientation': 'Unknown',
            'face_angles': {'pitch': 0, 'yaw': 0, 'roll': 0},
            'hand_gesture': 'No hands visible',
            'hand_movement': 0.0
        }
        
        # Application control
        self.running = True

    def reset_session(self):
        """Clear accumulated data for a new session"""
        with self.lock:
            self.current_transcription = ""
            self.latest_transcription = ""
            self.filler_word_count = 0
            self.total_word_count = 0
            self.filler_percentage = 0.0
            self.long_pause_count = 0
            self.last_pause_duration = 0.0
            self.wpm = 0.0
            self.audio_level = 0.0
            self.topic_confirmed = False
            self.confirmed_topic = ""
            self.gesture_analysis = {
                'has_eye_contact': True,
                'eye_contact_direction': 'Unknown',
                'eye_contact_percentage': 0.0,
                'good_posture': True,
                'posture_score': 100,
                'posture_issues': [],
                'face_orientation': 'Unknown',
                'face_angles': {'pitch': 0, 'yaw': 0, 'roll': 0},
                'hand_gesture': 'No hands visible',
                'hand_movement': 0.0
            }
    
    def update_slide_topic(self, topic):
        """Update the current slide topic (from OCR)"""
        with self.lock:
            self.current_slide_topic = topic
            self.slide_topic_timestamp = time.time()
            # Also update confirmed topic
            self.confirmed_topic = topic
    
    def set_topic_confirmed(self, confirmed):
        """
        Set topic confirmation status
        CRITICAL: Controls when audio relevance analysis runs
        """
        with self.lock:
            self.topic_confirmed = confirmed
            if confirmed:
                self.confirmed_topic = self.current_slide_topic
            else:
                self.confirmed_topic = ""
                self.relevance_status = "Waiting for topic confirmation..."
    
    def update_transcription(self, text, latest=""):
        """Update the current speech transcription"""
        with self.lock:
            self.current_transcription = text
            if latest:
                self.latest_transcription = latest
            self.transcription_timestamp = time.time()
    
    def update_speech_metrics(self, filler_count, total_words, long_pause_count, pause_duration, wpm):
        """Update speech quality metrics"""
        with self.lock:
            self.filler_word_count = filler_count
            self.total_word_count = total_words
            self.filler_percentage = (filler_count / total_words * 100) if total_words > 0 else 0.0
            self.long_pause_count = long_pause_count
            self.last_pause_duration = pause_duration
            self.wpm = wpm
    
    def update_audio_level(self, level: float):
        """Update the live microphone RMS level (0.0 – 1.0 scale)."""
        with self.lock:
            # Normalise: typical speech RMS is ~0.02-0.15, map to 0-1 range
            self.audio_level = min(1.0, level * 8.0)

    def update_pose(self, landmarks):
        """Update pose landmarks"""
        with self.lock:
            self.pose_landmarks = landmarks
    
    def update_gesture_analysis(self, analysis):
        """Update gesture analysis results"""
        with self.lock:
            self.gesture_analysis = analysis
    
    def update_video_frame(self, frame):
        """Update the current video frame"""
        with self.lock:
            self.video_frame = frame.copy() if frame is not None else None
    
    def update_similarity(self, score, is_on_topic, status):
        """Update similarity calculation results"""
        with self.lock:
            self.similarity_score = score
            self.is_on_topic = is_on_topic
            self.relevance_status = status
    
    def set_mode(self, mode):
        """Set operating mode (auto/manual)"""
        with self.lock:
            self.mode = mode
    
    def set_manual_topic(self, topic):
        """Set manual topic override"""
        with self.lock:
            self.manual_topic = topic
            self.current_slide_topic = topic
            self.confirmed_topic = topic
    
    def get_all_data(self):
        """Get a snapshot of all data (thread-safe)"""
        with self.lock:
            return {
                'slide_topic': self.current_slide_topic,
                'transcription': self.current_transcription,
                'latest_transcription': self.latest_transcription,
                'similarity': self.similarity_score,
                'is_on_topic': self.is_on_topic,
                'status': self.relevance_status,
                'mode': self.mode,
                'manual_topic': self.manual_topic,
                'pose_landmarks': self.pose_landmarks,
                'video_frame': self.video_frame.copy() if self.video_frame is not None else None,
                'filler_word_count': self.filler_word_count,
                'total_word_count': self.total_word_count,
                'filler_percentage': self.filler_percentage,
                'long_pause_count': self.long_pause_count,
                'last_pause_duration': self.last_pause_duration,
                'wpm': self.wpm,
                'audio_level': round(self.audio_level, 4),
                'topic_confirmed': self.topic_confirmed,  # CRITICAL
                'confirmed_topic': self.confirmed_topic,  # CRITICAL
                'gesture_analysis': self.gesture_analysis.copy()  # NEW
            }
    
    def get_active_topic(self):
        """
        Get the active topic for relevance analysis
        CRITICAL: Only returns topic if confirmed
        """
        with self.lock:
            if self.topic_confirmed:
                if self.mode == "manual" and self.manual_topic:
                    return self.manual_topic
                return self.confirmed_topic
            return ""
    
    def stop(self):
        """Signal all threads to stop"""
        with self.lock:
            self.running = False
    
    def is_running(self):
        """Check if application is running"""
        with self.lock:
            return self.running


class FusionLayer:
    """
    Fusion Layer – Combines visual and audio data to determine relevance.
    Embedding backend: NVIDIA Llama-3.2-NV-EmbedQA-1B-v2 via REST API.
    Falls back to lightweight TF-IDF cosine similarity when no API key is set.
    """

    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.running = False

        # Semantic similarity threshold
        self.SIMILARITY_THRESHOLD = 0.4

        # Decide backend at startup
        if NVIDIA_API_KEY:
            self._backend = "nvidia"
            print("🤖 Fusion backend: NVIDIA Llama-3.2-NV-EmbedQA-1B-v2")
            # Light dependency check — prefer httpx, fall back to requests
            try:
                import httpx
                self._http = httpx
                self._use_httpx = True
            except ImportError:
                import requests
                self._http = requests
                self._use_httpx = False
        else:
            self._backend = "tfidf"
            print("⚠️  NVIDIA_API_KEY not set — using TF-IDF cosine fallback.")
            print("    Set env var NVIDIA_API_KEY to enable the full model.")

        # Embedding cache (keyed by (text, input_type))
        self._embed_cache: dict = {}
        self._cache_lock = threading.Lock()

        # Change-detection
        self.last_topic = ""
        self.last_transcription = ""

        # Status tracking
        self.last_status_update: float = 0.0
        self.status_update_interval = 2.0

    # ── NVIDIA API embedding ─────────────────────────────────────────────────

    def _call_nvidia_api(self, text: str, input_type: str = "query") -> np.ndarray | None:
        """
        Call the NVIDIA embedding endpoint.
        input_type: "query" for live speech, "passage" for the slide topic.
        Returns a numpy float32 vector or None on error.
        """
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": NVIDIA_MODEL,
            "input": [text],
            "input_type": input_type,
            "encoding_format": "float",
            "truncate": "END",
        }
        try:
            if self._use_httpx:
                resp = self._http.post(
                    NVIDIA_EMBED_URL, headers=headers, json=payload, timeout=10.0
                )
                resp.raise_for_status()
                data = resp.json()
            else:
                resp = self._http.post(
                    NVIDIA_EMBED_URL, headers=headers, json=payload, timeout=10.0
                )
                resp.raise_for_status()
                data = resp.json()

            vec = data["data"][0]["embedding"]
            return np.array(vec, dtype=np.float32)
        except Exception as e:
            print(f"⚠️  NVIDIA API error: {e}")
            return None

    # ── TF-IDF fallback embedding ────────────────────────────────────────────

    @staticmethod
    def _tfidf_vector(text: str) -> np.ndarray:
        """
        Minimal bag-of-words TF-IDF vector (no external deps).
        Good enough as a keep-alive fallback when no API key is present.
        """
        import re
        from collections import Counter
        import math

        tokens = re.findall(r"[a-z]+", text.lower())
        if not tokens:
            return np.zeros(1, dtype=np.float32)

        tf = Counter(tokens)
        vocab = sorted(tf.keys())
        vec = np.array([tf[w] / len(tokens) for w in vocab], dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    # ── Public embedding interface ───────────────────────────────────────────

    def compute_embedding(
        self, text: str, input_type: str = "query"
    ) -> np.ndarray | None:
        """
        Return a unit embedding for *text*.
        * NVIDIA backend  →  calls Llama-3.2-NV-EmbedQA API
        * TF-IDF fallback →  local bag-of-words vector
        Results are cached per (text, input_type) pair.
        """
        if not text or len(text.strip()) < 3:
            return None

        key = (text.strip().lower(), input_type)

        with self._cache_lock:
            if key in self._embed_cache:
                return self._embed_cache[key]

        if self._backend == "nvidia":
            vec = self._call_nvidia_api(text.strip(), input_type)
        else:
            vec = self._tfidf_vector(text.strip())

        if vec is not None:
            with self._cache_lock:
                if len(self._embed_cache) > 200:
                    self._embed_cache.clear()
                self._embed_cache[key] = vec

        return vec

    # ── Similarity calculation ───────────────────────────────────────────────

    def calculate_similarity(
        self, topic: str, transcription: str
    ) -> tuple[float, bool, str]:
        """
        Calculate cosine similarity between slide topic and spoken text.
        Returns: (similarity_score, is_on_topic, status_message)
        """
        if not topic or len(topic.strip()) < 3:
            return 0.0, True, "⏳ Waiting for topic confirmation..."

        if not transcription or len(transcription.strip()) < 5:
            return 0.0, True, "🎤 Listening for speech..."

        # topic → passage embedding;  speech → query embedding
        topic_emb = self.compute_embedding(topic, input_type="passage")
        trans_emb = self.compute_embedding(transcription, input_type="query")

        if topic_emb is None or trans_emb is None:
            return 0.0, True, "⏳ Processing..."

        # Vectors may differ in length (TF-IDF fallback); pad if needed
        if topic_emb.shape != trans_emb.shape:
            max_len = max(len(topic_emb), len(trans_emb))
            topic_emb = np.pad(topic_emb, (0, max_len - len(topic_emb)))
            trans_emb = np.pad(trans_emb, (0, max_len - len(trans_emb)))

        similarity = float(max(0.0, min(1.0, 1.0 - cosine(topic_emb, trans_emb))))
        is_on_topic = similarity >= self.SIMILARITY_THRESHOLD

        if is_on_topic:
            status = f"✅ ON TOPIC ({similarity:.1%})"
        else:
            status = f"⚠️  OFF TOPIC ({similarity:.1%}) — Refocus on '{topic[:30]}…'"

        return similarity, is_on_topic, status

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        """Main fusion loop — runs in a separate thread."""
        self.running = True
        print("🧠 Fusion Layer started")
        print("⏸️  Relevance calculation starts AFTER topic confirmation")

        while self.shared_state.is_running() and self.running:
            try:
                data = self.shared_state.get_all_data()

                if not data.get("topic_confirmed", False):
                    current_time = time.time()
                    if current_time - self.last_status_update > self.status_update_interval:
                        self.shared_state.update_similarity(
                            0.0, True, "⏸️  Waiting for topic confirmation..."
                        )
                        self.last_status_update = current_time
                    time.sleep(0.5)
                    continue

                active_topic = self.shared_state.get_active_topic()
                transcription = data["transcription"]

                if active_topic != self.last_topic or transcription != self.last_transcription:
                    similarity, is_on_topic, status = self.calculate_similarity(
                        active_topic, transcription
                    )
                    self.shared_state.update_similarity(similarity, is_on_topic, status)
                    self.last_topic = active_topic
                    self.last_transcription = transcription

                    if transcription and len(transcription) > 10 and not is_on_topic:
                        print(f"\n⚠️  OFF-TOPIC ALERT!")
                        print(f"   Topic:      {active_topic}")
                        print(f"   Said:       {transcription[:80]}…")
                        print(f"   Similarity: {similarity:.1%}\n")

                time.sleep(0.1)

            except Exception as e:
                print(f"❌ Fusion Layer error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1.0)

        print("🛑 Fusion Layer stopped")

    def stop(self):
        self.running = False
