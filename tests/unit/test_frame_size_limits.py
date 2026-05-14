from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from db.schemas.common import FrameInput
from db.schemas.enrollment import EnrollmentFrameRequest
from db.schemas.recognition import RecognitionRequest


def _b64(size: int) -> str:
    return base64.b64encode(b"x" * size).decode("ascii")


def test_valid_frame_b64_accepted() -> None:
    frame = FrameInput(frame_b64=_b64(100))
    assert frame.frame_b64


def test_oversized_frame_b64_rejected() -> None:
    oversized = _b64(12_000_000)
    with pytest.raises(ValidationError) as exc:
        FrameInput(frame_b64=oversized)
    assert "frame_b64" in str(exc.value)


def test_invalid_base64_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        FrameInput(frame_b64="!!!invalid-b64!!!")
    assert "frame_b64" in str(exc.value) or "valid base64" in str(exc.value).lower()


def test_empty_frame_b64_rejected() -> None:
    with pytest.raises(ValidationError):
        FrameInput(frame_b64="")


def test_short_frame_b64_rejected() -> None:
    with pytest.raises(ValidationError):
        FrameInput(frame_b64=_b64(1))


def test_too_many_frames_rejected() -> None:
    frames = [FrameInput(frame_b64=_b64(100)) for _ in range(11)]
    with pytest.raises(ValidationError) as exc:
        RecognitionRequest(device_code="gate-a01", frames=frames, session_code=None)
    assert "frames" in str(exc.value)


def test_enrollment_oversized_frame_rejected() -> None:
    oversized = _b64(12_000_000)
    with pytest.raises(ValidationError) as exc:
        EnrollmentFrameRequest(
            enrollment_session_id="00000000-0000-0000-0000-000000000001",
            device_code="gate-a01",
            pose="front",
            frame_b64=oversized,
        )
    assert "frame_b64" in str(exc.value)
