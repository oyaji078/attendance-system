"""Endpoints for the redesigned admin console.

Read-heavy by design: the console's job is to show data the system already
derived (recap, dashboard, monitoring). The only writes here are enrollment —
the Siswa <-> Kelas relation — and the console's own settings.

Recap is deliberately not CRUD: there is no create/update/delete for it, only
views and exports, because a recap is computed from attendance.
"""

from __future__ import annotations

from datetime import date as date_type
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csrf import csrf_dependency
from app.core.dependencies import get_session
from app.api.routes.academic import lecturer_scope_for, require_academic_admin, require_academic_user
from db.models.entities import AdminUser
from db.schemas.console import (
    AttendanceEventListResponse,
    FaceSyncResponse,
    ClassDetailResponse,
    ClassRecapResponse,
    DashboardResponse,
    EnrollmentListResponse,
    EnrollmentRead,
    EnrollmentWrite,
    SettingsPayload,
    SettingsResponse,
    StudentDetailResponse,
)
from services.academic.console import ConsoleNotFoundError, ConsoleService
from services.academic.kiosk_bridge import backfill_from_logs

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/console", dependencies=[Depends(csrf_dependency)], tags=["console"])


def get_console_service(session: AsyncSession = Depends(get_session)) -> ConsoleService:
    return ConsoleService(session)


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> DashboardResponse:
    return await service.dashboard()


@router.get("/attendance", response_model=AttendanceEventListResponse)
async def attendance_events(
    date: date_type | None = None,
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    attendance_status: str | None = Query(default=None, pattern="^[HSIA]$"),
    source: str | None = Query(default=None, pattern="^(face|manual)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> AttendanceEventListResponse:
    items, total = await service.attendance_events(
        on_date=date, class_id=class_id, subject_id=subject_id,
        status=attendance_status, source=source, limit=limit, offset=offset,
    )
    return AttendanceEventListResponse(
        items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total
    )


@router.post("/attendance/sync-face", response_model=FaceSyncResponse)
async def sync_face_attendance(
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> FaceSyncResponse:
    """File past kiosk scans that never reached the recap.

    Scans taken while no pertemuan could be resolved left an audit log but no
    Hadir. This replays them so the recap reflects attendance that was really
    taken. An existing status is never changed; the only thing filled in on a
    row that already exists is a face match score it never got.
    """
    result = await backfill_from_logs(session)
    await session.commit()
    detail = f"{result['recorded']} kehadiran ditarik dari {result['days']} hari absensi wajah."
    if result["scored"]:
        detail += f" {result['scored']} catatan lama dilengkapi akurasi wajahnya."
    if result["skipped_days"]:
        detail += (
            f" {result['skipped_days']} hari dilewati karena sesinya belum terhubung ke jadwal manapun."
        )
    return FaceSyncResponse(**result, detail=detail)


@router.get("/classes/{class_id}", response_model=ClassDetailResponse)
async def class_detail(
    class_id: UUID,
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> ClassDetailResponse:
    try:
        return await service.class_detail(class_id)
    except ConsoleNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/classes/{class_id}/recap", response_model=ClassRecapResponse)
async def class_recap(
    class_id: UUID,
    academic_year: str | None = Query(default=None, max_length=16),
    semester: str | None = Query(default=None, max_length=16),
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> ClassRecapResponse:
    """Summary across every subject of the class — one percentage per subject."""
    try:
        return await service.class_recap(class_id, academic_year=academic_year or None, semester=semester or None)
    except ConsoleNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/students/{person_id}", response_model=StudentDetailResponse)
async def student_detail(
    person_id: UUID,
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> StudentDetailResponse:
    try:
        return await service.student_detail(person_id)
    except ConsoleNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/students/{person_id}/enrollments", response_model=EnrollmentListResponse)
async def list_enrollments(
    person_id: UUID,
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> EnrollmentListResponse:
    items = await service.list_enrollments(person_id)
    return EnrollmentListResponse(items=items, total=len(items))


@router.put("/students/{person_id}/enrollments", response_model=EnrollmentRead)
async def save_enrollment(
    person_id: UUID,
    request: EnrollmentWrite,
    service: ConsoleService = Depends(get_console_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> EnrollmentRead:
    """Place or move a student. The previous enrollment is closed, not deleted."""
    try:
        payload = await service.upsert_enrollment(person_id, request)
        await session.commit()
    except ConsoleNotFoundError as exc:
        raise _not_found(exc) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enrollment siswa ini sedang diubah dari tempat lain. Muat ulang halaman.",
        ) from exc
    return payload


@router.get("/settings", response_model=SettingsResponse)
async def read_settings(
    service: ConsoleService = Depends(get_console_service),
    _: AdminUser = Depends(require_academic_user),
) -> SettingsResponse:
    return await service.get_settings()


@router.put("/settings", response_model=SettingsResponse)
async def write_settings(
    payload: SettingsPayload,
    service: ConsoleService = Depends(get_console_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> SettingsResponse:
    result = await service.save_settings(payload)
    await session.commit()
    return result
