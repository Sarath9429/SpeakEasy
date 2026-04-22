import sys
try:
    import google.protobuf.symbol_database as _sym_db_mod
    import google.protobuf.message_factory as _msg_factory_mod

    def _get_prototype(self, descriptor):
        try:
            return _msg_factory_mod.GetMessageClass(descriptor)
        except Exception:
            from google.protobuf import reflection as _refl
            return _refl.MakeClass(descriptor)
    _SymDB = _sym_db_mod.SymbolDatabase
    if not hasattr(_SymDB, 'GetPrototype'):
        _SymDB.GetPrototype = _get_prototype
    _MsgFactory = _msg_factory_mod.MessageFactory
    if _MsgFactory is not None and not hasattr(_MsgFactory, 'GetPrototype'):
        _MsgFactory.GetPrototype = _get_prototype

except Exception as _patch_err:
    print(f"⚠️  Protobuf patch failed (non-fatal): {_patch_err}")

import cv2
import numpy as np
import mediapipe as mp
import time
import threading
import math
import os


class GestureAnalyzer:
    """
    Translates raw MediaPipe skeletal tracking data into holistic 
    behavioral insights (e.g., posture alignment, eye contact trajectory).
    These metrics directly inform the frontend's coaching dashboards.
    """
    
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_hands = mp.solutions.hands
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.hands = self.mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.eye_contact_history = []
        self.eye_contact_window = 8   # frames — smaller = more responsive
        self.posture_history = []
        self.posture_window = 8
        self.hand_movement_history = []
        self.last_hand_positions = None
        self.face_orientation_history = []
        
    def analyze_eye_contact(self, face_landmarks, frame_width, frame_height):
        """
        Detect if person is looking at camera (eye contact)
        Returns: (has_eye_contact, gaze_direction, confidence)
        """
        if not face_landmarks:
            return False, "No face detected", 0.0
        LEFT_IRIS = [469, 470, 471, 472]
        RIGHT_IRIS = [474, 475, 476, 477]
        LEFT_EYE_CORNERS = [33, 133]
        RIGHT_EYE_CORNERS = [362, 263]
        
        landmarks = face_landmarks.landmark
        left_iris_x = np.mean([landmarks[i].x for i in LEFT_IRIS])
        left_iris_y = np.mean([landmarks[i].y for i in LEFT_IRIS])
        right_iris_x = np.mean([landmarks[i].x for i in RIGHT_IRIS])
        right_iris_y = np.mean([landmarks[i].y for i in RIGHT_IRIS])
        left_corner_x = (landmarks[LEFT_EYE_CORNERS[0]].x + landmarks[LEFT_EYE_CORNERS[1]].x) / 2
        right_corner_x = (landmarks[RIGHT_EYE_CORNERS[0]].x + landmarks[RIGHT_EYE_CORNERS[1]].x) / 2
        left_offset = abs(left_iris_x - left_corner_x)
        right_offset = abs(right_iris_x - right_corner_x)
        avg_offset = (left_offset + right_offset) / 2
        LOOKING_AT_CAMERA_THRESHOLD = 0.015
        LOOKING_AWAY_THRESHOLD = 0.04
        if avg_offset < LOOKING_AT_CAMERA_THRESHOLD:
            has_contact = True
            direction = "Camera (Good!)"
            confidence = 1.0 - (avg_offset / LOOKING_AT_CAMERA_THRESHOLD)
        elif avg_offset < LOOKING_AWAY_THRESHOLD:
            has_contact = False
            direction = "Slightly away"
            confidence = 0.5
        else:
            has_contact = False
            if left_iris_x > left_corner_x and right_iris_x > right_corner_x:
                direction = "Looking right"
            elif left_iris_x < left_corner_x and right_iris_x < right_corner_x:
                direction = "Looking left"
            elif left_iris_y < 0.45:
                direction = "Looking up"
            elif left_iris_y > 0.55:
                direction = "Looking down"
            else:
                direction = "Looking away"
            confidence = min(avg_offset / 0.1, 1.0)
        self.eye_contact_history.append(has_contact)
        if len(self.eye_contact_history) > self.eye_contact_window:
            self.eye_contact_history.pop(0)
        eye_contact_pct = sum(self.eye_contact_history) / len(self.eye_contact_history) * 100 if self.eye_contact_history else 0
        
        return has_contact, direction, eye_contact_pct
    
    def analyze_posture(self, pose_landmarks):
        """
        Analyze body posture for presentation
        Checks: slouching, leaning, shoulder alignment
        Returns: (is_good_posture, posture_score, issues)
        """
        if not pose_landmarks:
            return True, 100, []
        
        landmarks = pose_landmarks.landmark
        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_HIP = 23
        RIGHT_HIP = 24
        NOSE = 0
        LEFT_EAR = 7
        RIGHT_EAR = 8
        
        issues = []
        score = 100
        left_shoulder_y = landmarks[LEFT_SHOULDER].y
        right_shoulder_y = landmarks[RIGHT_SHOULDER].y
        shoulder_diff = abs(left_shoulder_y - right_shoulder_y)
        
        if shoulder_diff > 0.05:
            issues.append("Uneven shoulders")
            score -= 20
        avg_shoulder_y = (left_shoulder_y + right_shoulder_y) / 2
        avg_hip_y = (landmarks[LEFT_HIP].y + landmarks[RIGHT_HIP].y) / 2
        torso_height = avg_hip_y - avg_shoulder_y
        nose_y = landmarks[NOSE].y
        head_forward = nose_y - avg_shoulder_y
        if head_forward > torso_height * 0.3:
            issues.append("Slouching/Head forward")
            score -= 30
        avg_shoulder_x = (landmarks[LEFT_SHOULDER].x + landmarks[RIGHT_SHOULDER].x) / 2
        avg_hip_x = (landmarks[LEFT_HIP].x + landmarks[RIGHT_HIP].x) / 2
        lateral_diff = abs(avg_shoulder_x - avg_hip_x)
        
        if lateral_diff > 0.08:
            issues.append("Leaning to side")
            score -= 25
        frame_center = 0.5
        body_center_x = (landmarks[LEFT_SHOULDER].x + landmarks[RIGHT_SHOULDER].x) / 2
        
        if abs(body_center_x - frame_center) > 0.25:
            issues.append("Off-center")
            score -= 15
        self.posture_history.append(score)
        if len(self.posture_history) > self.posture_window:
            self.posture_history.pop(0)
        avg_score = sum(self.posture_history) / len(self.posture_history) if self.posture_history else score
        
        is_good = avg_score >= 70
        
        return is_good, avg_score, issues
    
    def analyze_face_orientation(self, face_landmarks):
        """
        Detect head orientation (pitch, yaw, roll)
        Returns: (orientation, angles_dict)
        """
        if not face_landmarks:
            return "Unknown", {"pitch": 0, "yaw": 0, "roll": 0}
        
        landmarks = face_landmarks.landmark
        nose_tip = np.array([landmarks[1].x, landmarks[1].y, landmarks[1].z])
        nose_bridge = np.array([landmarks[168].x, landmarks[168].y, landmarks[168].z])
        left_eye = np.array([landmarks[33].x, landmarks[33].y, landmarks[33].z])
        right_eye = np.array([landmarks[263].x, landmarks[263].y, landmarks[263].z])
        chin = np.array([landmarks[152].x, landmarks[152].y, landmarks[152].z])
        eye_center = (left_eye + right_eye) / 2
        horizontal_diff = nose_tip[0] - eye_center[0]
        yaw = np.arctan2(horizontal_diff, 0.1) * 180 / np.pi
        vertical_diff = nose_tip[1] - nose_bridge[1]
        pitch = np.arctan2(vertical_diff, 0.1) * 180 / np.pi
        eye_diff = right_eye - left_eye
        roll = np.arctan2(eye_diff[1], eye_diff[0]) * 180 / np.pi
        if abs(yaw) < 15 and abs(pitch) < 15:
            orientation = "Facing camera (Good!)"
        elif yaw > 15:
            orientation = "Turned left"
        elif yaw < -15:
            orientation = "Turned right"
        elif pitch > 15:
            orientation = "Looking down"
        elif pitch < -15:
            orientation = "Looking up"
        else:
            orientation = "Slightly off"
        
        return orientation, {"pitch": pitch, "yaw": yaw, "roll": roll}
    
    def analyze_hand_gestures(self, hands_landmarks):
        """
        Track hand movements and gestures
        Returns: (gesture_description, movement_intensity)
        """
        if not hands_landmarks or not hands_landmarks.multi_hand_landmarks:
            self.last_hand_positions = None
            return "No hands visible", 0.0
        
        num_hands = len(hands_landmarks.multi_hand_landmarks)
        current_positions = []
        for hand_landmarks in hands_landmarks.multi_hand_landmarks:
            wrist = hand_landmarks.landmark[0]  # Wrist is landmark 0
            current_positions.append((wrist.x, wrist.y, wrist.z))
        movement_intensity = 0.0
        if self.last_hand_positions and len(self.last_hand_positions) == len(current_positions):
            for prev, curr in zip(self.last_hand_positions, current_positions):
                movement = math.sqrt(
                    (curr[0] - prev[0])**2 + 
                    (curr[1] - prev[1])**2 + 
                    (curr[2] - prev[2])**2
                )
                movement_intensity += movement
            
            movement_intensity = movement_intensity / len(current_positions)
        
        self.last_hand_positions = current_positions
        avg_height = sum(pos[1] for pos in current_positions) / len(current_positions)
        
        if num_hands == 2:
            if avg_height < 0.4:
                gesture = "Both hands raised (Enthusiastic!)"
            elif avg_height < 0.6:
                gesture = "Gesturing with both hands (Good!)"
            else:
                gesture = "Hands at sides"
        elif num_hands == 1:
            if avg_height < 0.5:
                gesture = "One hand gesturing"
            else:
                gesture = "One hand visible"
        else:
            gesture = "Hands not visible"
        if movement_intensity > 0.1:
            gesture += " - Active movement"
        elif movement_intensity > 0.05:
            gesture += " - Moderate movement"
        
        return gesture, movement_intensity * 100  # Scale to percentage


