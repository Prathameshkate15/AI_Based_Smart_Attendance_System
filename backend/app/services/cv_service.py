"""
Computer Vision Pipeline for Smart Attendance System
Handles face detection, liveness detection, and face recognition
"""

import cv2
import numpy as np
import insightface
from deepface import DeepFace
from typing import Optional, Tuple, Dict, Any, List


class CvPipeline:
    """Main computer vision pipeline for biometric attendance."""

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        liveness_threshold: float = 0.7,
        model_name: str = "buffalo_l",
    ):
        self.confidence_threshold = confidence_threshold
        self.liveness_threshold = liveness_threshold

        # Initialize InsightFace model for embeddings
        try:
            self.model = insightface.model_zoo.get_model(model_name)
            self.model.prepare(ctx_id=0)
        except Exception:
            self.model = None
            print("Warning: Could not load InsightFace model, falling back to DeepFace")

        self.known_embeddings: Dict[int, np.ndarray] = {}  # user_id -> embedding vector
        self.known_users: Dict[int, Dict[str, Any]] = {}  # user_id -> name, employee_id
        cascade_classifier = getattr(cv2, "CascadeClassifier", None)
        self.face_detector = (
            cascade_classifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if cascade_classifier
            else None
        )
        self.profile_detector = (
            cascade_classifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
            if cascade_classifier
            else None
        )

    def extract_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """Extract and normalize one face embedding."""
        if self.model is not None:
            embedding = self.model.get_emb(cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB))
        else:
            result = DeepFace.represent(
                img_path=face_image, model_name="Facenet", enforce_detection=False
            )
            embedding = np.array(result[0]["embedding"]) if result else None
        if embedding is None:
            return None
        embedding = np.asarray(embedding, dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(embedding)
        return embedding / norm if norm else None

    def extract_single_face_embedding(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Extract an enrollment embedding, tolerating missed profile detections."""
        boxes = self.detect_face_boxes(image)
        if boxes:
            x, y, width, height = max(boxes, key=lambda box: box[2] * box[3])
            return self.extract_embedding(image[y : y + height, x : x + width])
        if image.size == 0:
            return None
        height, width = image.shape[:2]
        margin_x, margin_y = int(width * 0.15), int(height * 0.08)
        return self.extract_embedding(
            image[margin_y : height - margin_y, margin_x : width - margin_x]
        )

    def detect_face_boxes(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect frontal and profile faces, merging duplicate detections."""
        if self.face_detector is None:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detectors = [self.face_detector]
        if self.profile_detector is not None:
            detectors.append(self.profile_detector)
        detections = []
        for detector in detectors:
            detections.extend(
                detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
            )
        if not detections:
            return []
        boxes = [tuple(map(int, box)) for box in detections]
        merged = []
        for box in boxes:
            if not any(self._intersection_over_union(box, existing) > 0.35 for existing in merged):
                merged.append(box)
        return merged

    @staticmethod
    def _intersection_over_union(first, second) -> float:
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        left, top = max(ax, bx), max(ay, by)
        right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        overlap = max(0, right - left) * max(0, bottom - top)
        union = aw * ah + bw * bh - overlap
        return overlap / union if union else 0.0

    def register_face(
        self, user_id: int, face_image: np.ndarray, name: str, employee_id: str
    ) -> Dict[str, Any]:
        """
        Extract face embedding from a registered face image.
        """
        try:
            embedding = self.extract_embedding(face_image)

            if embedding is None:
                return {"success": False, "error": "Could not extract face embedding"}

            # Normalize embedding for cosine similarity
            self.known_embeddings[user_id] = embedding
            self.known_users[user_id] = {"name": name, "employee_id": employee_id}

            return {
                "success": True,
                "embedding_dimension": len(embedding),
                "message": f"Face embedding registered for user {user_id} ({name})",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_face(self, face_image: np.ndarray) -> Tuple[Optional[int], Optional[float], Optional[Dict]]:
        """
        Verify a live face against known embeddings.
        Returns (user_id, confidence, user_info) or (None, None, None) if no match.
        """
        try:
            embedding = self.extract_embedding(face_image)
            if embedding is None:
                return None, None, None

            # Compare against known embeddings using cosine similarity
            best_match_id = None
            best_similarity = -1.0

            for uid, known_emb in self.known_embeddings.items():
                # Cosine similarity: dot product of normalized vectors
                similarity = float(np.dot(embedding, known_emb))

                if similarity > best_similarity and similarity >= self.confidence_threshold:
                    best_similarity = similarity
                    best_match_id = uid

            if best_match_id is not None:
                user_info = self.known_users.get(best_match_id, {})
                return best_match_id, best_similarity, user_info

            return None, None, None

        except Exception as e:
            return None, None, None

    def analyze_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect all faces and match each face against registered embeddings."""
        boxes = self.detect_face_boxes(image)
        if not boxes:
            return []
        matches = []
        for x, y, width, height in boxes:
            crop = image[y : y + height, x : x + width]
            user_id, confidence, user_info = self.verify_face(crop)
            matches.append(
                {
                    "box": {
                        "x": int(x),
                        "y": int(y),
                        "width": int(width),
                        "height": int(height),
                    },
                    "user_id": user_id,
                    "employee_id": user_info.get("employee_id") if user_info else None,
                    "name": user_info.get("name") if user_info else "Unknown",
                    "confidence": round(confidence, 4) if confidence is not None else None,
                    "recognized": user_id is not None,
                }
            )
        return matches

    def check_liveness(
        self, face_image_sequence: List[np.ndarray]
    ) -> Tuple[bool, float]:
        """
        Perform liveness detection using a sequence of face images.
        Returns (is_live, liveness_score).
        Uses blink detection and head movement analysis.
        """
        try:
            if len(face_image_sequence) < 2:
                return False, 0.0

            ear_scores = []  # Eye Aspect Ratio scores
            motion_scores = []

            for i in range(1, len(face_image_sequence)):
                prev_gray = cv2.cvtColor(
                    face_image_sequence[i - 1], cv2.COLOR_BGR2GRAY
                )
                curr_gray = cv2.cvtColor(face_image_sequence[i], cv2.COLOR_BGR2GRAY)

                # Motion detection - frame difference
                frame_diff = cv2.absdiff(prev_gray, curr_gray)
                motion_score = float(np.mean(frame_diff))
                motion_scores.append(motion_score)

                # Estimate Eye Aspect Ratio (EAR)
                ear = self._estimate_ear(face_image_sequence[i])
                ear_scores.append(ear)

            # Calculate metrics
            avg_motion = np.mean(motion_scores) if motion_scores else 0.0
            blink_count = sum(1 for ear in ear_scores if ear < 0.3)
            blink_ratio = blink_count / len(ear_scores) if ear_scores else 0.0

            # A short prompted movement sequence is the reliable signal here.
            # Blink estimation is only a supporting signal because the
            # lightweight eye-region heuristic is not reliable across cameras.
            motion_factor = min(avg_motion / 12.0, 1.0)
            blink_factor = min(blink_ratio * 5, 1.0)
            liveness_score = 0.8 * motion_factor + 0.2 * blink_factor
            is_live = liveness_score >= self.liveness_threshold

            return bool(is_live), float(liveness_score)

        except Exception as e:
            return False, 0.0

    def _estimate_ear(self, face_image: np.ndarray) -> float:
        """
        Estimate Eye Aspect Ratio for liveness detection.
        Uses a simplified model based on eye region intensity.
        """
        try:
            h, w = face_image.shape[:2]

            # Extract eye regions (approximate positions)
            # Left eye: top 40% of face, middle third
            # Right eye: top 45% of face, middle third
            left_eye = face_image[int(h * 0.35) : int(h * 0.45), int(w * 0.3) : int(w * 0.6)]
            right_eye = face_image[int(h * 0.4) : int(h * 0.5), int(w * 0.35) : int(w * 0.65)]

            # Convert to grayscale
            left_gray = cv2.cvtColor(left_eye, cv2.COLOR_BGR2GRAY)
            right_gray = cv2.cvtColor(right_eye, cv2.COLOR_BGR2GRAY)

            # Calculate mean intensity - blinks make eyes darker
            left_mean = float(np.mean(left_gray))
            right_mean = float(np.mean(right_gray))

            # Average the two eyes, normalize to 0-1 range
            avg_mean = (left_mean + right_mean) / 2.0 / 255.0
            return avg_mean
        except Exception:
            return 0.5

    def get_system_status(self) -> Dict[str, Any]:
        """Return pipeline status and statistics."""
        return {
            "known_users_count": len(self.known_users),
            "confidence_threshold": self.confidence_threshold,
            "liveness_threshold": self.liveness_threshold,
            "model_available": self.model is not None,
            "pipeline_ready": len(self.known_users) > 0,
            "embedding_dimension": (
                len(next(iter(self.known_embeddings.values()))) if self.known_embeddings else 512
            ),
        }