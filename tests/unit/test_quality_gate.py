from __future__ import annotations

import pytest

pytest.importorskip("cv2")
import cv2
import numpy as np

from services.quality.service import QualityGate
from services.recognition.types import DetectedFace, LivenessResult


def test_quality_gate_rejects_dark_frame() -> None:
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    faces = [DetectedFace(bbox=(40.0, 40.0, 240.0, 220.0), det_score=0.99, embedding=[0.1, 0.2, 0.3], keypoints=[], pose_yaw=0.0, pose_pitch=0.0, pose_roll=0.0, center_offset_x=0.0, center_offset_y=0.0, relative_area=0.35)]
    result = QualityGate().evaluate(
        frame=frame,
        faces=faces,
        max_faces=1,
        min_face_width_px=160,
        min_brightness=75.0,
        min_blur_score=0.0,
        liveness=LivenessResult(score=0.95, mode="test", implemented=True, details={}),
        liveness_threshold=0.70,
    )
    assert result.accepted is False
    assert result.reason == "frame_too_dark"


def test_quality_gate_rejects_blurry_frame() -> None:
    pattern = np.indices((240, 320)).sum(axis=0) % 2
    frame = (pattern * 255).astype(np.uint8)
    frame = np.stack([frame, frame, frame], axis=2)
    frame = cv2.GaussianBlur(frame, (31, 31), 0)
    faces = [DetectedFace(bbox=(40.0, 40.0, 240.0, 220.0), det_score=0.99, embedding=[0.1, 0.2, 0.3], keypoints=[], pose_yaw=0.0, pose_pitch=0.0, pose_roll=0.0, center_offset_x=0.0, center_offset_y=0.0, relative_area=0.35)]
    result = QualityGate().evaluate(
        frame=frame,
        faces=faces,
        max_faces=1,
        min_face_width_px=160,
        min_brightness=75.0,
        min_blur_score=80.0,
        liveness=LivenessResult(score=0.95, mode="test", implemented=True, details={}),
        liveness_threshold=0.70,
    )
    assert result.accepted is False
    assert result.reason == "frame_too_blurry"
