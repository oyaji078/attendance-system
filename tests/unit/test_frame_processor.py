from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from db.schemas.common import FrameInput
from services.recognition.frame_processor import ProcessedRecognitionFrame, RecognitionFrameProcessor
from services.recognition.types import DetectedFace, FrameAnalysis, LivenessResult, QualityResult


class FakePipeline:
    def __init__(self, faces: list[DetectedFace]) -> None:
        self.faces = faces
        self.analyze_calls = 0

    async def analyze(self, frame_bytes: bytes, det_thresh: float, det_size: tuple[int, int], max_faces: int) -> FrameAnalysis:
        self.analyze_calls += 1
        return FrameAnalysis(frame=np.zeros((100, 100, 3), dtype=np.uint8), faces=self.faces)


class FakeLiveness:
    def __init__(self) -> None:
        self.score_calls = 0

    async def score(self, frame: np.ndarray) -> LivenessResult:
        self.score_calls += 1
        return LivenessResult(score=0.8, mode="passive", implemented=True, details={})


class FakeQualityGate:
    def evaluate(self, frame, faces, max_faces, min_face_width_px, min_brightness, min_blur_score, liveness, liveness_threshold, quality_mode):
        accepted = len(faces) > 0
        return QualityResult(
            brightness_score=100.0,
            blur_score=120.0,
            contrast_score=45.0,
            overexposed_ratio=0.02,
            underexposed_ratio=0.01,
            liveness_score=liveness.score,
            face_width_px=180,
            face_center_offset_x=0.01,
            face_center_offset_y=0.01,
            pose_yaw=0.0,
            pose_pitch=0.0,
            pose_roll=0.0,
            pose_valid=True,
            accepted=accepted,
            reason="accepted" if accepted else "no_face_detected",
            ui_hint="accepted" if accepted else "no_face_detected",
            flags={"exactly_one_face": bool(len(faces) == 1)},
            face_count=len(faces),
        )


class FakeTemplateMatcher:
    async def search(self, embedding: list[float], limit: int = 3, class_id=None) -> list:
        return []

    def decision_for(self, candidates, quality, similarity_threshold):
        from services.recognition.types import RecognitionFrameDecision
        return RecognitionFrameDecision(True, "no_candidates", None, None, None, None, None, None, quality)


def _make_device(**overrides) -> object:
    defaults = {
        "det_thresh": 0.5,
        "det_size_width": 640,
        "det_size_height": 640,
        "max_faces": 1,
        "min_face_width_px": 100,
        "min_brightness": 40.0,
        "min_blur_score": 60.0,
        "liveness_threshold": 0.5,
        "similarity_threshold": 0.35,
    }
    defaults.update(overrides)
    return type("DeviceConfig", (), defaults)()


VALID_B64 = "YUdWc2JBOTBibXN2YVdOeklHTnZiWEJ2Y21WdVkyVnpMMjF6Y0dGdWN5NWpiMjU9"


def test_skips_liveness_when_no_face_detected() -> None:
    pipeline = FakePipeline(faces=[])
    liveness = FakeLiveness()
    processor = RecognitionFrameProcessor(
        pipeline=pipeline,
        liveness_service=liveness,
        quality_gate=FakeQualityGate(),
        template_matcher=FakeTemplateMatcher(),
    )
    result = asyncio.run(processor.process(FrameInput(frame_b64=VALID_B64, pose_hint=None), _make_device()))
    assert liveness.score_calls == 0
    assert result.decision.quality.liveness_score == 0.0


def test_runs_liveness_when_face_detected() -> None:
    face = DetectedFace(
        bbox=(0.1, 0.1, 0.5, 0.5),
        det_score=0.95,
        embedding=[0.1] * 128,
        keypoints=[(0.3, 0.3)],
        pose_yaw=0.0,
        pose_pitch=0.0,
        pose_roll=0.0,
        center_offset_x=0.0,
        center_offset_y=0.0,
        relative_area=0.2,
    )
    pipeline = FakePipeline(faces=[face])
    liveness = FakeLiveness()
    processor = RecognitionFrameProcessor(
        pipeline=pipeline,
        liveness_service=liveness,
        quality_gate=FakeQualityGate(),
        template_matcher=FakeTemplateMatcher(),
    )
    result = asyncio.run(processor.process(FrameInput(frame_b64=VALID_B64, pose_hint=None), _make_device()))
    assert liveness.score_calls == 1
    assert result.decision.quality.liveness_score == 0.8


def test_process_returns_frame_and_face_bbox_on_success() -> None:
    face = DetectedFace(
        bbox=(0.1, 0.2, 0.3, 0.4),
        det_score=0.95,
        embedding=[0.1] * 128,
        keypoints=[(0.3, 0.3)],
        pose_yaw=0.0,
        pose_pitch=0.0,
        pose_roll=0.0,
        center_offset_x=0.0,
        center_offset_y=0.0,
        relative_area=0.2,
    )
    pipeline = FakePipeline(faces=[face])
    processor = RecognitionFrameProcessor(
        pipeline=pipeline,
        liveness_service=FakeLiveness(),
        quality_gate=FakeQualityGate(),
        template_matcher=FakeTemplateMatcher(),
    )
    result = asyncio.run(processor.process(FrameInput(frame_b64=VALID_B64, pose_hint=None), _make_device()))
    assert result.frame is not None
    assert isinstance(result.frame, np.ndarray)
    assert result.face_bbox == (0.1, 0.2, 0.3, 0.4)
    assert result.face_crop_jpeg is None


def test_deferred_lazy_face_crop() -> None:
    from services.recognition.recognition_service import RecognitionService
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    bbox = (0.1, 0.2, 0.3, 0.4)
    pf = ProcessedRecognitionFrame(
        decision=MagicMock(),
        candidates=[],
        frame=frame,
        face_bbox=bbox,
    )
    with patch("services.recognition.face_crop.crop_face_jpeg", return_value=b"fake-jpeg") as mock_crop:
        result = RecognitionService._lazy_face_crop([pf])
        assert result == b"fake-jpeg"
        mock_crop.assert_called_once_with(frame, bbox)


def test_lazy_face_crop_returns_none_when_no_frame_or_bbox() -> None:
    from services.recognition.recognition_service import RecognitionService
    pf = ProcessedRecognitionFrame(
        decision=MagicMock(),
        candidates=[],
        frame=None,
        face_bbox=None,
    )
    result = RecognitionService._lazy_face_crop([pf])
    assert result is None


def test_pipeline_analyze_called_with_correct_args() -> None:
    face = DetectedFace(
        bbox=(0.1, 0.1, 0.5, 0.5),
        det_score=0.95,
        embedding=[0.1] * 128,
        keypoints=[(0.3, 0.3)],
        pose_yaw=0.0,
        pose_pitch=0.0,
        pose_roll=0.0,
        center_offset_x=0.0,
        center_offset_y=0.0,
        relative_area=0.2,
    )
    pipeline = FakePipeline(faces=[face])
    processor = RecognitionFrameProcessor(
        pipeline=pipeline,
        liveness_service=FakeLiveness(),
        quality_gate=FakeQualityGate(),
        template_matcher=FakeTemplateMatcher(),
    )
    asyncio.run(processor.process(FrameInput(frame_b64=VALID_B64, pose_hint=None), _make_device()))
    assert pipeline.analyze_calls == 1
