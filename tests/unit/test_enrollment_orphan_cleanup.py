"""Regression tests: a failed sample flush/commit must not leave orphan crop
files in object storage, and the compensation must never touch other files."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

pytest.importorskip("cv2")

from db.schemas.common import REQUIRED_POSES
from db.schemas.enrollment import EnrollmentFrameRequest
from services.recognition.enrollment_service import EnrollmentService
from services.recognition.types import EnrollmentState, QualityResult
from services.storage.object_storage import LocalObjectStorage

FRAME_B64 = "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz"


class FakeSession:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.fail_commit = fail_commit

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("simulated commit failure")

    async def rollback(self) -> None:
        self.rollback_calls += 1


class FakeDeviceRepository:
    async def get_by_code(self, device_code):
        return SimpleNamespace(
            device_code=device_code,
            is_enabled=True,
            det_thresh=0.6,
            det_size_width=320,
            det_size_height=320,
            max_faces=1,
            min_face_width_px=160,
            min_brightness=75.0,
            min_blur_score=90.0,
            liveness_threshold=0.7,
            accepted_per_pose=4,
        )


class FakeSampleRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.added = []

    async def add(self, sample):
        if self.fail:
            raise RuntimeError("simulated flush failure")
        self.added.append(sample)
        return sample


class FakeCache:
    def __init__(self, state: EnrollmentState) -> None:
        self.state = state
        self.set_calls = 0

    async def get_enrollment_state(self, enrollment_session_id):
        return self.state if enrollment_session_id == self.state.enrollment_session_id else None

    async def set_enrollment_state(self, state) -> None:
        self.set_calls += 1
        self.state = state


class FakePipeline:
    async def analyze(self, frame_bytes, det_thresh, det_size, max_faces):
        face = SimpleNamespace(
            bbox=[10.0, 10.0, 90.0, 90.0],
            embedding=np.zeros(512, dtype=np.float32),
            yaw=0.0,
            pitch=0.0,
            roll=0.0,
        )
        return SimpleNamespace(frame=np.zeros((120, 120, 3), dtype=np.uint8), faces=[face])


class FakeLiveness:
    async def score(self, frame) -> float:
        return 0.95


class FakeQualityGate:
    def evaluate(self, **kwargs) -> QualityResult:
        return QualityResult(
            brightness_score=100.0,
            blur_score=120.0,
            contrast_score=45.0,
            overexposed_ratio=0.01,
            underexposed_ratio=0.01,
            liveness_score=0.95,
            face_width_px=180,
            face_center_offset_x=0.0,
            face_center_offset_y=0.0,
            pose_yaw=0.0,
            pose_pitch=0.0,
            pose_roll=0.0,
            pose_valid=True,
            accepted=True,
            reason="accepted",
            ui_hint="ok",
            flags={"exactly_one_face": True},
        )


class FakePoseValidator:
    def validate(self, pose, face):
        return SimpleNamespace(is_valid=True, reason="ok", ui_hint="ok", pose_status="ok", guidance_direction=None)


class FailingDeleteStorage(LocalObjectStorage):
    async def delete_paths(self, paths):
        raise RuntimeError("simulated storage delete failure")


def _make_state(device_code: str = "gate-a01") -> EnrollmentState:
    return EnrollmentState(
        enrollment_session_id=uuid4(),
        person_id=uuid4(),
        student_id="ST-ORPHAN-1",
        full_name="Orphan Test",
        device_code=device_code,
        accepted_counts={pose: 0 for pose in REQUIRED_POSES},
        started_at=datetime.now(timezone.utc),
        rejected_counts={pose: 0 for pose in REQUIRED_POSES},
    )


def _make_service(tmp_path: Path, *, storage=None, sample_repo=None, session=None):
    state = _make_state()
    cache = FakeCache(state)
    service = EnrollmentService(
        session=session or FakeSession(),
        device_repository=FakeDeviceRepository(),
        person_repository=None,
        face_sample_repository=sample_repo if sample_repo is not None else FakeSampleRepository(),
        face_template_repository=None,
        cache=cache,
        pipeline=FakePipeline(),
        liveness_service=FakeLiveness(),
        quality_gate=FakeQualityGate(),
        template_builder=None,
        object_storage=storage or LocalObjectStorage(str(tmp_path)),
        pose_validator=FakePoseValidator(),
    )
    return service, state, cache


def _frame_request(state: EnrollmentState) -> EnrollmentFrameRequest:
    return EnrollmentFrameRequest(
        enrollment_session_id=state.enrollment_session_id,
        device_code=state.device_code,
        pose="front",
        frame_b64=FRAME_B64,
    )


def _stored_files(tmp_path: Path) -> list[Path]:
    return sorted(p for p in tmp_path.rglob("*.jpg") if p.is_file())


def test_failed_sample_flush_removes_orphan_file(tmp_path) -> None:
    service, state, cache = _make_service(tmp_path, sample_repo=FakeSampleRepository(fail=True))

    with pytest.raises(RuntimeError, match="could not be stored"):
        asyncio.run(service.process_frame(_frame_request(state)))

    assert _stored_files(tmp_path) == [], "failed flush must not leave a crop file behind"
    assert service.session.rollback_calls == 1
    assert cache.state.accepted_counts["front"] == 0, "counters must not advance on failure"
    assert cache.set_calls == 0


def test_failed_commit_removes_orphan_file(tmp_path) -> None:
    session = FakeSession(fail_commit=True)
    service, state, cache = _make_service(tmp_path, session=session)

    with pytest.raises(RuntimeError, match="could not be stored"):
        asyncio.run(service.process_frame(_frame_request(state)))

    assert _stored_files(tmp_path) == [], "failed commit must not leave a crop file behind"
    assert session.commit_calls == 1
    assert session.rollback_calls == 1
    assert cache.state.accepted_counts["front"] == 0


def test_compensation_never_touches_other_stored_files(tmp_path) -> None:
    storage = LocalObjectStorage(str(tmp_path))
    preexisting_uri = asyncio.run(storage.put_bytes("enrollment/other-person/existing.jpg", b"keep-me"))
    service, state, _cache = _make_service(tmp_path, storage=storage, sample_repo=FakeSampleRepository(fail=True))

    with pytest.raises(RuntimeError):
        asyncio.run(service.process_frame(_frame_request(state)))

    assert Path(preexisting_uri).is_file(), "compensation must only delete the freshly written crop"
    assert Path(preexisting_uri).read_bytes() == b"keep-me"
    assert _stored_files(tmp_path) == [Path(preexisting_uri)]


def test_successful_frame_keeps_file_and_advances_state(tmp_path) -> None:
    sample_repo = FakeSampleRepository()
    session = FakeSession()
    service, state, cache = _make_service(tmp_path, sample_repo=sample_repo, session=session)

    response = asyncio.run(service.process_frame(_frame_request(state)))

    assert response.accepted is True
    files = _stored_files(tmp_path)
    assert len(files) == 1, "successful sample must keep its crop file"
    assert len(sample_repo.added) == 1
    assert sample_repo.added[0].image_uri == files[0].as_posix()
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert cache.state.accepted_counts["front"] == 1
    assert cache.set_calls == 1


def test_cleanup_failure_still_surfaces_original_error(tmp_path) -> None:
    storage = FailingDeleteStorage(str(tmp_path))
    service, state, _cache = _make_service(tmp_path, storage=storage, sample_repo=FakeSampleRepository(fail=True))

    with pytest.raises(RuntimeError, match="could not be stored") as excinfo:
        asyncio.run(service.process_frame(_frame_request(state)))

    # The original flush failure stays the cause; the delete failure is only logged.
    assert "simulated flush failure" in str(excinfo.value.__cause__)
