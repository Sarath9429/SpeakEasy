"""
SynthSpeak Configuration File
Customize all parameters here for easy tuning
"""

# ============================================================================
# VISUAL PIPELINE CONFIGURATION
# ============================================================================

VISUAL_CONFIG = {
    # Camera Settings
    'camera_index': 0,  # 0 for default webcam, 1 for external
    'frame_width': 1280,
    'frame_height': 720,
    'fps': 30,
    
    # MediaPipe Pose Settings
    'pose_detection_confidence': 0.7,  # 0.0 to 1.0 (higher = more strict)
    'pose_tracking_confidence': 0.7,   # 0.0 to 1.0
    'pose_model_complexity': 1,        # 0=lite, 1=full, 2=heavy
    
    # OCR Settings (Google Cloud Vision)
    'ocr_interval': 4.0,               # Seconds between OCR scans
    'ocr_roi_top_percentage': 0.35,    # Use top 35% of frame for slide titles
    'google_vision_max_results': 10,   # Max text annotations to process
    # NOTE: Set env var before running:
    #   set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\credentials.json
    #   Obtain key at: https://console.cloud.google.com/apis/credentials

    # Text Cleaning
    'min_topic_length': 3,             # Minimum characters for valid topic
}

# ============================================================================
# AUDIO PIPELINE CONFIGURATION
# ============================================================================

AUDIO_CONFIG = {
    # Audio Recording Settings
    'sample_rate': 16000,              # Hz (16kHz standard for Whisper)
    'channels': 1,                     # 1=mono, 2=stereo
    'chunk_duration': 5.0,             # Seconds per recording chunk
    'audio_block_size': 0.1,           # Seconds per audio block (100ms)
    
    # Whisper Model Settings
    'model_size': 'base',              # tiny, base, small, medium, large
    'device': 'cpu',                   # cpu or cuda
    'compute_type': 'int8',            # int8, int16, float16, float32
    'cpu_threads': 4,                  # Number of CPU threads
    'num_workers': 1,                  # Number of parallel workers
    
    # Transcription Settings
    'beam_size': 5,                    # Beam search size (higher = more accurate, slower)
    'language': 'en',                  # Language code (en, es, fr, de, etc.)
    'vad_filter': True,                # Voice Activity Detection
    'vad_min_silence_duration': 500,   # Milliseconds
    'vad_threshold': 0.5,              # 0.0 to 1.0
    
    # Audio Quality Checks
    'silence_threshold': 0.01,         # Audio level below this is considered silence
}

# ============================================================================
# FUSION LAYER CONFIGURATION
# ============================================================================

FUSION_CONFIG = {
    # Semantic Similarity Settings
    'similarity_threshold': 0.4,       # 0.0 to 1.0 (0.4 = 40%)

    # ── NVIDIA Embedding API ──────────────────────────────────────────────
    # Model: nvidia/llama-3.2-nv-embedqa-1b-v2
    # Set the NVIDIA_API_KEY environment variable before running server.py:
    #   Windows:  set NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
    #   Linux:    export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
    # Get a free key at: https://build.nvidia.com/nvidia/llama-3_2-nv-embedqa-1b-v2
    'nvidia_model': 'nvidia/llama-3.2-nv-embedqa-1b-v2',
    'nvidia_api_url': 'https://integrate.api.nvidia.com/v1/embeddings',
    'nvidia_api_timeout': 10.0,        # seconds per request

    # Fallback: lightweight TF-IDF cosine similarity (used when NVIDIA_API_KEY is unset)
    'use_tfidf_fallback': True,

    # Caching Settings
    'embedding_cache_size': 200,       # Max cached (text, input_type) pairs

    # Update Frequency
    'fusion_update_interval': 0.1,     # Seconds (10 Hz)

    # Minimum Lengths for Processing
    'min_topic_length': 3,             # Characters
    'min_transcription_length': 5,     # Characters
}

# ============================================================================
# UI CONFIGURATION
# ============================================================================

UI_CONFIG = {
    # Window Settings
    'window_width': 1280,
    'window_height': 720,
    'window_name': 'SynthSpeak - AI Presentation Coach',
    
    # Display Settings
    'ui_fps': 30,                      # UI refresh rate
    'info_panel_width': 400,           # Width of right sidebar
    
    # Colors (BGR format)
    'color_green': (0, 255, 0),
    'color_red': (0, 0, 255),
    'color_yellow': (0, 255, 255),
    'color_white': (255, 255, 255),
    'color_black': (0, 0, 0),
    'color_blue': (255, 100, 0),
    
    # Text Settings
    'font_scale_title': 1.2,
    'font_scale_normal': 0.6,
    'font_scale_small': 0.45,
    'font_thickness_bold': 3,
    'font_thickness_normal': 2,
    'font_thickness_thin': 1,
    
    # Text Wrapping
    'max_chars_per_line': 35,
    'max_topic_lines': 3,
    'max_transcription_lines': 5,
    
    # Visual Feedback
    'status_bar_height': 60,
    'progress_bar_height': 5,
    'overlay_alpha': 0.7,              # Transparency (0.0 to 1.0)
}

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

