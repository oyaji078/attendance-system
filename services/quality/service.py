from __future__ import annotations

import cv2
import numpy as np

from services.recognition.types import DetectedFace, LivenessResult, QualityResult


MIN_CONTRAST = 18.0
MAX_OVEREXPOSED_RATIO = 0.18
MAX_UNDEREXPOSED_RATIO = 0.35
MAX_FACE_CENTER_OFFSET = 0.25


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
        quality_mode: str | None = None,
    ) -> QualityResult:
        grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness_score = float(np.mean(grayscale))
        blur_score = float(cv2.Laplacian(grayscale, cv2.CV_64F).var())
        contrast_score = float(np.std(grayscale))
        overexposed_ratio = float(np.mean(grayscale >= 245))
        underexposed_ratio = float(np.mean(grayscale <= 20))
        face_width_px = int(max((face.bbox[2] - face.bbox[0]) for face in faces) if faces else 0)
        primary_face = faces[0] if faces else None
        frame_height, frame_width = frame.shape[:2]
        face_bbox = [float(value) for value in primary_face.bbox] if primary_face else None
        face_box_normalized = None
        face_center = None
        face_size_ratio = None
        if primary_face is not None and frame_width > 0 and frame_height > 0:
            x1, y1, x2, y2 = primary_face.bbox
            width = max(0.0, float(x2) - float(x1))
            height = max(0.0, float(y2) - float(y1))
            center_x = float(x1 + x2) / 2.0
            center_y = float(y1 + y2) / 2.0
            face_box_normalized = {
                "x": float(x1) / frame_width,
                "y": float(y1) / frame_height,
                "width": width / frame_width,
                "height": height / frame_height,
            }
            face_center = {"x": center_x / frame_width, "y": center_y / frame_height}
            face_size_ratio = float(primary_face.relative_area)
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
            "min_contrast": contrast_score >= MIN_CONTRAST,
            "overexposed_ratio": overexposed_ratio <= MAX_OVEREXPOSED_RATIO,
            "underexposed_ratio": underexposed_ratio <= MAX_UNDEREXPOSED_RATIO,
            "face_centered_x": abs(face_center_offset_x) <= MAX_FACE_CENTER_OFFSET,
            "face_centered_y": abs(face_center_offset_y) <= MAX_FACE_CENTER_OFFSET,
        }
        ordered_reasons = [
            ("max_faces_respected", "multiple_faces_detected"),
            ("exactly_one_face", "exactly_one_face_required"),
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
        ui_hint = "Wajah berhasil direkam."
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
            face_bbox=face_bbox,
            face_box_normalized=face_box_normalized,
            face_center=face_center,
            face_size_ratio=face_size_ratio,
            face_count=len(faces),
            max_faces=max_faces,
            min_face_width_px=min_face_width_px,
            min_brightness=min_brightness,
            min_blur_score=min_blur_score,
            liveness_threshold=liveness_threshold,
            min_contrast=MIN_CONTRAST,
            max_overexposed_ratio=MAX_OVEREXPOSED_RATIO,
            max_underexposed_ratio=MAX_UNDEREXPOSED_RATIO,
            max_face_center_offset=MAX_FACE_CENTER_OFFSET,
            quality_mode=quality_mode,
        )

    @staticmethod
    def _hint_for_reason(reason: str, center_offset_x: float, center_offset_y: float) -> str:
        if reason == "frame_too_dark":
            return "Cahaya terlalu redup. Pindah ke tempat yang lebih terang."
        if reason == "frame_overexposed":
            return "Cahaya terlalu terang. Kurangi silau pada wajah."
        if reason == "frame_low_contrast":
            return "Pencahayaan kurang jelas. Cari cahaya yang lebih merata."
        if reason == "frame_too_blurry":
            return "Gambar buram, diamkan wajah."
        if reason == "face_too_small":
            return "Dekatkan wajah ke kamera."
        if reason == "face_not_centered":
            if abs(center_offset_x) >= abs(center_offset_y):
                return "Posisikan wajah di tengah."
            return "Naikkan atau turunkan wajah sedikit."
        if reason == "multiple_faces_detected":
            return "Pastikan hanya satu wajah di dalam kamera."
        if reason == "exactly_one_face_required":
            return "Posisikan wajah di dalam oval."
        if reason == "liveness_below_threshold":
            return "Wajah belum terverifikasi, coba lagi."
        return "Sesuaikan wajah dan coba lagi."
