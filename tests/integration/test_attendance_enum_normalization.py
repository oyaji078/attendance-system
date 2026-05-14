from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin import router as admin_router
from app.core.dependencies import get_attendance_session_service, get_session, require_admin
from db.repositories.attendance import AttendanceSessionProjection
from services.attendance.session_service import AttendanceSessionService


class CountResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class RowsResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows

    def one(self):
        return self.rows[0]


class FakeSessionProjectionRepository:
    def __init__(self, session_kind: str) -> None:
        now = datetime.now(timezone.utc)
        session = SimpleNamespace(
            id=uuid4(),
            session_code="LEGACY-001",
            session_name="Legacy Class",
            session_kind=session_kind,
            class_id=None,
            lecturer_id=None,
            device_code="gate-a01",
            is_active=True,
            is_deleted=True,
            cooldown_seconds=30,
            starts_at=None,
            ends_at=None,
            created_at=now,
            updated_at=now,
            deleted_at=now,
        )
        self.projection = AttendanceSessionProjection(
            session=session,
            total_logs=0,
            recognized=0,
            cooldown=0,
            unknown=0,
            last_event_at=None,
        )

    async def list_session_projections(self, *, include_deleted: bool = False):
        return [self.projection]


class FakeAttendanceLogSession:
    def __init__(self, *, decision: str = "recognized", reason: str = "multi_frame_confirm_passed", count_first: bool = True) -> None:
        self.log = SimpleNamespace(
            id=uuid4(),
            decision=decision,
            reason=reason,
            confidence=0.91,
            device_code="gate-a01",
            event_type="checkin",
            captured_image_uri=None,
            created_at=datetime.now(timezone.utc),
            is_deleted=False,
        )
        self.person = SimpleNamespace(student_id="ST-1001", full_name="Ada Lovelace", email="ada@example.edu")
        self.attendance_session = SimpleNamespace(session_code="LEGACY-001")
        self.class_group = SimpleNamespace(class_code="CS101", class_name="Computer Science")
        self.count_first = count_first
        self.execute_calls = 0
        self.committed = False

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.count_first and self.execute_calls == 1:
            return CountResult(1)
        return RowsResult([(self.log, self.person, self.attendance_session, self.class_group)])

    async def get(self, _model, log_id):
        return self.log if str(log_id) == str(self.log.id) else None

    async def commit(self) -> None:
        self.committed = True


def build_app(*, attendance_service=None, db_session=None) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[require_admin] = lambda: True
    if attendance_service is not None:
        app.dependency_overrides[get_attendance_session_service] = lambda: attendance_service
    if db_session is not None:
        async def override_session():
            yield db_session

        app.dependency_overrides[get_session] = override_session
    return app


def test_admin_attendance_sessions_normalizes_legacy_class(caplog) -> None:
    service = AttendanceSessionService(FakeSessionProjectionRepository("class"))
    client = TestClient(build_app(attendance_service=service), raise_server_exceptions=False)

    response = client.get("/admin/attendance-sessions?include_deleted=true")

    assert response.status_code == 200
    assert response.json()["items"][0]["session_kind"] == "lecture"
    assert "ValidationError" not in caplog.text


@pytest.mark.parametrize(
    ("stored_decision", "stored_reason", "expected_decision", "expected_reason"),
    [
        ("recognized", "multi_frame_confirm_passed", "accepted", "multi_frame_confirm_passed"),
        ("cooldown", "person_on_cooldown", "rejected", "cooldown"),
    ],
)
def test_admin_attendance_logs_normalizes_legacy_decisions(
    stored_decision: str,
    stored_reason: str,
    expected_decision: str,
    expected_reason: str,
    caplog,
) -> None:
    db_session = FakeAttendanceLogSession(decision=stored_decision, reason=stored_reason)
    client = TestClient(build_app(db_session=db_session), raise_server_exceptions=False)

    response = client.get("/admin/attendance-logs")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["decision"] == expected_decision
    assert item["reason"] == expected_reason
    assert "ValidationError" not in caplog.text


@pytest.mark.parametrize("manual_decision", ["manual_approved", "manual_rejected"])
def test_admin_attendance_log_manual_decisions_still_work(manual_decision: str) -> None:
    db_session = FakeAttendanceLogSession(decision="rejected", reason="no_match_within_threshold", count_first=False)
    client = TestClient(build_app(db_session=db_session), raise_server_exceptions=False)

    response = client.patch(
        f"/admin/attendance-logs/{db_session.log.id}",
        json={"decision": manual_decision, "reason": "manual_override"},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == manual_decision
    assert response.json()["reason"] == "manual_override"
    assert db_session.log.decision == manual_decision
    assert db_session.committed is True