APP_CONFIG = {
    # Default Mode
    'default_mode': 'auto',            # 'auto' or 'manual'
    
    # Threading
    'thread_timeout': 2.0,             # Seconds to wait for threads on shutdown
    
    # Logging
    'verbose': True,                   # Print detailed logs
    'enable_performance_metrics': False,  # Show FPS and processing times
    
    # Screenshots
    'screenshot_directory': '.',       # Directory to save screenshots
    'screenshot_prefix': 'synthspeak_screenshot',
}

# ============================================================================
# PERFORMANCE PRESETS
# ============================================================================

PERFORMANCE_PRESETS = {
    'high_accuracy': {
        'visual': {
            'pose_model_complexity': 2,
            'ocr_interval': 3.0,
        },
        'audio': {
            'model_size': 'small',
            'beam_size': 7,
        },
        'fusion': {
            'similarity_threshold': 0.5,
        }
    },
    
    'balanced': {
        'visual': {
            'pose_model_complexity': 1,
            'ocr_interval': 4.0,
        },
        'audio': {
            'model_size': 'base',
            'beam_size': 5,
        },
        'fusion': {
            'similarity_threshold': 0.4,
        }
    },
    
    'high_performance': {
        'visual': {
            'pose_model_complexity': 0,
            'ocr_interval': 6.0,
        },
        'audio': {
            'model_size': 'tiny',
            'beam_size': 3,
        },
        'fusion': {
            'similarity_threshold': 0.3,
        }
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def apply_preset(preset_name):
    """
    Apply a performance preset to the configuration
    
    Args:
        preset_name: 'high_accuracy', 'balanced', or 'high_performance'
    """
    if preset_name not in PERFORMANCE_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}")
    
    preset = PERFORMANCE_PRESETS[preset_name]
    
    # Update configurations
    if 'visual' in preset:
        VISUAL_CONFIG.update(preset['visual'])
    if 'audio' in preset:
        AUDIO_CONFIG.update(preset['audio'])
    if 'fusion' in preset:
        FUSION_CONFIG.update(preset['fusion'])
    
    print(f"✅ Applied preset: {preset_name}")


def get_config_summary():
    """Print a summary of current configuration"""
    print("\n" + "="*60)
    print("SYNTHSPEAK CONFIGURATION SUMMARY")
    print("="*60)
    
    print("\n📷 Visual Pipeline:")
    print(f"  - Camera: {VISUAL_CONFIG['camera_index']} @ {VISUAL_CONFIG['fps']} FPS")
    print(f"  - Resolution: {VISUAL_CONFIG['frame_width']}x{VISUAL_CONFIG['frame_height']}")
    print(f"  - OCR Interval: {VISUAL_CONFIG['ocr_interval']}s")
    print(f"  - Pose Model: Complexity {VISUAL_CONFIG['pose_model_complexity']}")
    
    print("\n🎤 Audio Pipeline:")
    print(f"  - Chunk Duration: {AUDIO_CONFIG['chunk_duration']}s")
    print(f"  - Whisper Model: {AUDIO_CONFIG['model_size']}")
    print(f"  - Compute Type: {AUDIO_CONFIG['compute_type']}")
    print(f"  - Beam Size: {AUDIO_CONFIG['beam_size']}")
    
    print("\n🧠 Fusion Layer:")
    print(f"  - Similarity Threshold: {FUSION_CONFIG['similarity_threshold']}")
    print(f"  - SBERT Model: {FUSION_CONFIG['sentence_transformer_model']}")
    
    print("\n🎨 UI Settings:")
    print(f"  - Resolution: {UI_CONFIG['window_width']}x{UI_CONFIG['window_height']}")
    print(f"  - Refresh Rate: {UI_CONFIG['ui_fps']} FPS")
    
    print("\n⚙️  Application:")
    print(f"  - Default Mode: {APP_CONFIG['default_mode']}")
    print(f"  - Verbose Logging: {APP_CONFIG['verbose']}")
    
    print("="*60 + "\n")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example 1: Apply high accuracy preset
    # apply_preset('high_accuracy')
    
    # Example 2: Apply performance preset for slow CPUs
    # apply_preset('high_performance')
    
    # Example 3: Custom configuration
    # FUSION_CONFIG['similarity_threshold'] = 0.5  # More strict
    # AUDIO_CONFIG['model_size'] = 'small'  # More accurate
    
    # Print configuration
    get_config_summary()