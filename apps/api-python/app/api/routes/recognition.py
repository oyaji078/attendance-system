import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_recognition_service
from app.core.rate_limiter import rate_limit_ml_dependency
from db.schemas.recognition import RecognitionRequest, RecognitionResponse
from services.recognition.recognition_service import RecognitionService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.post("/recognize", response_model=RecognitionResponse)
async def recognize(
    request: RecognitionRequest,
    service: RecognitionService = Depends(get_recognition_service),
    _: None = Depends(rate_limit_ml_dependency),
) -> RecognitionResponse:
    try:
        return await service.recognize(request, event_type="recognition_attempt", require_session=False)
    except LookupError as exc:
        LOGGER.warning("recognize_lookup_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data perangkat tidak ditemukan.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("recognize_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengenali wajah. Coba ulangi.") from exc
