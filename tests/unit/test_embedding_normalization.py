from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from db.models.vector import AsyncpgVector, normalize_embedding_for_db


def test_normalize_embedding_flattens_numpy_values() -> None:
    embedding = normalize_embedding_for_db(np.asarray([[0.1, 0.2, 0.3]], dtype=np.float32), dimension=3)

    assert embedding == pytest.approx([0.1, 0.2, 0.3])
    assert all(isinstance(value, float) for value in embedding)


def test_normalize_embedding_rejects_string_literals() -> None:
    with pytest.raises(ValueError, match="must not be a string"):
        normalize_embedding_for_db("[0.1, 0.2, 0.3]", dimension=3)


def test_normalize_embedding_validates_dimension() -> None:
    with pytest.raises(ValueError, match="512-d"):
        normalize_embedding_for_db([0.1, 0.2, 0.3])


def test_asyncpg_vector_bind_keeps_value_numeric() -> None:
    dialect = SimpleNamespace(name="postgresql", driver="asyncpg")
    processor = AsyncpgVector(3).bind_processor(dialect)

    value = processor([0.1, 0.2, 0.3])

    assert isinstance(value, list)
    assert value == pytest.approx([0.1, 0.2, 0.3])
