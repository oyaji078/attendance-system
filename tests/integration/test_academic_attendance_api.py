"""HTTP contract for the academic attendance routes.

Follows the pattern used by the other integration tests: a bare FastAPI app
carrying only the router under test, with dependencies overridden by fakes, so
no database or Redis is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.academic import router as academic_router
from app.core.dependencies import get_academic_service, get_current_admin_user, get_session
from db.schemas.academic_attendance import (
    AttendanceSheetResponse,
    AttendanceSheetStudent,
    ClassScheduleRead,
    MeetingRead,
    RecapMeetingColumn,
    RecapResponse,
    RecapRow,
)
from services.academic.service import AcademicPermissionError

NOW = datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc)

SCHEDULE_ID = uuid4()
MEETING_ID = uuid4()
LECTURER_ID = uuid4()
OTHER_LECTURER_ID = uuid4()
STUDENT_IDS = [uuid4(), uuid4(), uuid4()]


def make_schedule_read() -> ClassScheduleRead:
    return ClassScheduleRead(
        schedule_id=SCHEDULE_ID,
        schedule_code="JDW-0001",
        class_id=uuid4(),
        class_code="XII-RPL-1",
        class_name="XII RPL 1",
        subject_id=uuid4(),
        subject_code="PWEB-01",
        subject_name="Pemrograman Web",
        lecturer_id=LECTURER_ID,
        lecturer_name="Budi Santoso",
        academic_year="2025/2026",
        semester="ganjil",
        day_of_week="monday",
        total_meetings=12,
        is_active=True,
        student_count=3,
        meeting_count=12,
        held_meeting_count=2,
        created_at=NOW,
        updated_at=NOW,
    )


def make_meeting_read(number: int = 1, status: str = "planned") -> MeetingRead:
    return MeetingRead(
        meeting_id=MEETING_ID,
        schedule_id=SCHEDULE_ID,
        meeting_number=number,
        status=status,
        recorded_count=0,
        present_count=0,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeAcademicService:
    def __init__(self) -> None:
        self.saved: list[dict] = []
        self.last_lecturer_scope: object = "unset"

    async def attendance_sheet(self, meeting_id: UUID, *, lecturer_scope=None):
        self.last_lecturer_scope = lecturer_scope
        if lecturer_scope is not None and lecturer_scope != LECTURER_ID:
            raise AcademicPermissionError("Jadwal ini bukan milik akun guru yang sedang masuk.")
        students = [
            AttendanceSheetStudent(no=1, person_id=STUDENT_IDS[0], student_id="001", full_name="Ahmad"),
            AttendanceSheetStudent(no=2, person_id=STUDENT_IDS[1], student_id="002", full_name="Budi"),
            AttendanceSheetStudent(no=3, person_id=STUDENT_IDS[2], student_id="003", full_name="Citra"),
        ]
        return AttendanceSheetResponse(
            schedule=make_schedule_read(),
            meeting=make_meeting_read(),
            students=students,
            student_count=len(students),
        )

    async def save_attendance(
        self, meeting_id, entries, *, mark_meeting_held=True, recorded_by_admin_id=None, lecturer_scope=None
    ):
        self.last_lecturer_scope = lecturer_scope
        if lecturer_scope is not None and lecturer_scope != LECTURER_ID:
            raise AcademicPermissionError("Jadwal ini bukan milik akun guru yang sedang masuk.")
        self.saved.append(
            {
                "meeting_id": meeting_id,
                "entries": [(entry.person_id, entry.status) for entry in entries],
                "recorded_by_admin_id": recorded_by_admin_id,
            }
        )
        return len(entries), 0, 0

    async def recap(self, schedule_id, *, lecturer_scope=None):
        self.last_lecturer_scope = lecturer_scope
        if lecturer_scope is not None and lecturer_scope != LECTURER_ID:
            raise AcademicPermissionError("Jadwal ini bukan milik akun guru yang sedang masuk.")
        columns = [
            RecapMeetingColumn(meeting_id=uuid4(), meeting_number=n, status="held" if n <= 2 else "planned", label=str(n))
            for n in range(1, 13)
        ]
        rows = [
            RecapRow(
                no=1,
                person_id=STUDENT_IDS[0],
                student_id="001",
                full_name="Ahmad",
                cells=["H", "A"] + [None] * 10,
                hadir=1,
                alpha=1,
                held_meetings=2,
                attendance_percent=50.0,
            )
        ]
        return RecapResponse(
            schedule=make_schedule_read(),
            columns=columns,
            rows=rows,
            student_count=1,
            total_meetings=12,
            held_meetings=2,
            average_percent=50.0,
        )

    async def list_schedules(self, **kwargs):
        self.last_lecturer_scope = kwargs.get("lecturer_scope")
        return [make_schedule_read()]

    async def list_meetings(self, schedule_id, *, lecturer_scope=None):
        self.last_lecturer_scope = lecturer_scope
        return make_schedule_read(), [make_meeting_read()]

    async def generate_meetings(self, schedule_id, *, total_meetings=None, lecturer_scope=None):
        self.last_lecturer_scope = lecturer_scope
        count = total_meetings or 12
        return make_schedule_read(), [make_meeting_read(number=n) for n in range(1, count + 1)]


class FakeSession:
    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def get(self, *args, **kwargs):
        return object()

    async def execute(self, *args, **kwargs):
        class Result:
            def scalars(self):
                return SimpleNamespace(all=lambda: [])

        return Result()


def build_client(role: str = "admin", lecturer_id: UUID | None = None):
    app = FastAPI()
    app.include_router(academic_router)
    service = FakeAcademicService()

    user = SimpleNamespace(id=uuid4(), role=role, lecturer_id=lecturer_id, username="tester")
    app.dependency_overrides[get_academic_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: FakeSession()
    return TestClient(app), service, user


def test_sheet_returns_every_student_of_the_class():
    client, _, _ = build_client()
    response = client.get(f"/academic/meetings/{MEETING_ID}/attendance")
    assert response.status_code == 200
    body = response.json()
    assert body["student_count"] == 3
    assert [row["full_name"] for row in body["students"]] == ["Ahmad", "Budi", "Citra"]
    assert body["status_labels"] == {"H": "Hadir", "S": "Sakit", "I": "Izin", "A": "Alpha"}


def test_save_accepts_hsia_and_reports_counts():
    client, service, user = build_client()
    payload = {
        "entries": [
            {"person_id": str(STUDENT_IDS[0]), "status": "H"},
            {"person_id": str(STUDENT_IDS[1]), "status": "S"},
            {"person_id": str(STUDENT_IDS[2]), "status": "A"},
        ]
    }
    response = client.put(f"/academic/meetings/{MEETING_ID}/attendance", json=payload)
    assert response.status_code == 200
    assert response.json()["created"] == 3
    # The signed-in account is recorded as the author of the entry.
    assert service.saved[0]["recorded_by_admin_id"] == user.id


def test_save_normalizes_word_statuses():
    client, service, _ = build_client()
    payload = {"entries": [{"person_id": str(STUDENT_IDS[0]), "status": "hadir"}]}
    assert client.put(f"/academic/meetings/{MEETING_ID}/attendance", json=payload).status_code == 200
    assert service.saved[0]["entries"][0][1] == "H"


def test_save_rejects_unknown_status():
    client, _, _ = build_client()
    payload = {"entries": [{"person_id": str(STUDENT_IDS[0]), "status": "X"}]}
    assert client.put(f"/academic/meetings/{MEETING_ID}/attendance", json=payload).status_code == 422


def test_save_rejects_duplicate_student_in_one_payload():
    client, service, _ = build_client()
    payload = {
        "entries": [
            {"person_id": str(STUDENT_IDS[0]), "status": "H"},
            {"person_id": str(STUDENT_IDS[0]), "status": "A"},
        ]
    }
    assert client.put(f"/academic/meetings/{MEETING_ID}/attendance", json=payload).status_code == 422
    assert service.saved == []


def test_save_rejects_empty_payload():
    client, _, _ = build_client()
    assert client.put(f"/academic/meetings/{MEETING_ID}/attendance", json={"entries": []}).status_code == 422


def test_recap_exposes_counts_and_percentage():
    client, _, _ = build_client()
    body = client.get(f"/academic/schedules/{SCHEDULE_ID}/recap").json()
    assert len(body["columns"]) == 12
    assert body["held_meetings"] == 2
    row = body["rows"][0]
    assert row["hadir"] == 1 and row["alpha"] == 1
    assert row["attendance_percent"] == 50.0
    # Meetings 3..12 have not happened: no status, and not counted as Alpha.
    assert row["cells"][2:] == [None] * 10


def test_admin_is_not_scoped_to_a_lecturer():
    client, service, _ = build_client(role="admin")
    client.get(f"/academic/schedules/{SCHEDULE_ID}/recap")
    assert service.last_lecturer_scope is None


def test_lecturer_is_scoped_to_own_schedules():
    client, service, _ = build_client(role="lecturer", lecturer_id=LECTURER_ID)
    assert client.get(f"/academic/meetings/{MEETING_ID}/attendance").status_code == 200
    assert service.last_lecturer_scope == LECTURER_ID


def test_lecturer_cannot_open_another_lecturers_class():
    client, _, _ = build_client(role="lecturer", lecturer_id=OTHER_LECTURER_ID)
    assert client.get(f"/academic/meetings/{MEETING_ID}/attendance").status_code == 403


def test_lecturer_cannot_save_into_another_lecturers_class():
    client, service, _ = build_client(role="lecturer", lecturer_id=OTHER_LECTURER_ID)
    payload = {"entries": [{"person_id": str(STUDENT_IDS[0]), "status": "H"}]}
    assert client.put(f"/academic/meetings/{MEETING_ID}/attendance", json=payload).status_code == 403
    assert service.saved == []


def test_lecturer_without_linked_lecturer_record_is_refused():
    # Scope would otherwise fall back to None and grant admin-wide visibility.
    client, _, _ = build_client(role="lecturer", lecturer_id=None)
    assert client.get(f"/academic/meetings/{MEETING_ID}/attendance").status_code == 403


def test_operator_role_has_no_access():
    client, _, _ = build_client(role="operator")
    assert client.get(f"/academic/schedules").status_code == 403


def test_lecturer_cannot_create_master_data():
    client, _, _ = build_client(role="lecturer", lecturer_id=LECTURER_ID)
    response = client.post("/academic/subjects", json={"subject_name": "Matematika"})
    assert response.status_code == 403


def test_generate_meetings_defaults_to_schedule_total():
    client, _, _ = build_client()
    body = client.post(f"/academic/schedules/{SCHEDULE_ID}/meetings/generate", json={}).json()
    assert body["total"] == 12
    assert [item["meeting_number"] for item in body["items"]] == list(range(1, 13))


def test_generate_meetings_accepts_a_custom_count():
    client, _, _ = build_client()
    body = client.post(f"/academic/schedules/{SCHEDULE_ID}/meetings/generate", json={"total_meetings": 16}).json()
    assert body["total"] == 16


def test_generate_meetings_rejects_absurd_counts():
    client, _, _ = build_client()
    response = client.post(f"/academic/schedules/{SCHEDULE_ID}/meetings/generate", json={"total_meetings": 500})
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Jadwal + Sesi Absensi merged into one menu
# --------------------------------------------------------------------------- #


def test_schedule_read_exposes_its_kiosk_session():
    # The merged Jadwal view renders the session straight from the schedule row,
    # so these fields have to survive the response contract.
    client, _, _ = build_client()
    body = client.get(f"/academic/schedules/{SCHEDULE_ID}/recap").json()
    schedule = body["schedule"]
    for field in ("attendance_session_id", "session_code", "session_name", "session_is_active"):
        assert field in schedule, field


def test_guru_cannot_create_a_kiosk_session():
    client, _, _ = build_client(role="lecturer", lecturer_id=LECTURER_ID)
    assert client.post(f"/academic/schedules/{SCHEDULE_ID}/session", json={}).status_code == 403


def test_guru_cannot_toggle_a_kiosk_session():
    client, _, _ = build_client(role="lecturer", lecturer_id=LECTURER_ID)
    assert client.patch(f"/academic/schedules/{SCHEDULE_ID}/session/activate").status_code == 403
    assert client.patch(f"/academic/schedules/{SCHEDULE_ID}/session/deactivate").status_code == 403


def test_operator_cannot_touch_kiosk_sessions():
    client, _, _ = build_client(role="operator")
    assert client.post(f"/academic/schedules/{SCHEDULE_ID}/session", json={}).status_code == 403
