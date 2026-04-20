from __future__ import annotations

from services.recognition.pose_validator import PoseValidator
from services.recognition.types import DetectedFace


def build_face(*, yaw: float = 0.0, pitch: float = 0.0, center_x: float = 0.0, center_y: float = 0.0) -> DetectedFace:
    return DetectedFace(
        bbox=(40.0, 40.0, 240.0, 220.0),
        det_score=0.99,
        embedding=[0.1, 0.2, 0.3],
        keypoints=[],
        pose_yaw=yaw,
        pose_pitch=pitch,
        pose_roll=0.0,
        center_offset_x=center_x,
        center_offset_y=center_y,
        relative_area=0.32,
    )


def test_pose_validator_accepts_matching_left_pose() -> None:
    result = PoseValidator().validate("left_20", build_face(yaw=-18.0, pitch=2.0))
    assert result.is_valid is True
    assert result.reason == "pose_valid"


def test_pose_validator_rejects_pose_mismatch() -> None:
    result = PoseValidator().validate("right_20", build_face(yaw=-16.0, pitch=1.0))
    assert result.is_valid is False
    assert result.reason == "pose_mismatch_right_20"


def test_pose_validator_rejects_off_center_face() -> None:
    result = PoseValidator().validate("front", build_face(center_x=0.31))
    assert result.is_valid is False
    assert result.reason == "face_not_centered"
