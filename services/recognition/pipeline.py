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
        frame_height, frame_width = frame.shape[:2]
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
                    keypoints=[(float(point[0]), float(point[1])) for point in getattr(face, "kps", [])],
                    pose_yaw=float(self._safe_pose_component(face, 0)),
                    pose_pitch=float(self._safe_pose_component(face, 1)),
                    pose_roll=float(self._safe_pose_component(face, 2)),
                    center_offset_x=float(self._center_offset_x(face.bbox, frame_width)),
                    center_offset_y=float(self._center_offset_y(face.bbox, frame_height)),
                    relative_area=float(self._relative_area(face.bbox, frame_width, frame_height)),
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

    @staticmethod
    def _safe_pose_component(face: object, index: int) -> float:
        pose = getattr(face, "pose", None)
        if pose is None:
            return 0.0
        try:
            return float(pose[index])
        except (IndexError, TypeError, ValueError):
            return 0.0

    @staticmethod
    def _center_offset_x(bbox: object, frame_width: int) -> float:
        center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
        return 0.0 if frame_width <= 0 else ((center_x / frame_width) - 0.5) * 2.0

    @staticmethod
    def _center_offset_y(bbox: object, frame_height: int) -> float:
        center_y = (float(bbox[1]) + float(bbox[3])) / 2.0
        return 0.0 if frame_height <= 0 else ((center_y / frame_height) - 0.5) * 2.0

    @staticmethod
    def _relative_area(bbox: object, frame_width: int, frame_height: int) -> float:
        if frame_width <= 0 or frame_height <= 0:
            return 0.0
        width = max(0.0, float(bbox[2]) - float(bbox[0]))
        height = max(0.0, float(bbox[3]) - float(bbox[1]))
        return (width * height) / float(frame_width * frame_height)
