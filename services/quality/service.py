from __future__ import annotations

import cv2
import numpy as np

from services.recognition.types import DetectedFace, LivenessResult, QualityResult


class QualityGate:
    def evaluate(
        self,
        frame: np.ndarray,
        faces: list[DetectedFace],
        max_faces: int,
        min_face_width_px: int,
        min_brightness: float,
        min_blur_score: float,
        liveness: LivenessResult,
        liveness_threshold: float,
    ) -> QualityResult:
        grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness_score = float(np.mean(grayscale))
        blur_score = float(cv2.Laplacian(grayscale, cv2.CV_64F).var())
        face_width_px = int(max((face.bbox[2] - face.bbox[0]) for face in faces) if faces else 0)
        flags = {
            "exactly_one_face": len(faces) == 1,
            "max_faces_respected": len(faces) <= max_faces,
            "min_face_width": face_width_px >= min_face_width_px,
            "min_brightness": brightness_score >= min_brightness,
            "min_blur_score": blur_score >= min_blur_score,
            "liveness_threshold": liveness.score >= liveness_threshold,
        }
        ordered_reasons = [
            ("exactly_one_face", "exactly_one_face_required"),
            ("max_faces_respected", "too_many_faces"),
            ("min_face_width", "face_too_small"),
            ("min_brightness", "frame_too_dark"),
            ("min_blur_score", "frame_too_blurry"),
            ("liveness_threshold", "liveness_below_threshold"),
        ]
        accepted = True
        reason = "accepted"
        for key, message in ordered_reasons:
            if not flags[key]:
                accepted = False
                reason = message
                break
        return QualityResult(
            brightness_score=brightness_score,
            blur_score=blur_score,
            liveness_score=liveness.score,
            face_width_px=face_width_px,
            accepted=accepted,
            reason=reason,
            flags=flags,
        )

