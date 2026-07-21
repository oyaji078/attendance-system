from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import FaceTemplate
from db.models.vector import normalize_embedding_for_db
from db.repositories.match_queries import FACE_TEMPLATE_ANN_QUERY, FACE_TEMPLATE_CLASS_SCOPED_ANN_QUERY


@dataclass(slots=True)
class TemplateMatch:
    template_id: UUID
    person_id: UUID
    student_id: str
    full_name: str
    class_code: str | None
    class_name: str | None
    distance: float
    email: str | None = None
    class_id: UUID | None = None


class FaceTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_for_person(self, person_id: UUID) -> FaceTemplate | None:
        result = await self.session.execute(
            select(FaceTemplate).where(FaceTemplate.person_id == person_id, FaceTemplate.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_latest_for_person(self, person_id: UUID) -> FaceTemplate | None:
        result = await self.session.execute(
            select(FaceTemplate)
            .where(FaceTemplate.person_id == person_id)
            .order_by(FaceTemplate.version.desc(), FaceTemplate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_person(self, person_id: UUID) -> list[FaceTemplate]:
        result = await self.session.execute(
            select(FaceTemplate)
            .where(FaceTemplate.person_id == person_id)
            .order_by(FaceTemplate.version.desc(), FaceTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def upsert_active(
        self,
        person_id: UUID,
        embedding: list[float],
        sample_count: int,
        built_from_session_id: UUID | None,
        metadata_json: dict[str, object],
    ) -> FaceTemplate:
        normalized_embedding = normalize_embedding_for_db(embedding)
        active_template = await self.get_active_for_person(person_id)
        latest_template = await self.get_latest_for_person(person_id)
        if active_template is not None:
            active_template.is_active = False
        template = FaceTemplate(
            person_id=person_id,
            embedding=normalized_embedding,
            version=1 if latest_template is None else latest_template.version + 1,
            sample_count=sample_count,
            built_from_session_id=built_from_session_id,
            metadata_json=metadata_json,
            is_active=True,
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def search_active(self, query_embedding: list[float], limit: int = 5) -> list[TemplateMatch]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        normalized_embedding = normalize_embedding_for_db(query_embedding)
        await self.session.execute(text("SET LOCAL hnsw.ef_search = 40"))
        result = await self.session.execute(
            text(FACE_TEMPLATE_ANN_QUERY),
            {"query_embedding": normalized_embedding, "k": limit},
        )
        return [
            TemplateMatch(
                template_id=row.template_id,
                person_id=row.person_id,
                student_id=row.student_id,
                full_name=row.full_name,
                email=row.email,
                class_id=row.class_id,
                class_code=row.class_code,
                class_name=row.class_name,
                distance=float(row.distance),
            )
            for row in result
        ]

    async def search_active_for_class(self, query_embedding: list[float], class_id: UUID, limit: int = 5) -> list[TemplateMatch]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        normalized_embedding = normalize_embedding_for_db(query_embedding)
        await self.session.execute(text("SET LOCAL hnsw.ef_search = 40"))
        result = await self.session.execute(
            text(FACE_TEMPLATE_CLASS_SCOPED_ANN_QUERY),
            {"query_embedding": normalized_embedding, "class_id": class_id, "k": limit},
        )
        return [
            TemplateMatch(
                template_id=row.template_id,
                person_id=row.person_id,
                student_id=row.student_id,
                full_name=row.full_name,
                email=row.email,
                class_id=row.class_id,
                class_code=row.class_code,
                class_name=row.class_name,
                distance=float(row.distance),
            )
            for row in result
        ]

    async def total_templates(self) -> int:
        result = await self.session.execute(select(func.count(FaceTemplate.id)))
        return int(result.scalar_one())

    async def reindex_hnsw(self) -> None:
        # REINDEX CONCURRENTLY refuses to run inside a transaction block, so it
        # needs a dedicated autocommit connection instead of the request session.
        engine = self.session.bind
        async with engine.connect() as connection:
            autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(text("REINDEX INDEX CONCURRENTLY idx_face_templates_embedding_hnsw"))

    async def delete_for_person(self, person_id: UUID) -> int:
        result = await self.session.execute(delete(FaceTemplate).where(FaceTemplate.person_id == person_id))
        return int(result.rowcount or 0)

    async def deactivate_for_person(self, person_id: UUID) -> int:
        result = await self.session.execute(
            update(FaceTemplate)
            .where(FaceTemplate.person_id == person_id, FaceTemplate.is_active.is_(True))
            .values(is_active=False, deleted_at=datetime.now(timezone.utc))
        )
        return int(result.rowcount or 0)
