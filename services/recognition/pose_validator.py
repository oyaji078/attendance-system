from __future__ import annotations

from dataclasses import dataclass

from db.schemas.common import PoseName
from services.recognition.types import DetectedFace


@dataclass(slots=True)
class PoseValidationResult:
    is_valid: bool
    reason: str
    ui_hint: str
    pose_status: str
    guidance_direction: str | None = None


class PoseValidator:
    FRONT_YAW_MAX = 12.0
    FRONT_PITCH_MAX = 12.0
    SIDE_YAW_MIN = 8.0
    SIDE_YAW_MAX = 35.0
    SIDE_PITCH_MAX = 18.0
    UP_DOWN_PITCH_MIN = 10.0
    UP_DOWN_PITCH_MAX = 28.0
    CENTER_OFFSET_MAX = 0.25

    def validate(self, requested_pose: PoseName, face: DetectedFace) -> PoseValidationResult:
        if abs(face.center_offset_x) > self.CENTER_OFFSET_MAX:
            direction = "move_left" if face.center_offset_x > 0 else "move_right"
            return PoseValidationResult(False, "face_not_centered", "Posisikan wajah di tengah.", "off_center", direction)
        if abs(face.center_offset_y) > self.CENTER_OFFSET_MAX:
            direction = "move_up" if face.center_offset_y > 0 else "move_down"
            return PoseValidationResult(False, "face_not_centered", "Posisikan wajah di dalam oval.", "off_center", direction)

        # InsightFace yaw is backend camera-space yaw, independent of any
        # mirrored selfie preview. In this model, negative yaw is used for the
        # requested left_20 pose and positive yaw for right_20.
        yaw = face.pose_yaw
        pitch = face.pose_pitch

        if requested_pose == "front":
            if abs(yaw) <= self.FRONT_YAW_MAX and abs(pitch) <= self.FRONT_PITCH_MAX:
                return PoseValidationResult(True, "pose_valid", "Bagus, tetap diam.", "valid", None)
            if yaw < -self.FRONT_YAW_MAX:
                return PoseValidationResult(False, "pose_mismatch_front", "Putar wajah sedikit ke kanan.", "turn_too_left", "turn_right")
            if yaw > self.FRONT_YAW_MAX:
                return PoseValidationResult(False, "pose_mismatch_front", "Putar wajah sedikit ke kiri.", "turn_too_right", "turn_left")
            direction = "lower_chin" if pitch > 0 else "raise_chin"
            return PoseValidationResult(False, "pose_mismatch_front", "Lihat lurus ke kamera.", "pitch_off", direction)

        if requested_pose == "left_20":
            if -self.SIDE_YAW_MAX <= yaw <= -self.SIDE_YAW_MIN and abs(pitch) <= self.SIDE_PITCH_MAX:
                return PoseValidationResult(True, "pose_valid", "Bagus, tetap diam.", "valid", None)
            if yaw > -self.SIDE_YAW_MIN:
                return PoseValidationResult(False, "pose_mismatch_left_20", "Putar wajah sedikit ke kiri.", "needs_more_left", "turn_left")
            return PoseValidationResult(False, "pose_mismatch_left_20", "Kembalikan wajah sedikit ke tengah.", "turned_too_far_left", "turn_right")

        if requested_pose == "right_20":
            if self.SIDE_YAW_MIN <= yaw <= self.SIDE_YAW_MAX and abs(pitch) <= self.SIDE_PITCH_MAX:
                return PoseValidationResult(True, "pose_valid", "Bagus, tetap diam.", "valid", None)
            if yaw < self.SIDE_YAW_MIN:
                return PoseValidationResult(False, "pose_mismatch_right_20", "Putar wajah sedikit ke kanan.", "needs_more_right", "turn_right")
            return PoseValidationResult(False, "pose_mismatch_right_20", "Kembalikan wajah sedikit ke tengah.", "turned_too_far_right", "turn_left")

        if self.UP_DOWN_PITCH_MIN <= abs(pitch) <= self.UP_DOWN_PITCH_MAX:
            return PoseValidationResult(True, "pose_valid", "Bagus, tetap diam.", "valid", None)
        if abs(pitch) < self.UP_DOWN_PITCH_MIN:
            return PoseValidationResult(False, "pose_mismatch_up_or_down", "Naikkan atau turunkan dagu sedikit.", "needs_pitch", "raise_or_lower_chin")
        direction = "lower_chin" if pitch > 0 else "raise_chin"
        return PoseValidationResult(False, "pose_mismatch_up_or_down", "Kembalikan dagu sedikit lalu tahan.", "pitch_too_far", direction)
