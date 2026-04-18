from fastapi import APIRouter

from app.api.routes import admin, attendance, devices, enrollment, recognition

api_router = APIRouter()
api_router.include_router(devices.router, tags=["devices"])
api_router.include_router(enrollment.router, tags=["enrollment"])
api_router.include_router(recognition.router, tags=["recognition"])
api_router.include_router(attendance.router, tags=["attendance"])
api_router.include_router(admin.router, tags=["admin"])

