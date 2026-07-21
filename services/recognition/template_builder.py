from __future__ import annotations

import logging

import numpy as np

LOGGER = logging.getLogger(__name__)

_OUTLIER_THRESHOLD = 0.80


class TemplateBuilder:
    def build(self, embeddings: list[list[float]]) -> list[float]:
        if not embeddings:
            raise ValueError("cannot build a template from zero embeddings")
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise ValueError("all embeddings must have the same dimension")

        matrix = np.asarray(embeddings, dtype=np.float32)
        normalized = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12, None)

        rough_centroid = normalized.mean(axis=0)
        rough_centroid = rough_centroid / np.clip(np.linalg.norm(rough_centroid), 1e-12, None)

        similarities = normalized @ rough_centroid

        min_kept = max(4, len(embeddings) // 2)
        kept_mask = similarities >= _OUTLIER_THRESHOLD
        kept_count = int(kept_mask.sum())

        if kept_count < min_kept:
            filtered = normalized
            removed_count = 0
        else:
            filtered = normalized[kept_mask]
            removed_count = len(embeddings) - kept_count

        if removed_count > 0:
            LOGGER.info(
                "template_outliers_removed",
                extra={
                    "total_embeddings": len(embeddings),
                    "kept_embeddings": kept_count,
                    "removed_embeddings": removed_count,
                },
            )

        final_centroid = filtered.mean(axis=0)
        final_centroid = final_centroid / np.clip(np.linalg.norm(final_centroid), 1e-12, None)
        return final_centroid.astype(np.float32).tolist()
