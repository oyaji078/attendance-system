from __future__ import annotations

import numpy as np


class TemplateBuilder:
    def build(self, embeddings: list[list[float]]) -> list[float]:
        if not embeddings:
            raise ValueError("cannot build a template from zero embeddings")
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise ValueError("all embeddings must have the same dimension")
        matrix = np.asarray(embeddings, dtype=np.float32)
        normalized = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12, None)
        centroid = normalized.mean(axis=0)
        centroid = centroid / np.clip(np.linalg.norm(centroid), 1e-12, None)
        return centroid.astype(np.float32).tolist()

