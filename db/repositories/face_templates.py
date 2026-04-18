from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import FaceTemplate, VECTOR_DIMENSION
from db.repositories.match_queries import FACE_TEMPLATE_ANN_QUERY


@dataclass(slots=True)
class TemplateMatch:
    template_id: UUID
    person_id: UUID
    student_id: str
    full_name: str
    distance: float


class FaceTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_for_person(self, person_id: UUID) -> FaceTemplate | None:
        result = await self.session.execute(
            select(FaceTemplate).where(FaceTemplate.person_id == person_id, FaceTemplate.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def upsert_active(
        self,
        person_id: UUID,
        embedding: list[float],
        sample_count: int,
        built_from_session_id: UUID | None,
        metadata_json: dict[str, object],
    ) -> FaceTemplate:
        template = await self.get_active_for_person(person_id)
        if template is None:
            template = FaceTemplate(
                person_id=person_id,
                embedding=embedding,
                version=1,
                sample_count=sample_count,
                built_from_session_id=built_from_session_id,
                metadata_json=metadata_json,
                is_active=True,
            )
            self.session.add(template)
        else:
            template.embedding = embedding
            template.version += 1
            template.sample_count = sample_count
            template.built_from_session_id = built_from_session_id
            template.metadata_json = metadata_json
        await self.session.flush()
        return template

    async def search_active(self, query_embedding: list[float], limit: int = 5) -> list[TemplateMatch]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if len(query_embedding) != VECTOR_DIMENSION:
            raise ValueError(f"query embedding must have dimension {VECTOR_DIMENSION}")
        result = await self.session.execute(
            text(FACE_TEMPLATE_ANN_QUERY),
            {"query_embedding": self._to_vector_literal(query_embedding), "k": limit},
        )
        return [
            TemplateMatch(
                template_id=row.template_id,
                person_id=row.person_id,
                student_id=row.student_id,
                full_name=row.full_name,
                distance=float(row.distance),
            )
            for row in result
        ]

    async def total_templates(self) -> int:
        result = await self.session.execute(select(func.count(FaceTemplate.id)))
        return int(result.scalar_one())

    async def reindex_hnsw(self) -> None:
        await self.session.execute(text("REINDEX INDEX face_templates_embedding_hnsw_idx"))

    @staticmethod
    def _to_vector_literal(embedding: list[float]) -> str:
        return "[" + ",".join(f"{value:.10f}" for value in embedding) + "]"
