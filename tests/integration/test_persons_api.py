from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin import router as admin_router
from app.core.dependencies import get_admin_service, get_session, require_admin
from services.recognition.admin_service import PersonConflictError


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeSession:
    async def commit(self) -> None:
        return None

    async def refresh(self, _: object) -> None:
        return None


class InMemoryAdminService:
    def __init__(self) -> None:
        self.person_id = uuid4()
        self.template_id = uuid4()
        self.people: dict[UUID, dict[str, object]] = {
            self.person_id: {
                "person_id": self.person_id,
                "student_id": "ST-1001",
                "full_name": "Ada Lovelace",
                "email": "ada@example.edu",
                "class_id": None,
                "class_code": None,
                "class_name": None,
                "is_active": True,
                "primary_template_id": self.template_id,
                "sample_count": 3,
                "active_template_version": 2,
                "last_seen_at": _now(),
                "created_at": _now(),
                "updated_at": _now(),
            }
        }
        self.history: dict[UUID, dict[str, object]] = {
            self.person_id: {
                "sample_count": 3,
                "last_seen_at": self.people[self.person_id]["last_seen_at"],
                "log_ids": [str(uuid4())],
            }
        }

    async def count_persons(self) -> int:
        return len(self.people)

    async def list_persons(self, limit: int = 25, offset: int = 0) -> list[dict[str, object]]:
        return list(self.people.values())[offset:offset + limit]

    async def get_person(self, person_id: UUID) -> dict[str, object] | None:
        return self.people.get(person_id)

    async def create_person(self, request) -> dict[str, object]:
        if any(person["student_id"] == request.student_id for person in self.people.values()):
            raise Exception("student_id already exists")
        person_id = uuid4()
        payload = {
            "person_id": person_id,
            "student_id": request.student_id,
            "full_name": request.full_name,
            "email": request.email,
            "class_id": request.class_id,
            "class_code": None,
            "class_name": None,
            "is_active": request.is_active,
            "primary_template_id": None,
            "sample_count": 0,
            "active_template_version": None,
            "last_seen_at": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.people[person_id] = payload
        self.history[person_id] = {"sample_count": 0, "last_seen_at": None, "log_ids": []}
        return payload

    async def update_person(self, person_id: UUID, request) -> dict[str, object]:
        person = self.people.get(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        if any(other["student_id"] == request.student_id and other_id != person_id for other_id, other in self.people.items()):
            raise Exception(f"student_id {request.student_id} already exists")
        person["student_id"] = request.student_id
        person["full_name"] = request.full_name
        person["email"] = request.email
        person["class_id"] = request.class_id
        person["updated_at"] = _now()
        return person

    async def deactivate_person(self, person_id: UUID) -> dict[str, object]:
        person = self.people.get(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person["is_active"] = False
        person["sample_count"] = self.history[person_id]["sample_count"]
        person["last_seen_at"] = self.history[person_id]["last_seen_at"]
        person["updated_at"] = _now()
        return person

    async def reactivate_person(self, person_id: UUID) -> dict[str, object]:
        person = self.people.get(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person["is_active"] = True
        person["sample_count"] = self.history[person_id]["sample_count"]
        person["last_seen_at"] = self.history[person_id]["last_seen_at"]
        person["updated_at"] = _now()
        return person

    async def person_detail(self, student_id: str):
        for person in self.people.values():
            if person["student_id"] == student_id:
                return {
                    "person_id": person["person_id"],
                    "student_id": person["student_id"],
                    "full_name": person["full_name"],
                    "is_active": person["is_active"],
                    "primary_template_id": person["primary_template_id"],
                    "sample_count": person["sample_count"],
                    "active_template_version": person["active_template_version"],
                    "last_seen_at": person["last_seen_at"],
                }
        return None

    async def reindex(self) -> None:
        return None

    async def rebuild_all_templates(self) -> int:
        return 0

    async def metrics(self):
        return {
            "total_persons": len(self.people),
            "active_persons": sum(1 for person in self.people.values() if person["is_active"]),
            "total_templates": 1,
            "total_samples": 3,
            "total_logs": 1,
            "recognized_last_24h": 1,
        }


class FakeConflictAdminService(InMemoryAdminService):
    async def create_person(self, request):
        raise PersonConflictError(f"student_id {request.student_id} already exists")

    async def update_person(self, person_id: UUID, request):
        raise PersonConflictError(f"student_id {request.student_id} already exists")


def build_app(service: InMemoryAdminService) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_admin_service] = lambda: service
    app.dependency_overrides[require_admin] = lambda: True

    async def override_session():
        yield FakeSession()

    app.dependency_overrides[get_session] = override_session
    return app


def test_persons_crud_flow() -> None:
    service = InMemoryAdminService()
    client = TestClient(build_app(service))

    listed = client.get("/admin/persons")
    created = client.post("/admin/persons", json={"student_id": "ST-2002", "full_name": "Grace Hopper", "email": "grace@example.edu", "is_active": False})
    created_id = created.json()["person_id"]
    fetched = client.get(f"/admin/persons/{created_id}")
    updated = client.put(f"/admin/persons/{created_id}", json={"student_id": "ST-2002A", "full_name": "Grace Brewster Hopper", "email": "grace.b@example.edu"})
    deactivated = client.patch(f"/admin/persons/{created_id}/deactivate")
    reactivated = client.patch(f"/admin/persons/{created_id}/reactivate")

    assert listed.status_code == 200
    assert created.status_code == 201
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["student_id"] == "ST-2002A"
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True


def test_person_student_id_conflict_returns_409() -> None:
    client = TestClient(build_app(FakeConflictAdminService()))

    created = client.post("/admin/persons", json={"student_id": "ST-1001", "full_name": "Collision", "email": None, "is_active": False})
    updated = client.put(f"/admin/persons/{uuid4()}", json={"student_id": "ST-1001", "full_name": "Collision Update", "email": None})

    assert created.status_code == 409
    assert updated.status_code == 409


def test_deactivation_preserves_historical_data() -> None:
    service = InMemoryAdminService()
    client = TestClient(build_app(service))

    before = client.get(f"/admin/persons/{service.person_id}")
    deactivated = client.patch(f"/admin/persons/{service.person_id}/deactivate")
    after = client.get(f"/admin/persons/{service.person_id}")

    assert before.status_code == 200
    assert deactivated.status_code == 200
    assert after.status_code == 200
    assert after.json()["sample_count"] == before.json()["sample_count"]
    assert after.json()["last_seen_at"] == before.json()["last_seen_at"]
    assert after.json()["primary_template_id"] == before.json()["primary_template_id"]


def test_old_log_references_remain_valid_after_deactivation() -> None:
    service = InMemoryAdminService()
    client = TestClient(build_app(service))

    detail_before = client.get(f"/admin/persons/{service.person_id}")
    deactivated = client.patch(f"/admin/persons/{service.person_id}/deactivate")
    detail_after = client.get(f"/admin/persons/{service.person_id}")

    assert deactivated.status_code == 200
    assert detail_after.status_code == 200
    assert detail_after.json()["person_id"] == detail_before.json()["person_id"]
    assert detail_after.json()["last_seen_at"] == detail_before.json()["last_seen_at"]
    assert service.history[service.person_id]["log_ids"]
