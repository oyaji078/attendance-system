from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AttendanceLog, FaceSample, FaceTemplate, Person


@dataclass(slots=True)
class AdminPersonProjection:
    person: Person
    sample_count: int
    active_template_version: int | None
    last_seen_at: datetime | None


class PersonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _admin_projection_statement():
        return (
            select(
                Person,
                func.count(func.distinct(FaceSample.id)).label("sample_count"),
                func.max(FaceTemplate.version).label("active_template_version"),
                func.max(AttendanceLog.created_at).label("last_seen_at"),
            )
            .outerjoin(FaceSample, FaceSample.person_id == Person.id)
            .outerjoin(FaceTemplate, (FaceTemplate.person_id == Person.id) & (FaceTemplate.is_active.is_(True)))
            .outerjoin(AttendanceLog, AttendanceLog.person_id == Person.id)
            .group_by(Person.id)
        )

    async def get_by_student_id(self, student_id: str) -> Person | None:
        result = await self.session.execute(select(Person).where(Person.student_id == student_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, person_id: UUID) -> Person | None:
        result = await self.session.execute(select(Person).where(Person.id == person_id))
        return result.scalar_one_or_none()

    async def get_or_create(self, student_id: str, full_name: str, email: str | None) -> Person:
        person = await self.get_by_student_id(student_id)
        if person is None:
            person = Person(student_id=student_id, full_name=full_name, email=email, is_active=False)
            self.session.add(person)
            await self.session.flush()
            return person
        person.full_name = full_name
        person.email = email
        await self.session.flush()
        return person

    async def activate(self, person_id: UUID, template_id: UUID) -> None:
        person = await self.get_by_id(person_id)
        if person is None:
            raise ValueError(f"person {person_id} not found")
        person.is_active = True
        person.primary_template_id = template_id
        await self.session.flush()

    async def list_active_person_ids(self) -> list[UUID]:
        result = await self.session.execute(select(Person.id).where(Person.is_active.is_(True)))
        return list(result.scalars().all())

    async def admin_projection(self, student_id: str) -> AdminPersonProjection | None:
        result = await self.session.execute(self._admin_projection_statement().where(Person.student_id == student_id))
        row = result.one_or_none()
        if row is None:
            return None
        person, sample_count, active_template_version, last_seen_at = row
        return AdminPersonProjection(
            person=person,
            sample_count=sample_count,
            active_template_version=active_template_version,
            last_seen_at=last_seen_at,
        )

    async def admin_projection_by_id(self, person_id: UUID) -> AdminPersonProjection | None:
        result = await self.session.execute(self._admin_projection_statement().where(Person.id == person_id))
        row = result.one_or_none()
        if row is None:
            return None
        person, sample_count, active_template_version, last_seen_at = row
        return AdminPersonProjection(
            person=person,
            sample_count=sample_count,
            active_template_version=active_template_version,
            last_seen_at=last_seen_at,
        )

    async def list_admin_projections(self) -> list[AdminPersonProjection]:
        result = await self.session.execute(self._admin_projection_statement().order_by(Person.created_at.desc(), Person.student_id.asc()))
        return [
            AdminPersonProjection(
                person=person,
                sample_count=sample_count,
                active_template_version=active_template_version,
                last_seen_at=last_seen_at,
            )
            for person, sample_count, active_template_version, last_seen_at in result.all()
        ]

    async def create(self, student_id: str, full_name: str, email: str | None, is_active: bool = False) -> Person:
        await self._ensure_student_id_available(student_id)
        person = Person(student_id=student_id, full_name=full_name, email=email, is_active=is_active)
        self.session.add(person)
        await self.session.flush()
        return person

    async def update(self, person_id: UUID, student_id: str, full_name: str, email: str | None) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        await self._ensure_student_id_available(student_id, exclude_person_id=person_id)
        person.student_id = student_id
        person.full_name = full_name
        person.email = email
        await self.session.flush()
        return person

    async def deactivate(self, person_id: UUID) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person.is_active = False
        await self.session.flush()
        return person

    async def reactivate(self, person_id: UUID) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person.is_active = True
        await self.session.flush()
        return person

    async def _ensure_student_id_available(self, student_id: str, exclude_person_id: UUID | None = None) -> None:
        existing = await self.get_by_student_id(student_id)
        if existing is None:
            return
        if exclude_person_id is not None and existing.id == exclude_person_id:
            return
        raise ValueError(f"student_id {student_id} already exists")
