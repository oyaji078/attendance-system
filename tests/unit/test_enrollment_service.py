from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("cv2")
import numpy as np

from db.schemas.common import REQUIRED_POSES
from db.schemas.enrollment import EnrollmentFinishRequest, EnrollmentFrameRequest
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.enrollment_service import EnrollmentService
from services.recognition.pose_validator import PoseValidator
from services.recognition.template_builder import TemplateBuilder
from services.recognition.types import DetectedFace, EnrollmentState, FrameAnalysis, LivenessResult


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeDeviceRepository:
    def __init__(self, accepted_per_pose: int = 1) -> None:
        self.device = SimpleNamespace(
            code="gate-a01",
            is_enabled=True,
            accepted_per_pose=accepted_per_pose,
            det_thresh=0.5,
            det_size_width=640,
            det_size_height=640,
            max_faces=1,
            min_face_width_px=160,
            min_brightness=75.0,
            min_blur_score=40.0,
            liveness_threshold=0.7,
        )

    async def get_by_code(self, code: str):
        return self.device if code == self.device.code else None


class FakePersonRepository:
    def __init__(self) -> None:
        self.activated = []

    async def activate(self, person_id, template_id) -> None:
        self.activated.append((person_id, template_id))


class FakeFaceSampleRepository:
    def __init__(self) -> None:
        self.samples = []

    async def add(self, sample) -> None:
        self.samples.append(sample)

    async def list_for_enrollment_session(self, enrollment_session_id):
        return [sample for sample in self.samples if sample.enrollment_session_id == enrollment_session_id]

    async def list_for_person(self, person_id):
        return [sample for sample in self.samples if sample.person_id == person_id]


class FakeFaceTemplateRepository:
    async def upsert_active(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)


class FakeCache:
    def __init__(self, state: EnrollmentState) -> None:
        self.state = state

    async def get_enrollment_state(self, enrollment_session_id):
        if self.state and self.state.enrollment_session_id == enrollment_session_id:
            return self.state
        return None

    async def set_enrollment_state(self, state: EnrollmentState) -> None:
        self.state = state

    async def clear_enrollment_state(self, enrollment_session_id) -> None:
        if self.state and self.state.enrollment_session_id == enrollment_session_id:
            self.state = None


class FakePipeline:
    def __init__(self, frame: np.ndarray, face: DetectedFace) -> None:
        self.analysis = FrameAnalysis(frame=frame, faces=[face])

    async def analyze(self, **kwargs) -> FrameAnalysis:
        return self.analysis


class FakeLivenessService:
    async def score(self, frame: np.ndarray) -> LivenessResult:
        return LivenessResult(score=0.96, mode="test", implemented=True, details={})


class FakeObjectStorage:
    async def put_bytes(self, path: str, payload: bytes) -> str:
        return f"memory://{path}"


def valid_frame_payload() -> str:
    return base64.b64encode(b"fake-frame-payload-" * 3).decode("ascii")


def textured_frame() -> np.ndarray:
    rows = np.arange(240, dtype=np.uint16)[:, None]
    cols = np.arange(320, dtype=np.uint16)[None, :]
    base = ((rows * 7 + cols * 11) % 255).astype(np.uint8)
    frame = np.stack([base, np.roll(base, 9, axis=1), np.roll(base, 17, axis=0)], axis=2)
    return frame


def build_face(*, yaw: float, pitch: float = 0.0) -> DetectedFace:
    return DetectedFace(
        bbox=(40.0, 40.0, 240.0, 220.0),
        det_score=0.99,
        embedding=[0.1, 0.2, 0.3],
        keypoints=[],
        pose_yaw=yaw,
        pose_pitch=pitch,
        pose_roll=0.0,
        center_offset_x=0.02,
        center_offset_y=0.01,
        relative_area=0.35,
    )


def build_state() -> EnrollmentState:
    return EnrollmentState(
        enrollment_session_id=uuid4(),
        person_id=uuid4(),
        student_id="ST-1001",
        full_name="Ada Lovelace",
        device_code="gate-a01",
        accepted_counts={pose: 0 for pose in REQUIRED_POSES},
        started_at=datetime.now(timezone.utc),
    )


def build_service(*, frame: np.ndarray, face: DetectedFace, accepted_per_pose: int = 1):
    state = build_state()
    service = EnrollmentService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(accepted_per_pose=accepted_per_pose),
        person_repository=FakePersonRepository(),
        face_sample_repository=FakeFaceSampleRepository(),
        face_template_repository=FakeFaceTemplateRepository(),
        cache=FakeCache(state),
        pipeline=FakePipeline(frame, face),
        liveness_service=FakeLivenessService(),
        quality_gate=QualityGate(),
        template_builder=TemplateBuilder(),
        object_storage=FakeObjectStorage(),
        pose_validator=PoseValidator(),
    )
    return service, state


def test_wrong_pose_does_not_increment_accepted_count() -> None:
    service, state = build_service(frame=textured_frame(), face=build_face(yaw=0.0))
    response = asyncio.run(
        service.process_frame(
            EnrollmentFrameRequest(
                enrollment_session_id=state.enrollment_session_id,
                device_code=state.device_code,
                pose="left_20",
                frame_b64=valid_frame_payload(),
            )
        )
    )
    assert response.accepted is False
    assert response.pose_accepted_count == 0
    assert response.reason == "pose_mismatch_left_20"
    assert state.accepted_counts["left_20"] == 0
    assert len(service.face_sample_repository.samples) == 0


def test_correct_pose_increments_accepted_count() -> None:
    service, state = build_service(frame=textured_frame(), face=build_face(yaw=-18.0))
    response = asyncio.run(
        service.process_frame(
            EnrollmentFrameRequest(
                enrollment_session_id=state.enrollment_session_id,
                device_code=state.device_code,
                pose="left_20",
                frame_b64=valid_frame_payload(),
            )
        )
    )
    assert response.accepted is True
    assert response.pose_accepted_count == 1
    assert state.accepted_counts["left_20"] == 1
    assert len(service.face_sample_repository.samples) == 1


def test_pose_quota_logic_still_blocks_extra_frames() -> None:
    service, state = build_service(frame=textured_frame(), face=build_face(yaw=-18.0), accepted_per_pose=2)
    request = EnrollmentFrameRequest(
        enrollment_session_id=state.enrollment_session_id,
        device_code=state.device_code,
        pose="left_20",
        frame_b64=valid_frame_payload(),
    )
    first = asyncio.run(service.process_frame(request))
    second = asyncio.run(service.process_frame(request))
    third = asyncio.run(service.process_frame(request))
    assert first.accepted is True
    assert second.accepted is True
    assert third.accepted is False
    assert third.reason == "pose_quota_reached"
    assert state.accepted_counts["left_20"] == 2


def test_finish_fails_when_required_pose_counts_are_incomplete() -> None:
    service, state = build_service(frame=textured_frame(), face=build_face(yaw=0.0))
    with pytest.raises(ValueError, match="required pose counts"):
        asyncio.run(service.finish(EnrollmentFinishRequest(enrollment_session_id=state.enrollment_session_id)))
