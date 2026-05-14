from __future__ import annotations

import math
from typing import Any

import numpy as np
from pgvector.sqlalchemy import Vector as PgVectorType

VECTOR_DIMENSION = 512


def normalize_embedding_for_db(value: Any, dimension: int | None = VECTOR_DIMENSION) -> list[float]:
    """Return a flat Python float list suitable for pgvector inserts."""
    if isinstance(value, str | bytes | bytearray):
        raise ValueError("Embedding must not be a string")

    source = value.to_numpy() if hasattr(value, "to_numpy") else value
    try:
        array = np.asarray(source, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ValueError("embedding must contain only numeric values") from exc

    if array.ndim == 0:
        raise ValueError("embedding must be a one-dimensional numeric vector")

    flattened = array.reshape(-1)
    if dimension is not None and flattened.size != dimension:
        raise ValueError(f"Expected {dimension}-d embedding, got {flattened.size}")

    embedding = [float(item) for item in flattened.tolist()]
    if not all(math.isfinite(item) for item in embedding):
        raise ValueError("embedding must contain only finite numeric values")

    return embedding


class AsyncpgVector(PgVectorType):
    """pgvector SQLAlchemy type that keeps asyncpg binary binds numeric.

    pgvector's stock SQLAlchemy type serializes bound values to a text literal
    like "[0.1,0.2]". This app registers pgvector's asyncpg binary codec on
    each connection, so asyncpg must receive the original numeric vector value.
    """

    cache_ok = True

    def bind_processor(self, dialect: Any):
        if dialect.name == "postgresql" and dialect.driver == "asyncpg":
            dim = self.dim

            def process(value: Any) -> list[float] | None:
                if value is None:
                    return None
                return normalize_embedding_for_db(value, dim)

            return process

        return super().bind_processor(dialect)
