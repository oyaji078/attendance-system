"""HTTP contract for the console routes.

Same pattern as the other integration tests: a bare app carrying only the
router under test, with the service and session replaced by fakes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.console import get_console_service, router as console_router
from app.core.dependencies import get_current_admin_user, get_session
from db.schemas.console import (
    ClassRecapResponse,
    ClassRecapRow,
    ClassRecapSubject,
    DashboardMetric,
    DashboardResponse,
    EnrollmentRead,
    SettingsResponse,
)
from services.academic.console import ConsoleNotFoundError

NOW = datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc)
CLASS_ID = uuid4()
PERSON_ID = uuid4()
SUBJECT_ID = uuid4()


class FakeConsoleService:
    def __init__(self) -> None:
        self.saved = []
        self.missing = False

    async def dashboard(self):
        return DashboardResponse(
            metrics=[DashboardMetric(key="students", label="Total Siswa", value=42)],
            today_present=10, today_absent=2, today_total=12, activity=[], generated_at=NOW,
        )

    async def class_recap(self, class_id, *, academic_year=None, semester=None):
        if self.missing:
            raise ConsoleNotFoundError("Kelas tidak ditemukan.")
        return ClassRecapResponse(
            class_id=class_id, class_code="X-IPA-1", class_name="X IPA 1",
            academic_year=academic_year, semester=semester,
            subjects=[
                ClassRecapSubject(schedule_id=uuid4(), subject_id=SUBJECT_ID, subject_name="Matematika", held_meetings=4, total_meetings=16),
                ClassRecapSubject(schedule_id=uuid4(), subject_id=uuid4(), subject_name="Fisika", held_meetings=0, total_meetings=16),
            ],
            rows=[
                ClassRecapRow(no=1, person_id=PERSON_ID, student_id="00123", full_name="Ahmad",
                              percents=[75.0, None], average_percent=75.0),
            ],
            student_count=1, average_percent=75.0,
        )

    async def upsert_enrollment(self, person_id, request):
        self.saved.append((person_id, request.class_id, request.status))
        return EnrollmentRead(
            enrollment_id=uuid4(), person_id=person_id, class_id=request.class_id,
            class_code="X-IPA-1", class_name="X IPA 1", status=request.status,
            start_date=request.start_date, end_date=None, note=request.note,
            created_at=NOW, updated_at=NOW,
        )

    async def list_enrollments(self, person_id):
        return []

    async def get_settings(self):
        return SettingsResponse(school_name="SMPN 1 Selong", updated_at=NOW)

    async def save_settings(self, payload):
        return SettingsResponse(**payload.model_dump(), updated_at=NOW)


class FakeSession:
    async def commit(self):
        return None

    async def rollback(self):
        return None


def build_client(role: str = "admin", lecturer_id=None):
    app = FastAPI()
    app.include_router(console_router)
    service = FakeConsoleService()
    user = SimpleNamespace(id=uuid4(), role=role, lecturer_id=lecturer_id, username="tester")
    app.dependency_overrides[get_console_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: FakeSession()
    return TestClient(app), service


def test_dashboard_returns_metrics():
    client, _ = build_client()
    body = client.get("/console/dashboard").json()
    assert body["metrics"][0]["label"] == "Total Siswa"
    assert body["today_total"] == 12


def test_class_recap_is_a_summary_without_meeting_columns():
    client, _ = build_client()
    body = client.get(f"/console/classes/{CLASS_ID}/recap").json()
    # One percentage per subject — never P1..Pn, which belongs to the other recap.
    assert [s["subject_name"] for s in body["subjects"]] == ["Matematika", "Fisika"]
    assert body["rows"][0]["percents"] == [75.0, None]
    assert "columns" not in body


def test_class_recap_reports_untaught_subject_as_no_data():
    client, _ = build_client()
    body = client.get(f"/console/classes/{CLASS_ID}/recap").json()
    fisika_index = 1
    assert body["subjects"][fisika_index]["held_meetings"] == 0
    # None, not 0.0: nothing has been held, so there is no attendance to report.
    assert body["rows"][0]["percents"][fisika_index] is None


def test_class_recap_missing_class_is_404():
    client, service = build_client()
    service.missing = True
    assert client.get(f"/console/classes/{CLASS_ID}/recap").status_code == 404


def test_recap_has_no_create_update_or_delete_routes():
    client, _ = build_client()
    # A recap is computed from attendance; it is never edited directly.
    assert client.post(f"/console/classes/{CLASS_ID}/recap", json={}).status_code == 405
    assert client.put(f"/console/classes/{CLASS_ID}/recap", json={}).status_code == 405
    assert client.delete(f"/console/classes/{CLASS_ID}/recap").status_code == 405


def test_enrollment_move_is_recorded():
    client, service = build_client()
    response = client.put(
        f"/console/students/{PERSON_ID}/enrollments",
        json={"class_id": str(CLASS_ID), "status": "active", "start_date": "2026-08-01"},
    )
    assert response.status_code == 200
    assert service.saved == [(PERSON_ID, CLASS_ID, "active")]


def test_guru_can_read_but_not_change_enrollment():
    client, _ = build_client(role="lecturer", lecturer_id=uuid4())
    assert client.get(f"/console/students/{PERSON_ID}/enrollments").status_code == 200
    assert (
        client.put(
            f"/console/students/{PERSON_ID}/enrollments",
            json={"class_id": str(CLASS_ID), "status": "active"},
        ).status_code
        == 403
    )


def test_guru_can_read_but_not_write_settings():
    client, _ = build_client(role="lecturer", lecturer_id=uuid4())
    assert client.get("/console/settings").status_code == 200
    assert client.put("/console/settings", json={"school_name": "Nakal"}).status_code == 403


def test_operator_is_locked_out_of_the_console():
    client, _ = build_client(role="operator")
    assert client.get("/console/dashboard").status_code == 403
    assert client.get(f"/console/classes/{CLASS_ID}/recap").status_code == 403


def test_attendance_status_filter_rejects_unknown_codes():
    client, _ = build_client()
    # Only H/S/I/A are attendance statuses; anything else is a malformed query.
    assert client.get("/console/attendance?attendance_status=Z").status_code == 422
    assert client.get("/console/attendance?source=telepathy").status_code == 422
