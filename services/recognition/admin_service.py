from __future__ import annotations

import logging

from db.repositories.attendance import AttendanceRepository
from db.repositories.face_samples import FaceSampleRepository
from db.repositories.face_templates import FaceTemplateRepository
from db.repositories.metrics import MetricsRepository
from db.repositories.persons import PersonRepository
from db.schemas.admin import AdminMetricsResponse, AdminPersonResponse
from db.schemas.persons import PersonCreateRequest, PersonRead, PersonUpdateRequest
from services.recognition.template_builder import TemplateBuilder

LOGGER = logging.getLogger(__name__)


class PersonConflictError(ValueError):
    pass


class AdminService:
    def __init__(
        self,
        person_repository: PersonRepository,
        sample_repository: FaceSampleRepository,
        template_repository: FaceTemplateRepository,
        attendance_repository: AttendanceRepository,
        metrics_repository: MetricsRepository,
        template_builder: TemplateBuilder,
    ) -> None:
        self.person_repository = person_repository
        self.sample_repository = sample_repository
        self.template_repository = template_repository
        self.attendance_repository = attendance_repository
        self.metrics_repository = metrics_repository
        self.template_builder = template_builder

    async def reindex(self) -> None:
        await self.template_repository.reindex_hnsw()
        LOGGER.info("hnsw_reindexed")

    async def rebuild_all_templates(self) -> int:
        rebuilt = 0
        for person_id in await self.person_repository.list_active_person_ids():
            samples = await self.sample_repository.list_for_person(person_id)
            if not samples:
                continue
            await self.template_repository.upsert_active(
                person_id=person_id,
                embedding=self.template_builder.build([sample.embedding for sample in samples]),
                sample_count=len(samples),
                built_from_session_id=samples[-1].enrollment_session_id,
                metadata_json={"rebuilt_by": "admin"},
            )
            rebuilt += 1
        LOGGER.info("templates_rebuilt", extra={"rebuilt_count": rebuilt})
        return rebuilt

    async def metrics(self) -> AdminMetricsResponse:
        total_persons, active_persons = await self.metrics_repository.person_counts()
        attendance_metrics = await self.attendance_repository.metrics()
        return AdminMetricsResponse(
            total_persons=total_persons,
            active_persons=active_persons,
            total_templates=await self.template_repository.total_templates(),
            total_samples=await self.metrics_repository.sample_count(),
            total_logs=attendance_metrics["total_logs"],
            recognized_last_24h=attendance_metrics["recognized_last_24h"],
        )

    async def person_detail(self, student_id: str) -> AdminPersonResponse | None:
        projection = await self.person_repository.admin_projection(student_id)
        if projection is None:
            return None
        return AdminPersonResponse(
            person_id=projection.person.id,
            student_id=projection.person.student_id,
            full_name=projection.person.full_name,
            is_active=projection.person.is_active,
            primary_template_id=projection.person.primary_template_id,
            sample_count=projection.sample_count,
            active_template_version=projection.active_template_version,
            last_seen_at=projection.last_seen_at,
        )

    async def list_persons(self) -> list[PersonRead]:
        return [self._person_read(projection) for projection in await self.person_repository.list_admin_projections()]

    async def get_person(self, person_id) -> PersonRead | None:
        projection = await self.person_repository.admin_projection_by_id(person_id)
        if projection is None:
            return None
        return self._person_read(projection)

    async def create_person(self, request: PersonCreateRequest) -> PersonRead:
        try:
            person = await self.person_repository.create(
                student_id=request.student_id,
                full_name=request.full_name,
                email=request.email,
                is_active=request.is_active,
            )
        except ValueError as exc:
            raise PersonConflictError(str(exc)) from exc
        projection = await self.person_repository.admin_projection_by_id(person.id)
        if projection is None:
            raise LookupError(f"person {person.id} not found after create")
        return self._person_read(projection)

    async def update_person(self, person_id, request: PersonUpdateRequest) -> PersonRead:
        try:
            person = await self.person_repository.update(
                person_id=person_id,
                student_id=request.student_id,
                full_name=request.full_name,
                email=request.email,
            )
        except ValueError as exc:
            raise PersonConflictError(str(exc)) from exc
        projection = await self.person_repository.admin_projection_by_id(person.id)
        if projection is None:
            raise LookupError(f"person {person.id} not found after update")
        return self._person_read(projection)

    async def deactivate_person(self, person_id) -> PersonRead:
        person = await self.person_repository.deactivate(person_id)
        projection = await self.person_repository.admin_projection_by_id(person.id)
        if projection is None:
            raise LookupError(f"person {person.id} not found after deactivate")
        return self._person_read(projection)

    async def reactivate_person(self, person_id) -> PersonRead:
        person = await self.person_repository.reactivate(person_id)
        projection = await self.person_repository.admin_projection_by_id(person.id)
        if projection is None:
            raise LookupError(f"person {person.id} not found after reactivate")
        return self._person_read(projection)

    @staticmethod
    def _person_read(projection) -> PersonRead:
        return PersonRead(
            person_id=projection.person.id,
            student_id=projection.person.student_id,
            full_name=projection.person.full_name,
            email=projection.person.email,
            is_active=projection.person.is_active,
            primary_template_id=projection.person.primary_template_id,
            sample_count=projection.sample_count,
            active_template_version=projection.active_template_version,
            last_seen_at=projection.last_seen_at,
            created_at=projection.person.created_at,
            updated_at=projection.person.updated_at,
        )
