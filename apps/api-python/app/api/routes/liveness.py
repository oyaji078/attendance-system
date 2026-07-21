from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.dependencies import get_container
from app.core.rate_limiter import rate_limit_ml_dependency
from db.schemas.liveness import ChallengeRequest, ChallengeResponse, ChallengeVerifyRequest, ChallengeVerifyResponse
from services.liveness.color_challenge import ColorChallengeService

router = APIRouter(tags=["liveness"])
LOGGER = logging.getLogger(__name__)


def get_challenge_service(request: Request) -> ColorChallengeService:
    container = get_container(request)
    if not hasattr(container, "challenge_service") or container.challenge_service is None:
        cache = getattr(container, "cache", None)
        container.challenge_service = ColorChallengeService(cache=cache)
    return container.challenge_service


@router.post("/liveness/challenge", response_model=ChallengeResponse)
async def request_challenge(
    body: ChallengeRequest,
    service: ColorChallengeService = Depends(get_challenge_service),
    _: None = Depends(rate_limit_ml_dependency),
) -> ChallengeResponse:
    try:
        challenge = await service.generate(body.device_code)
        return ChallengeResponse(
            challenge_id=challenge.challenge_id,
            color_key=challenge.color_key,
            color_label=challenge.color_label,
            display_rgb=challenge.display_rgb,
            expires_at_seconds=int(challenge.expires_at - time.time()),
        )
    except Exception as exc:
        LOGGER.exception("liveness_challenge_generation_failed", extra={"device_code": body.device_code, "error_type": type(exc).__name__})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "challenge_failed", "message": "Tantangan liveness gagal dibuat."}) from exc


@router.post("/liveness/verify", response_model=ChallengeVerifyResponse)
async def verify_challenge(
    body: ChallengeVerifyRequest,
    service: ColorChallengeService = Depends(get_challenge_service),
    _: None = Depends(rate_limit_ml_dependency),
) -> ChallengeVerifyResponse:
    try:
        result = await service.verify(body.challenge_id, body.frame_b64)
        return ChallengeVerifyResponse(
            challenge_id=body.challenge_id,
            passed=result.passed,
            liveness_score=result.liveness_score,
            reason=result.reason,
            remaining_attempts=result.remaining_attempts,
            color_present_ratio=result.color_present_ratio,
        )
    except Exception as exc:
        LOGGER.exception(
            "liveness_challenge_verification_failed",
            extra={"challenge_id": body.challenge_id, "device_code": body.device_code, "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "verify_failed", "message": "Verifikasi tantangan gagal."}) from exc
