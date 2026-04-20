from __future__ import annotations

from dataclasses import dataclass

from db.schemas.common import PoseName
from services.recognition.types import DetectedFace


@dataclass(slots=True)
class PoseValidationResult:
    is_valid: bool
    reason: str
    ui_hint: str


class PoseValidator:
    FRONT_YAW_MAX = 10.0
    FRONT_PITCH_MAX = 12.0
    SIDE_YAW_MIN = 12.0
    SIDE_YAW_MAX = 35.0
    SIDE_PITCH_MAX = 18.0
    UP_DOWN_PITCH_MIN = 10.0
    UP_DOWN_PITCH_MAX = 28.0
    CENTER_OFFSET_MAX = 0.22

    def validate(self, requested_pose: PoseName, face: DetectedFace) -> PoseValidationResult:
        if abs(face.center_offset_x) > self.CENTER_OFFSET_MAX:
            return PoseValidationResult(False, "face_not_centered", "Move your face to the center of the frame.")
        if abs(face.center_offset_y) > self.CENTER_OFFSET_MAX:
            return PoseValidationResult(False, "face_not_centered", "Adjust your head to the center vertically.")

        yaw = face.pose_yaw
        pitch = face.pose_pitch

        if requested_pose == "front":
            if abs(yaw) <= self.FRONT_YAW_MAX and abs(pitch) <= self.FRONT_PITCH_MAX:
                return PoseValidationResult(True, "pose_valid", "Front pose accepted. Hold steady.")
            if yaw < -self.FRONT_YAW_MAX:
                return PoseValidationResult(False, "pose_mismatch_front", "Turn slightly right to face forward.")
            if yaw > self.FRONT_YAW_MAX:
                return PoseValidationResult(False, "pose_mismatch_front", "Turn slightly left to face forward.")
            return PoseValidationResult(False, "pose_mismatch_front", "Level your chin and face forward.")

        if requested_pose == "left_20":
            if -self.SIDE_YAW_MAX <= yaw <= -self.SIDE_YAW_MIN and abs(pitch) <= self.SIDE_PITCH_MAX:
                return PoseValidationResult(True, "pose_valid", "Left pose accepted. Hold still.")
            if yaw > -self.SIDE_YAW_MIN:
                return PoseValidationResult(False, "pose_mismatch_left_20", "Turn slightly more to your left.")
            return PoseValidationResult(False, "pose_mismatch_left_20", "Ease back a little toward the camera.")

        if requested_pose == "right_20":
            if self.SIDE_YAW_MIN <= yaw <= self.SIDE_YAW_MAX and abs(pitch) <= self.SIDE_PITCH_MAX:
                return PoseValidationResult(True, "pose_valid", "Right pose accepted. Hold still.")
            if yaw < self.SIDE_YAW_MIN:
                return PoseValidationResult(False, "pose_mismatch_right_20", "Turn slightly more to your right.")
            return PoseValidationResult(False, "pose_mismatch_right_20", "Ease back a little toward the camera.")

        if self.UP_DOWN_PITCH_MIN <= abs(pitch) <= self.UP_DOWN_PITCH_MAX:
            return PoseValidationResult(True, "pose_valid", "Pitch pose accepted. Hold still.")
        if abs(pitch) < self.UP_DOWN_PITCH_MIN:
            return PoseValidationResult(False, "pose_mismatch_up_or_down", "Raise or lower your chin slightly.")
        return PoseValidationResult(False, "pose_mismatch_up_or_down", "Reduce the tilt slightly and hold still.")
