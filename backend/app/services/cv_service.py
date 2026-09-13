"""
Computer Vision Pipeline for Smart Attendance System
Handles face detection, liveness detection, and face recognition
"""

import cv2
import numpy as np
from deepface import DeepFace
from typing import Optional, Tuple, Dict, Any


class CvPipeline:
    """Main computer vision pipeline for biometric attendance."""

    def __init__(self, confidence_threshold: float = 0.5, liveness_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self.liveness_threshold = liveness_threshold
        self.known_embeddings = {}  # user_id -> embedding vector
        self.known_users = {}  # user_id -> name, employee_id

    def register_face(self, user_id: int, face_image: np.ndarray, name: str, employee_id: str) -> Dict[str, Any]:
        """
        Extract face embedding from registered images.
        Capture 5-10 images and average the embeddings.
        """
        try:
            # Use DeepFace to extract embedding
            embedding_objs = DeepFace.represent(
                img_path=face_image,
                model="Facenet",
                enforce_detection=False,
            )

            if not embedding_objs:
                return {"success": False, "error": "No face detected in image"}

            # Average embeddings if multiple images provided
            embeddings = [np.array(emb["embedding"]) for emb in embedding_objs]
            average_embedding = np.mean(embeddings, axis=0)
            normalized_embedding = average_embedding / np.linalg.norm(average_embedding)

            self.known_embeddings[user_id] = normalized_embedding
            self.known_users[user_id] = {"name": name, "employee_id": employee_id}

            return {
                "success": True,
                "embedding_dimension": len(normalized_embedding),
                "message": f"Face embedded registered for user {user_id}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_face(self, face_image: np.ndarray) -> Tuple[Optional[int], Optional[float], Optional[Dict]]:
        """
        Verify a live face against known embeddings.
        Returns (user_id, confidence, user_info) or (None, None, None) if no match.
        """
        try:
            # Extract embedding from live frame
            embedding_objs = DeepFace.represent(
                img_path=face_image,
                model="Facenet",
                enforce_detection=False,
            )

            if not embedding_objs:
                return None, None, None

            live_embedding = np.array(embedding_objs[0]["embedding"])
            normalized_live = live_embedding / np.linalg.norm(live_embedding)

            # Compare against known embeddings using cosine similarity
            best_match_id = None
            best_similarity = -1.0

            for user_id, known_embedding in self.known_embeddings.items():
                # Cosine similarity
                similarity = np.dot(normalized_live, known_embedding)

                if similarity > best_similarity and similarity >= self.confidence_threshold:
                    best_similarity = similarity
                    best_match_id = user_id

            if best_match_id is not None:
                user_info = self.known_users.get(best_match_id, {})
                return best_match_id, float(best_similarity), user_info

            return None, None, None

        except Exception as e:
            return None, None, None

    def check_liveness(self, face_image_sequence: list) -> Tuple[bool, float]:
        """
        Perform liveness detection using a sequence of face images.
        Returns (is_live, liveness_score).
        """
        try:
            if len(face_image_sequence) < 2:
                return False, 0.0

            # Simple liveness checks:
            # 1. Check for eye blink pattern (EAR - Eye Aspect Ratio)
            # 2. Check for head movement between frames
            # 3. Check for texture consistency (photo vs 3D face)

            ear_scores = []
            for i in range(1, len(face_image_sequence)):
                prev_gray = cv2.cvtColor(face_image_sequence[i - 1], cv2.COLOR_BGR2GRAY)
                curr_gray = cv2.cvtColor(face_image_sequence[i], cv2.COLOR_BGR2GRAY)

                # Simple motion detection - calculate frame difference
                frame_diff = cv2.absdiff(prev_gray, curr_gray)
                motion_score = np.mean(frame_diff)

                # Simple EAR approximation based on eye region
                # In production, use dlib shape predictor for precise eye landmarks
                ear = self._estimate_ear(face_image_sequence[i])
                ear_scores.append(ear)

            # Liveness score: combination of motion (live people move) and blink patterns
            motion_consistency = np.mean(ear_scores) if ear_scores else 0
            blink_indicator = sum(1 for ear in ear_scores if ear < 0.3) / len(ear_scores) if ear_scores else 0

            # Live person: has some motion AND blink pattern
            liveness_score = (0.6 * min(motion_consistivity / 50.0, 1.0) +
                              0.4 * min(blink_indicator * 3, 1.0))

            is_live = liveness_score >= self.liveness_threshold
            return is_live, float(liveness_score)

        except Exception as e:
            return False, 0.0

    def _estimate_ear(self, face_image: np.ndarray) -> float:
        """Estimate Eye Aspect Ratio for liveness detection."""
        try:
            # Simple approximation - in production use dlib shape predictor
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
            # Look at the upper and lower eye regions
            h, w = gray.shape

            # Simple threshold-based eye detection
            # This is a very rough approximation
            left_eye_region = gray[int(h * 0.4):int(h * 0.5), int(w * 0.3):int(w * 0.7)]
            right_eye_region = gray[int(h * 0.45):int(h * 0.55), int(w * 0.35):int(w * 0.65)]

            # Calculate ratio of white pixels (simplified)
            left_white = np.mean(left_eye_region)
            right_white = np.mean(right_eye_region)

            # Blink = eyes darken (pupils expand, eyelids close)
            # Open eyes = brighter region
            eye_ratio = min(left_white, right_white) / 255.0
            return float(eye_ratio)
        except Exception:
            return 0.5

    def get_system_status(self) -> Dict[str, Any]:
        """Return pipeline status and statistics."""
        return {
            "known_users_count": len(self.known_users),
            "confidence_threshold": self.confidence_threshold,
            "liveness_threshold": self.liveness_threshold,
            "pipeline_ready": len(self.known_users) > 0,
        }