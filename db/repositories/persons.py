from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AttendanceLog, ClassGroup, FaceSample, FaceTemplate, Person


@dataclass(slots=True)
class AdminPersonProjection:
    person: Person
    sample_count: int
    active_template_version: int | None
    last_seen_at: datetime | None
    class_code: str | None
    class_name: str | None


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
                ClassGroup.class_code,
                ClassGroup.class_name,
            )
            .outerjoin(ClassGroup, ClassGroup.id == Person.class_id)
            .outerjoin(
                FaceSample,
                (FaceSample.person_id == Person.id)
                & (FaceSample.is_active.is_(True))
                & (FaceSample.is_deleted.is_(False)),
            )
            .outerjoin(
                FaceTemplate,
                (FaceTemplate.person_id == Person.id)
                & (FaceTemplate.is_active.is_(True))
                & (FaceTemplate.deleted_at.is_(None)),
            )
            .outerjoin(AttendanceLog, AttendanceLog.person_id == Person.id)
            .where(Person.is_deleted.is_(False))
            .group_by(Person.id, ClassGroup.class_code, ClassGroup.class_name)
        )

    async def get_by_student_id(self, student_id: str) -> Person | None:
        result = await self.session.execute(select(Person).where(Person.student_id == student_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, person_id: UUID) -> Person | None:
        result = await self.session.execute(select(Person).where(Person.id == person_id))
        return result.scalar_one_or_none()

    async def get_or_create(self, student_id: str, full_name: str, email: str | None, class_id: UUID | None = None) -> Person:
        person = await self.get_by_student_id(student_id)
        if person is None:
            person = Person(student_id=student_id, full_name=full_name, email=email, class_id=class_id, is_active=False)
            self.session.add(person)
            await self.session.flush()
            return person
        person.full_name = full_name
        person.email = email
        person.class_id = class_id
        person.is_deleted = False
        person.deleted_at = None
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
        result = await self.session.execute(select(Person.id).where(Person.is_active.is_(True), Person.is_deleted.is_(False)))
        return list(result.scalars().all())

    async def admin_projection(self, student_id: str) -> AdminPersonProjection | None:
        result = await self.session.execute(self._admin_projection_statement().where(Person.student_id == student_id))
        row = result.one_or_none()
        if row is None:
            return None
        person, sample_count, active_template_version, last_seen_at, class_code, class_name = row
        return AdminPersonProjection(
            person=person,
            sample_count=sample_count,
            active_template_version=active_template_version,
            last_seen_at=last_seen_at,
            class_code=class_code,
            class_name=class_name,
        )

    async def admin_projection_by_id(self, person_id: UUID) -> AdminPersonProjection | None:
        result = await self.session.execute(self._admin_projection_statement().where(Person.id == person_id))
        row = result.one_or_none()
        if row is None:
            return None
        person, sample_count, active_template_version, last_seen_at, class_code, class_name = row
        return AdminPersonProjection(
            person=person,
            sample_count=sample_count,
            active_template_version=active_template_version,
            last_seen_at=last_seen_at,
            class_code=class_code,
            class_name=class_name,
        )

    async def list_admin_projections(self, limit: int = 25, offset: int = 0) -> list[AdminPersonProjection]:
        result = await self.session.execute(
            self._admin_projection_statement()
            .order_by(Person.created_at.desc(), Person.student_id.asc())
            .offset(offset)
            .limit(limit)
        )
        return [
            AdminPersonProjection(
                person=person,
                sample_count=sample_count,
                active_template_version=active_template_version,
                last_seen_at=last_seen_at,
                class_code=class_code,
                class_name=class_name,
            )
            for person, sample_count, active_template_version, last_seen_at, class_code, class_name in result.all()
        ]

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count(Person.id)).where(Person.is_deleted.is_(False))
        )
        return int(result.scalar_one())

    async def create(
        self,
        student_id: str,
        full_name: str,
        email: str | None,
        class_id: UUID | None = None,
        is_active: bool = False,
        address: str | None = None,
    ) -> Person:
        await self._ensure_student_id_available(student_id)
        person = Person(student_id=student_id, full_name=full_name, email=email, address=address, class_id=class_id, is_active=is_active)
        self.session.add(person)
        await self.session.flush()
        return person

    async def update(
        self,
        person_id: UUID,
        student_id: str,
        full_name: str,
        email: str | None,
        class_id: UUID | None = None,
        address: str | None = None,
    ) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        await self._ensure_student_id_available(student_id, exclude_person_id=person_id)
        person.student_id = student_id
        person.full_name = full_name
        person.email = email
        person.address = address
        person.class_id = class_id
        await self.session.flush()
        return person

    async def deactivate(self, person_id: UUID) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person.is_active = False
        await self.session.flush()
        return person

    async def clear_face_profile(self, person_id: UUID) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person.primary_template_id = None
        await self.session.flush()
        return person

    async def reactivate(self, person_id: UUID) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person.is_active = True
        person.is_deleted = False
        person.deleted_at = None
        await self.session.flush()
        return person

    async def soft_delete(self, person_id: UUID) -> Person:
        person = await self.get_by_id(person_id)
        if person is None:
            raise LookupError(f"person {person_id} not found")
        person.is_active = False
        person.is_deleted = True
        person.deleted_at = datetime.now(timezone.utc)
        person.primary_template_id = None
        await self.session.flush()
        return person

    async def _ensure_student_id_available(self, student_id: str, exclude_person_id: UUID | None = None) -> None:
        existing = await self.get_by_student_id(student_id)
        if existing is None:
            return
        if exclude_person_id is not None and existing.id == exclude_person_id:
            return
        raise ValueError(f"student_id {student_id} already exists")
