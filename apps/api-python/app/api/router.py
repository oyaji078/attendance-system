from fastapi import APIRouter

from app.api.routes import academic, admin, attendance, auth, console, devices, enrollment, liveness, recognition

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(devices.router, tags=["devices"])
api_router.include_router(enrollment.router, tags=["enrollment"])
api_router.include_router(recognition.router, tags=["recognition"])
api_router.include_router(attendance.router, tags=["attendance"])
api_router.include_router(liveness.router)
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(academic.router)
api_router.include_router(console.router)
