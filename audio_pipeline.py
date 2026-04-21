"""
SynthSpeak Audio Pipeline module.
This module receives audio chunks pushed from the browser via the /ws/stream
WebSocket endpoint. It buffers the stream and interacts with the Deepgram API
to provide speech-to-text transcription. It also analyzes speech for filler
words and pauses, and acts as a gatekeeper to only process audio when a valid
presentation topic is confirmed.
"""

import numpy as np
from scipy.io.wavfile import write as wav_write
import tempfile
import os
import time
import threading
import datetime
import requests
from pathlib import Path

# The Deepgram API key required for transcription services.
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "3e5f8214bf4e70d6de0c5ae89c2b23cff0d7b3d6")

# Directory used to archive all generated session recordings.
RECORDINGS_DIR = Path(__file__).parent / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)

class AudioPipeline:
    """
    Manages the live audio recording, chunking, and transcription workflow.
    Integrates with the application's shared state to synchronize audio 
    events (like speech pace, pauses, and fillers) with visual data.
    """

    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.running = False

        # Configured for Deepgram Nova-2 compatibility
        self.SAMPLE_RATE = 16000
        self.CHANNELS = 1
        self.CHUNK_DURATION = 8.0
        self.CHUNK_SAMPLES = int(self.SAMPLE_RATE * self.CHUNK_DURATION)

        # Thread-safe buffer for incoming audio chunks from the browser stream
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()

        # Temporary location for intermediary audio files during transcription
        self.temp_dir = tempfile.gettempdir()

        # Vocabulary used to detect hesitant speech patterns
        self.filler_words = [
            'um', 'uh', 'umm', 'uhh', 'like', 'you know',
            'sort of', 'kind of', 'basically', 'actually',
            'literally', 'well', 'so', 'i mean',
        ]
        self.filler_count = 0
        self.total_words = 0

        # State tracking for speech cadence and pause detection
        self.last_speech_time = time.time()
        self.pause_threshold = 2.0
        self.long_pauses = 0

        # Controls whether audio processing should pause based on the UI topic state
        self.is_processing_paused = False
        self.last_topic_check_time = 0
        self.topic_check_interval = 1.0

        # Cumulative audio and transcript data for the active recording session
        self.session_audio_chunks: list[np.ndarray] = []
        self.session_start_dt: datetime.datetime | None = None
        self.accumulated_transcription: str = ""
        self.last_saved_file: str | None = None

    def feed_audio_chunk(self, raw_bytes: bytes) -> None:
        """
        Entry point for browser-streamed audio.
        Converts the raw PCM float32 chunk to a numpy array and appends it to
        both the live processing buffer and the session recording accumulator.
        Topic enforcement is done in JS (Start is blocked without a topic), so
        we do NOT re-check topic_confirmed here — it would cause the first
        few seconds of every session to be silently dropped because reset_session()
        clears topic_confirmed and the `cmd: manual` arrives 500ms later.
        """
        try:
            arr = np.frombuffer(raw_bytes, dtype=np.float32).reshape(-1, 1)
            with self.buffer_lock:
                self.audio_buffer.append(arr)
                if self.running:
                    self.session_audio_chunks.append(arr.copy())
            audio_level = float(np.abs(arr).mean())
            self.shared_state.update_audio_level(audio_level)
        except Exception as e:
            print(f"⚠️  feed_audio_chunk error: {e}")

    def get_audio_chunk(self) -> np.ndarray | None:
        """
        Atomically retrieves and empties the accumulated audio from the buffer.
        """
        with self.buffer_lock:
            if not self.audio_buffer:
                return None
            data = np.concatenate(self.audio_buffer, axis=0)
            self.audio_buffer.clear()
            return data

    def save_audio_to_file(self, audio_data: np.ndarray, path: str) -> str:
        """
        Converts normalized float32 audio to 16-bit PCM and writes to disk.
        """
        # Ensure values stay strictly in the -1.0 to 1.0 bounds to prevent int16 overflow wrap-around (static)
        safe_audio = np.clip(audio_data, -1.0, 1.0)
        audio_int16 = (safe_audio * 32767).astype(np.int16)
        wav_write(path, self.SAMPLE_RATE, audio_int16)
        return path

    def save_session_recording(self):
        """
        Aggregates all buffered session chunks and exports them as a single WAV file.
        This enables playback in the Recordings UI after a session concludes.
        """
        if not self.session_audio_chunks:
            return None
        try:
            combined = np.concatenate(self.session_audio_chunks, axis=0)
            dt = self.session_start_dt or datetime.datetime.now()
            filename = f"session_{dt.strftime('%Y%m%d_%H%M%S')}.wav"
            out_path = RECORDINGS_DIR / filename
            
            self.save_audio_to_file(combined, str(out_path))
            print(f"💾 Session recording saved → {out_path}")
            
            self.session_audio_chunks.clear()
            self.accumulated_transcription = ""
            self.last_saved_file = str(out_path)
            
            return str(out_path)
        except Exception as e:
            print(f"⚠️  Could not save session recording: {e}")
            return None

    def _call_deepgram(self, audio_file: str, initial_prompt: str = ""):
        """
        Internal dispatcher for Deepgram's Nova-2 speech-to-text API.

        KEY FIX: Deepgram's `keywords` parameter must be passed as SEPARATE
        URL query parameters, one per word — NOT as a single joined string.
        e.g. "greenhouse effect" -> ?keywords=greenhouse:7&keywords=effect:7
        Using a list-of-tuples for `params` ensures requests encodes this correctly.
        A boost of 7 (on a 1-10 scale) strongly primes Nova-2 to prefer these
        exact words when the acoustic signal is ambiguous.
        """
        if not DEEPGRAM_API_KEY:
            print("⚠️  DEEPGRAM_API_KEY not set. Transcription disabled.")
            return None

        url = "https://api.deepgram.com/v1/listen"
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "audio/wav",
        }

        # Use a list of tuples — a plain dict cannot hold duplicate keys,
        # but Deepgram needs one `keywords=word:boost` entry per word.
        params = [
            ("model",        "nova-2"),
            ("language",     "en"),
            ("smart_format", "true"),
            ("punctuate",    "true"),
            ("filler_words", "true"),
        ]

        if initial_prompt:
            # Split the topic into individual tokens; skip very short stop-words
            stop = {"a", "an", "the", "of", "in", "on", "at", "to", "and",
                    "or", "is", "it", "for", "by", "as"}
            tokens = [
                w.strip(".,!?;:'\"").lower()
                for w in initial_prompt.split()
                if len(w.strip(".,!?;:'\"")) >= 3 and w.lower() not in stop
            ]
            # De-duplicate while preserving order
            seen = set()
            unique_tokens = [t for t in tokens if not (t in seen or seen.add(t))]
            for token in unique_tokens:
                params.append(("keywords", f"{token}:7"))
            print(f"🔑 Deepgram keyword hints: {unique_tokens}")

        try:
            with open(audio_file, "rb") as f:
                response = requests.post(url, headers=headers, params=params, data=f)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️  Deepgram API error: {e}")
            return None

    def transcribe_audio(self, audio_file: str, initial_prompt: str = "", use_vad: bool = False) -> str:
        """
        Initiates a Deepgram API request and extracts the raw textual transcript.
        """
        data = self._call_deepgram(audio_file, initial_prompt=initial_prompt)
        if data:
            try:
                return data["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
            except (KeyError, IndexError):
                pass
        return ""

    def transcribe_with_annotations(self, audio_file: str, initial_prompt: str = "", pause_threshold: float = 2.0):
        """
        Processes audio through Deepgram and calculates timing metadata.
        Interleaves pause markers into the transcript based on word-level timestamps 
        to visualize pacing in the frontend interface.
        """
        data = self._call_deepgram(audio_file, initial_prompt=initial_prompt)
        if not data:
            return "", "", 0

        try:
            alt = data["results"]["channels"][0]["alternatives"][0]
            words = alt.get("words", [])
            
            if not words:
                txt = alt.get("transcript", "").strip()
                return txt, txt, 0

            plain_parts = []
            annotated_parts = []
            pause_count = 0
            prev_end = None

            for w in words:
                text = w.get("punctuated_word", w.get("word", "")).strip()
                if not text:
                    continue
                start = w.get("start", 0.0)
                
                if prev_end is not None:
                    gap = start - prev_end
                    if gap >= pause_threshold:
                        pause_s = round(gap)
                        annotated_parts.append(f"(pause {pause_s}s)")
                        pause_count += 1
                        
                plain_parts.append(text)
                annotated_parts.append(text)
                prev_end = w.get("end", start + 0.5)

            return " ".join(plain_parts), " ".join(annotated_parts), pause_count
            
        except (KeyError, IndexError) as e:
            print(f"⚠️  Transcription parse error: {e}")
            return "", "", 0

    def build_highlighted_transcript(self, annotated_transcript: str, filler_list: list) -> str:
        """
        Transforms the annotated text into styled HTML content for the dashboard.
        Highlights recognized filler words and formats pause boundaries.
        """
        if not annotated_transcript:
            return ""
        import re
        result = annotated_transcript
        
        result = re.sub(
            r'\(pause (\d+s)\)',
            r'<span class="pause-label">⏸ \1</span>',
            result
        )
        
        unique_fillers = sorted(set(filler_list), key=len, reverse=True)
        for filler in unique_fillers:
            pattern = re.compile(r'\b(' + re.escape(filler) + r')\b', re.IGNORECASE)
            result = pattern.sub(r'<mark class="filler-mark">\1</mark>', result)
            
        return result

    def detect_filler_words(self, transcription: str):
        """
        Analyzes a transcription chunk for common hesitations and filler phrases.
        Calculates frequency metrics utilized by the coaching feedback system.
        """
        if not transcription:
            return 0, [], 0
            
        text_lower = transcription.lower()
        words = text_lower.split()
        total = len(words)
        count, found = 0, []
        
        for phrase in ['you know', 'sort of', 'kind of', 'i mean']:
            n = text_lower.count(phrase)
            if n:
                count += n
                found.extend([phrase] * n)
                
        for word in words:
            w = word.strip('.,!?;:')
            if w in self.filler_words:
                count += 1
                found.append(w)
                
        return count, found, total

    def check_pause_duration(self):
        """
        Evaluates elapsed time since the last detected speech event.
        Returns a boolean indicating if the delay exceeds the configured threshold.
        """
        dur = time.time() - self.last_speech_time
        return dur > self.pause_threshold, dur

    def should_process_audio(self):
        """
        Determines if incoming audio should be transcribed and evaluated.
        Enforces a requirement that a presentation topic must be confirmed first
        to ensure relevance tracking functions accurately.
        """
        if self.is_processing_paused:
            return False, "⏸️  Audio analysis PAUSED"
            
        data = self.shared_state.get_all_data()
        
        if not data.get('topic_confirmed', False):
            return False, "⏸️  Waiting for topic confirmation…"
            
        topic = self.shared_state.get_active_topic()
        
        if not topic or len(topic.strip()) < 3:
            return False, "⏸️  No valid topic…"
            
        return True, "▶️  Processing audio"

    def pause_processing(self):
        """
        Temporarily halts speech evaluation. Often triggered during manual topic overrides.
        """
        self.is_processing_paused = True
        print("\n⏸️  AUDIO ANALYSIS PAUSED (manual topic entry)")

    def resume_processing(self):
        """
        Reactivates speech evaluation following an interruption or override.
        """
        self.is_processing_paused = False
        print("\n▶️  AUDIO ANALYSIS RESUMED")

    def reset_session(self):
        """
        Flushes cumulative data to prepare the pipeline for a new recording.
        """
        self.accumulated_transcription = ""
        self.filler_count = 0
        self.total_words = 0
        self.long_pauses = 0
        self.last_speech_time = time.time()
        print("🔄 AudioPipeline session reset")

    def run(self):
        """
        Initialises the session and waits.
        Audio data now arrives via feed_audio_chunk() pushed by the
        /ws/stream WebSocket handler — there is no local mic capture.
        The thread stays alive so stop_pipelines() can join it cleanly;
        it exits as soon as self.running is cleared by stop().
        """
        self.running = True
        self.session_start_dt = datetime.datetime.now()
        self.session_audio_chunks.clear()
        self.last_saved_file = None

        print("🎧 Audio Pipeline started (browser-feed mode)")
        print("⏸️  Whole-session mode: transcription runs AFTER stop is pressed")

        try:
            while self.running:
                time.sleep(0.1)
        except Exception as e:
            print(f"❌ Audio Pipeline error: {e}")
            import traceback; traceback.print_exc()
        finally:
            self.save_session_recording()
            self.cleanup()

        print("🛑 Audio Pipeline stopped")

    def cleanup(self):
        """
        Purges any remaining data in the stream buffer and removes unneeded
        temporary files generated during external API transfers.
        """
        with self.buffer_lock:
            self.audio_buffer.clear()
            
        try:
            for f in os.listdir(self.temp_dir):
                if f.startswith("ss_audio_"):
                    os.remove(os.path.join(self.temp_dir, f))
        except Exception:
            pass

    def stop(self):
        """
        Signals the capture loop to terminate.
        The actual finalization and file exporting is handled by the loop's finally block
        to maintain thread-safe access to the buffer.
        """
        self.running = False