from __future__ import annotations

from dataclasses import dataclass

from db.models.entities import DeviceConfig
from db.repositories.face_templates import FaceTemplateRepository, TemplateMatch
from db.schemas.common import FrameInput
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.frame_codec import decode_frame_b64
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.types import QualityResult, RecognitionFrameDecision


class TemplateMatcher:
    def __init__(self, template_repository: FaceTemplateRepository) -> None:
        self.template_repository = template_repository

    async def search(self, embedding: list[float], limit: int = 3) -> list[TemplateMatch]:
        return await self.template_repository.search_active(embedding, limit=limit)

    @staticmethod
    def decision_for(candidates: list[TemplateMatch], quality: QualityResult, similarity_threshold: float) -> RecognitionFrameDecision:
        if not candidates:
            return RecognitionFrameDecision(True, "no_candidates", None, None, None, None, None, None, quality)
        top = candidates[0]
        if top.distance > similarity_threshold:
            return RecognitionFrameDecision(
                True,
                "distance_above_threshold",
                None,
                None,
                None,
                None,
                top.distance,
                max(0.0, 1.0 - top.distance),
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
            max(0.0, 1.0 - top.distance),
            quality,
        )


@dataclass(slots=True)
class ProcessedRecognitionFrame:
    decision: RecognitionFrameDecision
    candidates: list[TemplateMatch]


class RecognitionFrameProcessor:
    def __init__(
        self,
        pipeline: InsightFaceEmbeddingPipeline,
        liveness_service: HeuristicPassiveLivenessService,
        quality_gate: QualityGate,
        template_matcher: TemplateMatcher,
    ) -> None:
        self.pipeline = pipeline
        self.liveness_service = liveness_service
        self.quality_gate = quality_gate
        self.template_matcher = template_matcher

    async def process(self, frame_input: FrameInput, device: DeviceConfig) -> ProcessedRecognitionFrame:
        analysis = await self.pipeline.analyze(
            frame_bytes=decode_frame_b64(frame_input.frame_b64),
            det_thresh=device.det_thresh,
            det_size=(device.det_size_width, device.det_size_height),
            max_faces=device.max_faces,
        )
        liveness = await self.liveness_service.score(analysis.frame)
        quality = self.quality_gate.evaluate(
            frame=analysis.frame,
            faces=analysis.faces,
            max_faces=device.max_faces,
            min_face_width_px=device.min_face_width_px,
            min_brightness=device.min_brightness,
            min_blur_score=device.min_blur_score,
            liveness=liveness,
            liveness_threshold=device.liveness_threshold,
        )
        if not quality.accepted:
            return ProcessedRecognitionFrame(
                decision=RecognitionFrameDecision(False, quality.reason, None, None, None, None, None, None, quality),
                candidates=[],
            )
        candidates = await self.template_matcher.search(analysis.faces[0].embedding, limit=3)
        return ProcessedRecognitionFrame(
            decision=self.template_matcher.decision_for(candidates, quality, device.similarity_threshold),
            candidates=candidates,
        )
