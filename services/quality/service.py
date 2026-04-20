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
        contrast_score = float(np.std(grayscale))
        overexposed_ratio = float(np.mean(grayscale >= 245))
        underexposed_ratio = float(np.mean(grayscale <= 20))
        face_width_px = int(max((face.bbox[2] - face.bbox[0]) for face in faces) if faces else 0)
        primary_face = faces[0] if faces else None
        face_center_offset_x = float(primary_face.center_offset_x if primary_face else 0.0)
        face_center_offset_y = float(primary_face.center_offset_y if primary_face else 0.0)
        pose_yaw = float(primary_face.pose_yaw if primary_face else 0.0)
        pose_pitch = float(primary_face.pose_pitch if primary_face else 0.0)
        pose_roll = float(primary_face.pose_roll if primary_face else 0.0)
        flags = {
            "exactly_one_face": len(faces) == 1,
            "max_faces_respected": len(faces) <= max_faces,
            "min_face_width": face_width_px >= min_face_width_px,
            "min_brightness": brightness_score >= min_brightness,
            "min_blur_score": blur_score >= min_blur_score,
            "liveness_threshold": liveness.score >= liveness_threshold,
            "min_contrast": contrast_score >= 18.0,
            "overexposed_ratio": overexposed_ratio <= 0.18,
            "underexposed_ratio": underexposed_ratio <= 0.35,
            "face_centered_x": abs(face_center_offset_x) <= 0.25,
            "face_centered_y": abs(face_center_offset_y) <= 0.25,
        }
        ordered_reasons = [
            ("exactly_one_face", "exactly_one_face_required"),
            ("max_faces_respected", "too_many_faces"),
            ("min_face_width", "face_too_small"),
            ("min_brightness", "frame_too_dark"),
            ("underexposed_ratio", "frame_too_dark"),
            ("overexposed_ratio", "frame_overexposed"),
            ("min_blur_score", "frame_too_blurry"),
            ("min_contrast", "frame_low_contrast"),
            ("face_centered_x", "face_not_centered"),
            ("face_centered_y", "face_not_centered"),
            ("liveness_threshold", "liveness_below_threshold"),
        ]
        accepted = True
        reason = "accepted"
        ui_hint = "Frame accepted."
        for key, message in ordered_reasons:
            if not flags[key]:
                accepted = False
                reason = message
                ui_hint = self._hint_for_reason(message, face_center_offset_x, face_center_offset_y)
                break
        return QualityResult(
            brightness_score=brightness_score,
            blur_score=blur_score,
            contrast_score=contrast_score,
            overexposed_ratio=overexposed_ratio,
            underexposed_ratio=underexposed_ratio,
            liveness_score=liveness.score,
            face_width_px=face_width_px,
            face_center_offset_x=face_center_offset_x,
            face_center_offset_y=face_center_offset_y,
            pose_yaw=pose_yaw,
            pose_pitch=pose_pitch,
            pose_roll=pose_roll,
            pose_valid=True,
            accepted=accepted,
            reason=reason,
            ui_hint=ui_hint,
            flags=flags,
        )

    @staticmethod
    def _hint_for_reason(reason: str, center_offset_x: float, center_offset_y: float) -> str:
        if reason == "frame_too_dark":
            return "Too dark. Move to better lighting or face the light."
        if reason == "frame_overexposed":
            return "Too bright. Reduce glare or move away from strong light."
        if reason == "frame_low_contrast":
            return "Lighting is flat. Add more balanced light on your face."
        if reason == "frame_too_blurry":
            return "Hold still for a moment to reduce blur."
        if reason == "face_too_small":
            return "Move closer to the camera."
        if reason == "face_not_centered":
            if abs(center_offset_x) >= abs(center_offset_y):
                return "Center your face horizontally in the frame."
            return "Center your face vertically in the frame."
        if reason == "too_many_faces":
            return "Only one face should be visible."
        if reason == "exactly_one_face_required":
            return "Make sure exactly one face is visible."
        if reason == "liveness_below_threshold":
            return "Hold still and look naturally at the camera."
        return "Adjust your face and try again."
