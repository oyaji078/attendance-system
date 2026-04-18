from __future__ import annotations

import asyncio
import logging
import threading
from functools import lru_cache
from typing import TYPE_CHECKING

import cv2
import numpy as np
import onnxruntime as ort

from services.recognition.types import DetectedFace, FrameAnalysis

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis

LOGGER = logging.getLogger(__name__)


class InsightFaceEmbeddingPipeline:
    def __init__(self, model_name: str, model_root: str, providers: list[str]) -> None:
        self.model_name = model_name
        self.model_root = model_root
        self.providers = providers
        self._lock = threading.Lock()

    async def analyze(self, frame_bytes: bytes, det_thresh: float, det_size: tuple[int, int], max_faces: int) -> FrameAnalysis:
        return await asyncio.to_thread(self._analyze_sync, frame_bytes, det_thresh, det_size, max_faces)

    def _analyze_sync(self, frame_bytes: bytes, det_thresh: float, det_size: tuple[int, int], max_faces: int) -> FrameAnalysis:
        frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("unable to decode frame bytes")
        analyzer = self._get_analyzer(det_thresh, det_size)
        with self._lock:
            faces = analyzer.get(frame, max_num=max_faces)
        return FrameAnalysis(
            frame=frame,
            faces=[
                DetectedFace(
                    bbox=tuple(float(value) for value in face.bbox),
                    det_score=float(face.det_score),
                    embedding=face.embedding.astype(np.float32).tolist(),
                )
                for face in faces
            ],
        )

    @lru_cache(maxsize=8)
    def _get_analyzer(self, det_thresh: float, det_size: tuple[int, int]) -> "FaceAnalysis":
        from insightface.app import FaceAnalysis

        available = set(ort.get_available_providers())
        providers = [provider for provider in self.providers if provider in available]
        if not providers:
            raise RuntimeError(f"none of the configured ONNX Runtime providers are available: {self.providers}")
        LOGGER.info("insightface_pipeline_initialized", extra={"det_thresh": det_thresh, "det_size": det_size, "providers": providers})
        analyzer = FaceAnalysis(name=self.model_name, root=self.model_root, providers=providers)
        analyzer.prepare(ctx_id=0 if "CUDAExecutionProvider" in providers else -1, det_thresh=det_thresh, det_size=det_size)
        return analyzer

