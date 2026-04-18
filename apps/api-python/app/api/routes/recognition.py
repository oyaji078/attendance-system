from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_recognition_service
from db.schemas.recognition import RecognitionRequest, RecognitionResponse
from services.recognition.recognition_service import RecognitionService

router = APIRouter()


@router.post("/recognize", response_model=RecognitionResponse)
async def recognize(request: RecognitionRequest, service: RecognitionService = Depends(get_recognition_service)) -> RecognitionResponse:
    try:
        return await service.recognize(request, event_type="recognize", require_session=False)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

