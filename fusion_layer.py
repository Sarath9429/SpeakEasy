"""
SynthSpeak Fusion Layer module.
This module acts as the central intelligence hub, synchronizing data 
from the visual and audio pipelines. It computes semantic similarity 
between the speaker's live transcription and the detected presentation 
slide topic using the NVIDIA Llama-3.2-NV-EmbedQA API (with a local 
TF-IDF fallback).
"""

import threading
import time
import numpy as np
from scipy.spatial.distance import cosine
import os

# Retrieves the NVIDIA API key from the environment for hardware-accelerated LLM embeddings.
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "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")
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "meta/llama-3.1-405b-instruct"

class SharedState:
    """
    Thread-safe data store facilitating communication between concurrent 
    pipelines (Audio, Visual, and Fusion). Maintains live metrics for 
    transcription, topic relevance, speech quality, and body language.
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # Visual data properties
        self.current_slide_topic = ""
        self.slide_topic_timestamp = 0
        self.pose_landmarks = None
        self.video_frame = None
        
        # Audio transcription properties
        self.current_transcription = ""
        self.latest_transcription = ""
        self.transcription_timestamp = 0
        
        # Speech cadence properties
        self.filler_word_count = 0
        self.total_word_count = 0
        self.filler_percentage = 0.0
        self.long_pause_count = 0
        self.last_pause_duration = 0.0
        self.wpm = 0.0
        self.annotated_transcript: str = ""
        self.highlighted_transcript: str = ""
        self.audio_level: float = 0.0
        
        # Cross-pipeline fusion outcomes
        self.similarity_score = 0.0
        self.is_on_topic = True
        self.relevance_status = "Waiting for topic..."
        
        # Application context and overrides
        self.mode = "auto"
        self.manual_topic = ""
        self.topic_confirmed = False
        self.confirmed_topic = ""
        
        # Captured behavioral analytics
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
        
        self.running = True

    def reset_session(self):
        """Purges accumulated session data."""
        with self.lock:
            self.current_transcription = ""
            self.latest_transcription = ""
            self.filler_word_count = 0
            self.total_word_count = 0
            self.filler_percentage = 0.0
            self.long_pause_count = 0
            self.last_pause_duration = 0.0
            self.wpm = 0.0
            self.annotated_transcript = ""
            self.highlighted_transcript = ""
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
        """Updates the OCR-detected topic string."""
        with self.lock:
            self.current_slide_topic = topic
            self.slide_topic_timestamp = time.time()
            self.confirmed_topic = topic

    def set_topic_confirmed(self, confirmed):
        """Locks the topic for subsequent relevance evaluation."""
        with self.lock:
            self.topic_confirmed = confirmed
            if confirmed:
                self.confirmed_topic = self.current_slide_topic
            else:
                self.confirmed_topic = ""
                self.relevance_status = "Waiting for topic confirmation..."

    def update_transcription(self, text, latest=""):
        """Commits the latest textual snippet from Deepgram."""
        with self.lock:
            self.current_transcription = text
            if latest:
                self.latest_transcription = latest
            self.transcription_timestamp = time.time()

    def update_speech_metrics(self, filler_count, total_words, long_pause_count, pause_duration, wpm):
        """Updates numeric indicators derived from user speech."""
        with self.lock:
            self.filler_word_count = filler_count
            self.total_word_count = total_words
            self.filler_percentage = (filler_count / total_words * 100) if total_words > 0 else 0.0
            self.long_pause_count = long_pause_count
            self.last_pause_duration = pause_duration
            self.wpm = wpm

    def set_annotated_transcripts(self, annotated: str, highlighted: str):
        """Saves versions of the text embedded with HTML highlight tags for pauses/fillers."""
        with self.lock:
            self.annotated_transcript = annotated
            self.highlighted_transcript = highlighted

    def update_audio_level(self, level: float):
        """Provides raw RMS microphone input values for the frontend visualizer."""
        with self.lock:
            self.audio_level = min(1.0, level * 8.0)

    def update_pose(self, landmarks):
        """Updates structural skeleton paths from MediaPipe."""
        with self.lock:
            self.pose_landmarks = landmarks

    def update_gesture_analysis(self, analysis):
        """Updates holistic body language metrics."""
        with self.lock:
            self.gesture_analysis = analysis

    def update_video_frame(self, frame):
        """Commits the latest camera frame image."""
        with self.lock:
            self.video_frame = frame.copy() if frame is not None else None

    def update_similarity(self, score, is_on_topic, status):
        """Registers the LLM-derived relevance alignment score."""
        with self.lock:
            self.similarity_score = score
            self.is_on_topic = is_on_topic
            self.relevance_status = status

    def set_mode(self, mode):
        """Toggles between internal control styles (auto vs manual)."""
        with self.lock:
            self.mode = mode

    def set_manual_topic(self, topic):
        """Overrides the visual detector with an explicit user phrase."""
        with self.lock:
            self.manual_topic = topic
            self.current_slide_topic = topic
            self.confirmed_topic = topic

    def get_all_data(self):
        """Safely extracts all live properties into a unified dictionary."""
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
                'topic_confirmed': self.topic_confirmed,
                'confirmed_topic': self.confirmed_topic,
                'gesture_analysis': self.gesture_analysis.copy()
            }

    def get_json_snapshot(self):
        """Builds a JSON-safe version of the application state by stripping binaries/complex objects."""
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
                'filler_word_count': self.filler_word_count,
                'total_word_count': self.total_word_count,
                'filler_percentage': self.filler_percentage,
                'long_pause_count': self.long_pause_count,
                'last_pause_duration': self.last_pause_duration,
                'wpm': self.wpm,
                'audio_level': round(self.audio_level, 4),
                'topic_confirmed': self.topic_confirmed,
                'confirmed_topic': self.confirmed_topic,
                'gesture_analysis': self.gesture_analysis.copy(),
                'annotated_transcript': self.annotated_transcript,
                'highlighted_transcript': self.highlighted_transcript,
            }

    def get_active_topic(self):
        """Resolves the currently active authoritative topic."""
        with self.lock:
            if self.topic_confirmed:
                if self.mode == "manual" and self.manual_topic:
                    return self.manual_topic
                return self.confirmed_topic
            return ""

    def stop(self):
        """Triggers thread loops to unwind."""
        with self.lock:
            self.running = False

    def is_running(self):
        """Exposes the application run loop constraint."""
        with self.lock:
            return self.running


class FusionLayer:
    """
    Evaluates real-time alignment between the speaker's vocalizations 
    and the visual context of the presentation. Dispatches scoring payloads
    to the UI backend.
    """

    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.running = False
        self.SIMILARITY_THRESHOLD = 0.4

        if NVIDIA_API_KEY:
            self._backend = "nvidia"
            print("🤖 Fusion backend: NVIDIA Llama-3.2-NV-EmbedQA-1B-v2")
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

        self._embed_cache: dict = {}
        self._cache_lock = threading.Lock()
        
        self.last_topic = ""
        self.last_transcription = ""
        
        self.last_status_update: float = 0.0
        self.status_update_interval = 2.0
        
        self._last_llm_eval: float = 0.0
        self._last_llm_score: float = 0.0

    def _call_nvidia_api(self, text: str, input_type: str = "query") -> np.ndarray | None:
        """Invokes the external API to map textual inputs into dense vector embeddings."""
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
                    NVIDIA_EMBED_URL, headers=headers, json=payload, timeout=30.0
                )
                resp.raise_for_status()
                data = resp.json()
            else:
                resp = self._http.post(
                    NVIDIA_EMBED_URL, headers=headers, json=payload, timeout=30.0
                )
                resp.raise_for_status()
                data = resp.json()

            vec = data["data"][0]["embedding"]
            return np.array(vec, dtype=np.float32)
        except Exception as e:
            print(f"⚠️  NVIDIA API error: {e}")
            return None

    @staticmethod
    def _tfidf_vector(text: str) -> np.ndarray:
        """A dependency-free term frequency generator used when cloud APIs are inaccessible."""
        import re
        from collections import Counter

        tokens = re.findall(r"[a-z]+", text.lower())
        if not tokens:
            return np.zeros(1, dtype=np.float32)

        tf = Counter(tokens)
        vocab = sorted(tf.keys())
        vec = np.array([tf[w] / len(tokens) for w in vocab], dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def compute_embedding(
        self, text: str, input_type: str = "query"
    ) -> np.ndarray | None:
        """Orchestrates embedding lookup, incorporating local caching to avoid redundant API trips."""
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

    def calculate_similarity(
        self, topic: str, transcription: str
    ) -> tuple[float, bool, str]:
        """
        Derives a strict relevance grade between the spoken text and the presentation context.
        Operates on an internal rate limit to avoid saturating external endpoints.
        """
        if not topic or len(topic.strip()) < 3:
            return 0.0, True, "⏳ Waiting for topic confirmation..."

        if not transcription or len(transcription.strip()) < 5:
            return 0.0, True, "🎤 Listening for speech..."

        similarity = 0.0

        if getattr(self, "_backend", "tfidf") == "nvidia":
            current_time = time.time()
            if current_time - self._last_llm_eval < 5.0:
                similarity = self._last_llm_score
            else:
                prompt = f"Topic: '{topic}'. The speaker has said: '{transcription}'. Grade how relevant their speech is to the topic from 0.00 to 1.00. Reply STRICTLY with a single float number like 0.85 and nothing else."
                
                headers = {
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                payload = {
                    "model": NVIDIA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 10,
                    "stream": False
                }
                try:
                    resp = self._http.post(
                        NVIDIA_EMBED_URL, headers=headers, json=payload, timeout=60.0
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    reply = data["choices"][0]["message"]["content"].strip()
                    import re
                    match = re.search(r"0\.\d+|1\.0|0", reply)
                    similarity = float(match.group()) if match else 0.5
                    self._last_llm_score = similarity
                    self._last_llm_eval = current_time
                except Exception as e:
                    # On timeout or network error — silently reuse the last score
                    err_str = str(e)
                    if "timeout" in err_str.lower() or "timed out" in err_str.lower():
                        print("⏱️  LLM relevance check timed out — reusing last score.")
                    else:
                        print(f"⚠️  LLM Eval error: {e}")
                    similarity = self._last_llm_score
        else:
            topic_emb = self.compute_embedding(topic, input_type="passage")
            trans_emb = self.compute_embedding(transcription, input_type="query")
            if topic_emb is not None and trans_emb is not None:
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

    def run(self):
        """
        Main orchestration loop enforcing the alignment checks synchronously 
        while delegating network calls where applicable.
        """
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
        """Terminates thread safety loops."""
        self.running = False
