from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter

import numpy as np

from db.models.entities import DeviceConfig
from db.repositories.face_templates import FaceTemplateRepository, TemplateMatch
from db.schemas.common import FrameInput
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.face_crop import crop_face_jpeg
from services.recognition.frame_codec import decode_frame_b64
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.types import LivenessResult, QualityResult, RecognitionFrameDecision

LOGGER = logging.getLogger(__name__)


class TemplateMatcher:
    def __init__(self, template_repository: FaceTemplateRepository, confidence_threshold: float = 0.55) -> None:
        self.template_repository = template_repository
        self.confidence_threshold = confidence_threshold

    async def search(self, embedding: list[float], limit: int = 3, class_id=None) -> list[TemplateMatch]:
        if class_id is not None:
            return await self.template_repository.search_active_for_class(embedding, class_id, limit=limit)
        return await self.template_repository.search_active(embedding, limit=limit)

    def decision_for(self, candidates: list[TemplateMatch], quality: QualityResult, similarity_threshold: float) -> RecognitionFrameDecision:
        if not candidates:
            return RecognitionFrameDecision(True, "no_candidates", None, None, None, None, None, None, quality)
        top = candidates[0]
        confidence = max(0.0, 1.0 - top.distance)
        if top.distance > similarity_threshold:
            return RecognitionFrameDecision(
                True,
                "distance_above_threshold",
                None,
                None,
                None,
                None,
                top.distance,
                confidence,
                quality,
            )
        if confidence < self.confidence_threshold:
            return RecognitionFrameDecision(
                True,
                "confidence_below_threshold",
                None,
                None,
                None,
                None,
                top.distance,
                confidence,
                quality,
            )
        return RecognitionFrameDecision(
            True,
            "match_candidate",
            top.person_id,
            top.template_id,
            top.student_id,
            top.full_name,
            top.distance,
            confidence,
            quality,
        )


@dataclass(slots=True)
class ProcessedRecognitionFrame:
    decision: RecognitionFrameDecision
    candidates: list[TemplateMatch]
    frame: np.ndarray | None = None
    face_bbox: tuple[float, float, float, float] | None = None
    face_crop_jpeg: bytes | None = None


class RecognitionFrameProcessor:
    def __init__(
        self,
        pipeline: InsightFaceEmbeddingPipeline,
        liveness_service: HeuristicPassiveLivenessService,
        quality_gate: QualityGate,
        template_matcher: TemplateMatcher,
        quality_mode: str = "normal",
    ) -> None:
        self.pipeline = pipeline
        self.liveness_service = liveness_service
        self.quality_gate = quality_gate
        self.template_matcher = template_matcher
        self.quality_mode = quality_mode

    async def process(self, frame_input: FrameInput, device: DeviceConfig, class_id=None) -> ProcessedRecognitionFrame:
        started_at = perf_counter()
        pipeline_started_at = perf_counter()
        analysis = await self.pipeline.analyze(
            frame_bytes=decode_frame_b64(frame_input.frame_b64),
            det_thresh=device.det_thresh,
            det_size=(device.det_size_width, device.det_size_height),
            max_faces=device.max_faces,
        )
        pipeline_ms = (perf_counter() - pipeline_started_at) * 1000.0
        liveness_started_at = perf_counter()
        if not analysis.faces:
            liveness = LivenessResult(score=0.0, mode="skipped_no_faces", implemented=True, details={})
        else:
            liveness = await self.liveness_service.score(analysis.frame)
        liveness_ms = (perf_counter() - liveness_started_at) * 1000.0
        quality_started_at = perf_counter()
        quality_thresholds = self._quality_thresholds(device)
        quality = self.quality_gate.evaluate(
            frame=analysis.frame,
            faces=analysis.faces,
            max_faces=device.max_faces,
            min_face_width_px=quality_thresholds["min_face_width_px"],
            min_brightness=quality_thresholds["min_brightness"],
            min_blur_score=quality_thresholds["min_blur_score"],
            liveness=liveness,
            liveness_threshold=quality_thresholds["liveness_threshold"],
            quality_mode=self.quality_mode,
        )
        quality_ms = (perf_counter() - quality_started_at) * 1000.0
        if not quality.accepted:
            LOGGER.info(
                "recognition_frame_processed",
                extra={
                    "accepted": False,
                    "reason": quality.reason,
                    "pipeline_ms": round(pipeline_ms, 2),
                    "liveness_ms": round(liveness_ms, 2),
                    "quality_ms": round(quality_ms, 2),
                    "vector_search_ms": 0.0,
                    "total_ms": round((perf_counter() - started_at) * 1000.0, 2),
                },
            )
            return ProcessedRecognitionFrame(
                decision=RecognitionFrameDecision(False, quality.reason, None, None, None, None, None, None, quality),
                candidates=[],
            )
        search_started_at = perf_counter()
        candidates = await self.template_matcher.search(analysis.faces[0].embedding, limit=3, class_id=class_id)
        search_ms = (perf_counter() - search_started_at) * 1000.0
        decision = self.template_matcher.decision_for(candidates, quality, device.similarity_threshold)
        LOGGER.info(
            "recognition_frame_processed",
            extra={
                "accepted": True,
                "reason": decision.reason,
                "pipeline_ms": round(pipeline_ms, 2),
                "liveness_ms": round(liveness_ms, 2),
                "quality_ms": round(quality_ms, 2),
                "vector_search_ms": round(search_ms, 2),
                "candidate_count": len(candidates),
                "total_ms": round((perf_counter() - started_at) * 1000.0, 2),
            },
        )
        return ProcessedRecognitionFrame(
            decision=decision,
            candidates=candidates,
            frame=analysis.frame,
            face_bbox=analysis.faces[0].bbox,
        )

    def _quality_thresholds(self, device: DeviceConfig) -> dict[str, float | int]:
        thresholds: dict[str, float | int] = {
            "min_face_width_px": device.min_face_width_px,
            "min_brightness": device.min_brightness,
            "min_blur_score": device.min_blur_score,
            "liveness_threshold": device.liveness_threshold,
        }
        if self.quality_mode == "local_fast":
            thresholds["min_face_width_px"] = min(device.min_face_width_px, 140)
            thresholds["min_blur_score"] = min(device.min_blur_score, 75.0)
        elif self.quality_mode == "strict":
            thresholds["min_face_width_px"] = max(device.min_face_width_px, 160)
            thresholds["min_blur_score"] = max(device.min_blur_score, 90.0)
            thresholds["liveness_threshold"] = max(device.liveness_threshold, 0.7)
        return thresholds
