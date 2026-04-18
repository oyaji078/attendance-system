from __future__ import annotations

from db.repositories.match_queries import FACE_TEMPLATE_ANN_QUERY


def test_ann_query_targets_face_templates_only() -> None:
    normalized = " ".join(FACE_TEMPLATE_ANN_QUERY.lower().split())
    assert "from face_templates as ft" in normalized
    assert "order by ft.embedding <=> cast(:query_embedding as vector(512))" in normalized
    assert "from face_samples" not in normalized