class VisualPipeline:
    """
    Primary image processing thread. Receives JPEG frames pushed from the
    browser via the /ws/stream WebSocket endpoint, runs frame-level skeletal
    extraction via MediaPipe, and coordinates asynchronous OCR scans to
    establish presentation topics.
    """
    
    def __init__(self, shared_state):
        """Initialize visual pipeline"""
        self.shared_state = shared_state
        self.running = False
        self.use_screen_capture = False
        self.screen_monitor = 1
        self.FPS = 30
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        # NOTE: pose/face/hand objects are created fresh in run() each session
        # to avoid MediaPipe graph timestamp conflicts across multiple sessions.
        self.pose = None
        self.gesture_analyzer = None
        # Processing flag — prevents frame queue buildup when CPU is slow
        self._processing_frame = False
        # Topic state — initialised here so set_manual_topic() and get_state_dict()
        # can be called safely before run() completes.
        self.topic_confirmed = False
        self.confirmed_topic = ""
        self.detected_topic = ""
        self.pending_confirmation = False
        self.manual_mode = False
        # Lock and cache for the most-recently-received frame
        self._last_frame_lock = threading.Lock()
        self._last_frame = None
        # OCR state
        self.ocr_in_progress = False
        self.ocr_trigger = threading.Event()

    
    def capture_screen(self):
        """Capture the screen/presentation display"""
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[self.screen_monitor]
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except Exception as e:
            print(f"⚠️  Screen capture error: {e}")
            return None
        
    def feed_frame(self, jpeg_bytes: bytes) -> None:
        """
        Entry point for browser-streamed video frames.
        Decodes the JPEG, runs MediaPipe analysis, and updates shared state.
        Drops the frame immediately if the previous frame is still being processed
        (prevents queue buildup when CPU is slower than the browser send rate).
        """
        # Guard: skip if pipeline stopped or MediaPipe not ready
        if not self.running or self.pose is None or self.gesture_analyzer is None:
            return
        # Skip-if-busy: drop the frame rather than queuing behind slow CPU
        if self._processing_frame:
            return
        self._processing_frame = True
        try:
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return
            with self._last_frame_lock:
                self._last_frame = frame
            annotated_frame, _ = self.process_frame_with_analysis(frame)
            self.shared_state.update_video_frame(annotated_frame)
            if self.ocr_trigger.is_set() and not self.ocr_in_progress and not self.topic_confirmed:
                self.ocr_trigger.clear()
                ocr_frame = self.capture_screen() if self.use_screen_capture else frame
                if ocr_frame is not None:
                    self.run_ocr_async(ocr_frame)
        except Exception:
            pass  # silently ignore per-frame errors
        finally:
            self._processing_frame = False

    def process_frame_with_analysis(self, frame):
        """
        Process frame with full gesture analysis
        Returns: annotated_frame, analysis_results
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pose_results = self.pose.process(rgb_frame)
        face_results = self.gesture_analyzer.face_mesh.process(rgb_frame)
        hand_results = self.gesture_analyzer.hands.process(rgb_frame)
        
        annotated_frame = frame.copy()
        analysis = {
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
        if pose_results.pose_landmarks:
            good_posture, posture_score, issues = self.gesture_analyzer.analyze_posture(
                pose_results.pose_landmarks
            )
            analysis['good_posture'] = good_posture
            analysis['posture_score'] = posture_score
            analysis['posture_issues'] = issues
        if face_results.multi_face_landmarks:
            for face_landmarks in face_results.multi_face_landmarks:
                has_contact, direction, eye_pct = self.gesture_analyzer.analyze_eye_contact(
                    face_landmarks, frame.shape[1], frame.shape[0]
                )
                analysis['has_eye_contact'] = has_contact
                analysis['eye_contact_direction'] = direction
                analysis['eye_contact_percentage'] = eye_pct
                orientation, angles = self.gesture_analyzer.analyze_face_orientation(face_landmarks)
                analysis['face_orientation'] = orientation
                analysis['face_angles'] = angles
        if hand_results.multi_hand_landmarks:
            gesture, movement = self.gesture_analyzer.analyze_hand_gestures(hand_results)
            analysis['hand_gesture'] = gesture
            analysis['hand_movement'] = movement
        if pose_results.pose_landmarks:
            self.shared_state.update_pose(pose_results.pose_landmarks)
        self.shared_state.update_gesture_analysis(analysis)
        
        return annotated_frame, analysis

    def set_manual_topic(self, topic):
        """Set topic manually"""
        if topic and len(topic.strip()) > 2:
            self.confirmed_topic = topic.strip()
            self.detected_topic = topic.strip()
            self.topic_confirmed = True
            self.pending_confirmation = False
            self.manual_mode = True
            
            self.shared_state.update_slide_topic(self.confirmed_topic)
            self.shared_state.set_topic_confirmed(True)
            
            print(f"\n✅ MANUAL TOPIC SET: '{self.confirmed_topic}'")
            print("   🎤 Audio relevance detection is NOW ACTIVE")
            print("   Press 'N' to reset for new slide\n")
            return True
        return False
    
    def reset_topic(self):
        """Reset topic state for a new session"""
        self.topic_confirmed = False
        self.confirmed_topic = ""
        self.manual_mode = False
        self.shared_state.set_topic_confirmed(False)
        print("\n🔄 TOPIC RESET")

    def get_frame_for_ocr(self, cached_frame=None):
        """Kept for compatibility — returns the cached frame (screen capture removed)."""
        return cached_frame

    def run(self):
        """Main visual pipeline loop — waits for frames delivered via feed_frame()."""
        # Create fresh MediaPipe objects for each session.
        # This avoids CalculatorGraph timestamp conflicts that occur when
        # the same graph is reused across multiple Start/Stop cycles.
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
            model_complexity=1
        )
        self.gesture_analyzer = GestureAnalyzer()

        self.running = True
        print("👁️  Visual Pipeline started (browser-feed mode)")

        try:
            while self.running:
                time.sleep(0.1)
        except Exception as e:
            print(f"❌ Visual Pipeline error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()

        print("🛑 Visual Pipeline stopped")
    
    def cleanup(self):
        """Clean up resources — close MediaPipe graphs gracefully."""
        try:
            if self.pose is not None:
                self.pose.close()
                self.pose = None
        except Exception:
            pass
        try:
            if self.gesture_analyzer is not None:
                self.gesture_analyzer.face_mesh.close()
                self.gesture_analyzer.hands.close()
                self.gesture_analyzer = None
        except Exception:
            pass
    
    def stop(self):
        """Stop the visual pipeline"""
        self.running = False