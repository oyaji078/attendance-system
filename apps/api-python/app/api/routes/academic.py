"""Jadwal, pertemuan, and manual H/S/I/A attendance endpoints.

Separate router from ``admin`` on purpose: ``/admin/*`` is admin-only and stays
that way, while these routes also admit a ``lecturer`` account so a guru can run
Login -> Jadwal -> Buka Absensi -> Simpan without an admin doing it for them.

Authorization model:

* master data (mata pelajaran, jadwal) — admin only for writes, readable by guru
* pertemuan + input absensi + rekap — admin, or the guru who owns the schedule

Scoping is enforced in the service layer via ``lecturer_scope``; the routes only
decide which value to pass.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from io import BytesIO
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csrf import csrf_dependency
from app.core.dependencies import get_academic_service, get_current_admin_user, get_session
from db.domain.attendance import ATTENDANCE_SUCCESS_DECISIONS
from db.models.entities import AdminUser, AttendanceLog, ClassGroup, Subject
from db.schemas.academic_attendance import (
    ATTENDANCE_STATUS_LABELS,
    AttendancePrefillResponse,
    AttendanceSaveRequest,
    AttendanceSaveResponse,
    AttendanceSheetResponse,
    ClassScheduleListResponse,
    ClassScheduleRead,
    ClassScheduleWrite,
    KioskSessionRequest,
    MeetingGenerateRequest,
    MeetingListResponse,
    MeetingRead,
    MeetingWrite,
    RecapFilterOptions,
    RecapResponse,
    ScheduleDeleteResponse,
    SubjectListResponse,
    SubjectRead,
    SubjectWrite,
)
from services.academic.branding import Branding, load_branding
from services.academic.service import (
    AcademicNotFoundError,
    AcademicPermissionError,
    AcademicService,
)

LOGGER = logging.getLogger(__name__)

WITA_TZ = timezone(timedelta(hours=8))

router = APIRouter(prefix="/academic", dependencies=[Depends(csrf_dependency)], tags=["academic"])

SUBJECT_CONFLICT = "Kode mata pelajaran sudah digunakan."
SCHEDULE_CONFLICT = "Jadwal untuk kelas, mata pelajaran, dan periode ini sudah ada."


def require_academic_user(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
    """Admins and lecturers may use the attendance features; operators may not."""
    if user.role not in {"admin", "lecturer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses admin atau guru diperlukan.")
    return user


def require_academic_admin(user: AdminUser = Depends(require_academic_user)) -> AdminUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hanya admin yang dapat mengubah data master.")
    return user


def lecturer_scope_for(user: AdminUser) -> UUID | None:
    """``None`` for admins (see everything), own lecturer id for a guru.

    A lecturer account without a linked ``lecturer_id`` would otherwise be scoped
    to ``None`` and silently gain admin-wide visibility, so that is rejected.
    """
    if user.role != "lecturer":
        return None
    if user.lecturer_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun guru ini belum terhubung ke data guru. Hubungi admin.",
        )
    return user.lecturer_id


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, AcademicNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, AcademicPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --------------------------------------------------------------------------- #
# Mata pelajaran
# --------------------------------------------------------------------------- #


@router.get("/subjects", response_model=SubjectListResponse)
async def list_subjects(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: AcademicService = Depends(get_academic_service),
    _: AdminUser = Depends(require_academic_user),
) -> SubjectListResponse:
    items, total = await service.list_subjects(limit=limit, offset=offset)
    return SubjectListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(
    request: SubjectWrite,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> SubjectRead:
    # The unique index fires on flush inside the service, not only on commit, so
    # both have to sit inside the same guard or a duplicate surfaces as a 500.
    try:
        payload = await service.create_subject(request)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SUBJECT_CONFLICT) from exc
    return payload


@router.put("/subjects/{subject_id}", response_model=SubjectRead)
async def update_subject(
    subject_id: UUID,
    request: SubjectWrite,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> SubjectRead:
    try:
        payload = await service.update_subject(subject_id, request)
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SUBJECT_CONFLICT) from exc
    return payload


@router.patch("/subjects/{subject_id}/deactivate", response_model=SubjectRead)
async def deactivate_subject(
    subject_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> SubjectRead:
    try:
        payload = await service.set_subject_active(subject_id, False)
    except AcademicNotFoundError as exc:
        raise _translate(exc) from exc
    await session.commit()
    return payload


@router.patch("/subjects/{subject_id}/reactivate", response_model=SubjectRead)
async def reactivate_subject(
    subject_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> SubjectRead:
    try:
        payload = await service.set_subject_active(subject_id, True)
    except AcademicNotFoundError as exc:
        raise _translate(exc) from exc
    await session.commit()
    return payload


# --------------------------------------------------------------------------- #
# Jadwal
# --------------------------------------------------------------------------- #


@router.get("/schedules", response_model=ClassScheduleListResponse)
async def list_schedules(
    academic_year: str | None = Query(default=None, max_length=16),
    semester: str | None = Query(default=None, max_length=16),
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    lecturer_id: UUID | None = None,
    service: AcademicService = Depends(get_academic_service),
    user: AdminUser = Depends(require_academic_user),
) -> ClassScheduleListResponse:
    items = await service.list_schedules(
        academic_year=academic_year or None,
        semester=semester or None,
        class_id=class_id,
        subject_id=subject_id,
        lecturer_id=lecturer_id,
        lecturer_scope=lecturer_scope_for(user),
    )
    return ClassScheduleListResponse(items=items, total=len(items))


@router.get("/schedules/filters", response_model=RecapFilterOptions)
async def schedule_filter_options(
    service: AcademicService = Depends(get_academic_service),
    _: AdminUser = Depends(require_academic_user),
) -> RecapFilterOptions:
    return RecapFilterOptions(academic_years=await service.list_academic_years(), semesters=["ganjil", "genap"])


@router.post("/schedules", response_model=ClassScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request: ClassScheduleWrite,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    await _validate_schedule_refs(request, session)
    try:
        payload = await service.create_schedule(request)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SCHEDULE_CONFLICT) from exc
    return payload


@router.put("/schedules/{schedule_id}", response_model=ClassScheduleRead)
async def update_schedule(
    schedule_id: UUID,
    request: ClassScheduleWrite,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    await _validate_schedule_refs(request, session)
    try:
        payload = await service.update_schedule(schedule_id, request)
        await session.commit()
    except AcademicNotFoundError as exc:
        raise _translate(exc) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SCHEDULE_CONFLICT) from exc
    return payload


@router.delete("/schedules/{schedule_id}", response_model=ScheduleDeleteResponse)
async def delete_schedule(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ScheduleDeleteResponse:
    """Delete a jadwal. Prefer deactivate when the term's data still matters —
    this removes its meetings and attendance too."""
    try:
        result = await service.delete_schedule(schedule_id)
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    return ScheduleDeleteResponse(**result)


@router.patch("/schedules/{schedule_id}/deactivate", response_model=ClassScheduleRead)
async def deactivate_schedule(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    try:
        payload = await service.set_schedule_active(schedule_id, False)
    except AcademicNotFoundError as exc:
        raise _translate(exc) from exc
    await session.commit()
    return payload


@router.patch("/schedules/{schedule_id}/reactivate", response_model=ClassScheduleRead)
async def reactivate_schedule(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    try:
        payload = await service.set_schedule_active(schedule_id, True)
    except AcademicNotFoundError as exc:
        raise _translate(exc) from exc
    await session.commit()
    return payload


@router.post("/schedules/{schedule_id}/session", response_model=ClassScheduleRead)
async def ensure_kiosk_session(
    schedule_id: UUID,
    request: KioskSessionRequest | None = None,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    """Give the jadwal a face-recognition session, or refresh the one it has."""
    try:
        payload = await service.ensure_kiosk_session(
            schedule_id, device_code=(request.device_code if request else None)
        )
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SCHEDULE_CONFLICT) from exc
    return payload


@router.patch("/schedules/{schedule_id}/session/activate", response_model=ClassScheduleRead)
async def activate_kiosk_session(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    try:
        payload = await service.set_kiosk_session_active(schedule_id, True)
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    return payload


@router.patch("/schedules/{schedule_id}/session/deactivate", response_model=ClassScheduleRead)
async def deactivate_kiosk_session(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    _: AdminUser = Depends(require_academic_admin),
) -> ClassScheduleRead:
    try:
        payload = await service.set_kiosk_session_active(schedule_id, False)
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    return payload


# --------------------------------------------------------------------------- #
# Pertemuan
# --------------------------------------------------------------------------- #


@router.get("/schedules/{schedule_id}/meetings", response_model=MeetingListResponse)
async def list_meetings(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    user: AdminUser = Depends(require_academic_user),
) -> MeetingListResponse:
    try:
        schedule, items = await service.list_meetings(schedule_id, lecturer_scope=lecturer_scope_for(user))
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    return MeetingListResponse(schedule=schedule, items=items, total=len(items))


@router.post("/schedules/{schedule_id}/meetings/generate", response_model=MeetingListResponse)
async def generate_meetings(
    schedule_id: UUID,
    request: MeetingGenerateRequest,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_academic_user),
) -> MeetingListResponse:
    try:
        schedule, items = await service.generate_meetings(
            schedule_id, total_meetings=request.total_meetings, lecturer_scope=lecturer_scope_for(user)
        )
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    except IntegrityError as exc:
        # Two operators generated meetings at once; the unique index on
        # (schedule_id, meeting_number) kept the duplicates out.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pertemuan sedang dibuat dari tempat lain. Muat ulang halaman.",
        ) from exc
    return MeetingListResponse(schedule=schedule, items=items, total=len(items))


@router.put("/meetings/{meeting_id}", response_model=MeetingRead)
async def update_meeting(
    meeting_id: UUID,
    request: MeetingWrite,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_academic_user),
) -> MeetingRead:
    try:
        payload = await service.update_meeting(meeting_id, request, lecturer_scope=lecturer_scope_for(user))
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    await session.commit()
    return payload


# --------------------------------------------------------------------------- #
# Input absensi
# --------------------------------------------------------------------------- #


@router.get("/meetings/{meeting_id}/attendance", response_model=AttendanceSheetResponse)
async def attendance_sheet(
    meeting_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    user: AdminUser = Depends(require_academic_user),
) -> AttendanceSheetResponse:
    try:
        return await service.attendance_sheet(meeting_id, lecturer_scope=lecturer_scope_for(user))
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc


@router.put("/meetings/{meeting_id}/attendance", response_model=AttendanceSaveResponse)
async def save_attendance(
    meeting_id: UUID,
    request: AttendanceSaveRequest,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_academic_user),
) -> AttendanceSaveResponse:
    try:
        created, updated, skipped = await service.save_attendance(
            meeting_id,
            request.entries,
            mark_meeting_held=request.mark_meeting_held,
            recorded_by_admin_id=user.id,
            lecturer_scope=lecturer_scope_for(user),
        )
        await session.commit()
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc
    except IntegrityError as exc:
        # The (meeting_id, person_id) unique index caught a concurrent save.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Absensi pertemuan ini sedang disimpan dari tempat lain. Muat ulang lalu coba lagi.",
        ) from exc
    detail = f"Absensi tersimpan: {created} baru, {updated} diperbarui."
    if skipped:
        detail += f" {skipped} entri diabaikan karena bukan siswa kelas ini."
    return AttendanceSaveResponse(meeting_id=meeting_id, created=created, updated=updated, skipped=skipped, detail=detail)


@router.get("/meetings/{meeting_id}/attendance/prefill", response_model=AttendancePrefillResponse)
async def prefill_from_face_recognition(
    meeting_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_academic_user),
) -> AttendancePrefillResponse:
    """Suggest H for students the kiosk already recognised for this meeting.

    Read-only: it returns a proposed sheet, it does not write. The teacher still
    reviews and saves, so a bad face match never becomes attendance by itself.
    """
    try:
        sheet = await service.attendance_sheet(meeting_id, lecturer_scope=lecturer_scope_for(user))
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc

    meeting = sheet.meeting
    if meeting.attendance_session_id is None or meeting.meeting_date is None:
        return AttendancePrefillResponse(
            meeting_id=meeting_id,
            matched=0,
            students=sheet.students,
            detail="Pertemuan ini belum terhubung ke sesi absensi wajah atau belum punya tanggal.",
        )

    # Same WITA day boundary the kiosk dedup index uses, so "hari itu" means the
    # same day here as it does there.
    day_expression = func.date(func.timezone("Asia/Makassar", AttendanceLog.created_at))
    result = await session.execute(
        select(AttendanceLog.person_id)
        .where(
            AttendanceLog.session_id == meeting.attendance_session_id,
            AttendanceLog.is_deleted.is_(False),
            AttendanceLog.decision.in_(ATTENDANCE_SUCCESS_DECISIONS),
            day_expression == meeting.meeting_date,
        )
        .distinct()
    )
    recognized = {person_id for person_id in result.scalars().all() if person_id is not None}

    students = []
    matched = 0
    for student in sheet.students:
        if student.person_id in recognized:
            matched += 1
            students.append(student.model_copy(update={"status": "H", "source": "face"}))
        else:
            students.append(student)
    return AttendancePrefillResponse(
        meeting_id=meeting_id,
        matched=matched,
        students=students,
        detail=f"{matched} siswa dikenali kamera pada tanggal pertemuan ini.",
    )


# --------------------------------------------------------------------------- #
# Rekap
# --------------------------------------------------------------------------- #


@router.get("/schedules/{schedule_id}/recap", response_model=RecapResponse)
async def schedule_recap(
    schedule_id: UUID,
    service: AcademicService = Depends(get_academic_service),
    user: AdminUser = Depends(require_academic_user),
) -> RecapResponse:
    try:
        return await service.recap(schedule_id, lecturer_scope=lecturer_scope_for(user))
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc


@router.get("/schedules/{schedule_id}/recap/export")
async def export_schedule_recap(
    schedule_id: UUID,
    format: str = Query(default="excel", pattern="^(excel|pdf)$"),
    service: AcademicService = Depends(get_academic_service),
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_academic_user),
) -> StreamingResponse:
    try:
        recap = await service.recap(schedule_id, lecturer_scope=lecturer_scope_for(user))
    except (AcademicNotFoundError, AcademicPermissionError) as exc:
        raise _translate(exc) from exc

    branding = await load_branding(session)
    if format == "pdf":
        return _recap_pdf_response(recap, branding)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rekap Absensi"

    schedule = recap.schedule
    sheet.append([branding.school_name.upper()])
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append(["REKAP ABSENSI"])
    sheet["A2"].font = Font(bold=True, size=12)
    if branding.has_logo:
        try:
            from openpyxl.drawing.image import Image as XlsxImage

            logo = XlsxImage(branding.logo_stream())
            # Scale to a fixed height so a large upload cannot cover the sheet.
            ratio = 56 / max(logo.height, 1)
            logo.height = 56
            logo.width = int(logo.width * ratio)
            logo.anchor = "E1"
            sheet.add_image(logo)
        except Exception:  # noqa: BLE001 - a bad logo must not fail the export
            LOGGER.warning("excel_logo_skipped", exc_info=True)
    sheet.append(["Kelas", f"{schedule.class_code or '-'} - {schedule.class_name or '-'}"])
    sheet.append(["Mata Pelajaran", f"{schedule.subject_code or '-'} - {schedule.subject_name or '-'}"])
    sheet.append(["Guru", schedule.lecturer_name or "-"])
    sheet.append(["Tahun Ajaran", schedule.academic_year])
    sheet.append(["Semester", schedule.semester.capitalize()])
    sheet.append(["Pertemuan Terlaksana", f"{recap.held_meetings} dari {recap.total_meetings}"])
    sheet.append([])

    header = ["No", "NISN", "Nama Siswa"]
    header += [f"P{column.meeting_number}" for column in recap.columns]
    header += ["H", "S", "I", "A", "Kehadiran %"]
    sheet.append(header)
    header_row = sheet.max_row
    for cell in sheet[header_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for row in recap.rows:
        values = [row.no, row.student_id, row.full_name]
        values += [cell or "" for cell in row.cells]
        values += [row.hadir, row.sakit, row.izin, row.alpha, f"{row.attendance_percent}%"]
        sheet.append(values)

    sheet.column_dimensions["B"].width = 18
    sheet.column_dimensions["C"].width = 32

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    filename = f"rekap-absensi-{schedule.schedule_code}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _recap_pdf_response(recap, branding: Branding) -> StreamingResponse:
    """Formal presensi sheet: letterhead, ruled P1..Pn matrix, totals, legend."""
    schedule = recap.schedule
    buffer = BytesIO()
    # Landscape: a 16-meeting matrix does not fit portrait at a readable size.
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))

    left = 28.0
    right = page_width - 28.0

    # --- column geometry, shared by the header and every row --------------
    meeting_count = max(len(recap.columns), 1)
    no_w, nisn_w, name_w = 26.0, 78.0, 152.0
    total_w, pct_w = 24.0, 48.0
    fixed = no_w + nisn_w + name_w + total_w * 4 + pct_w
    cell_w = max(15.0, (right - left - fixed) / meeting_count)
    table_right = left + fixed + cell_w * meeting_count

    # x offset of every vertical rule, so the grid always lines up with text
    edges = [left, left + no_w, left + no_w + nisn_w, left + no_w + nisn_w + name_w]
    for index in range(meeting_count):
        edges.append(edges[-1] + cell_w)
    for _ in range(4):
        edges.append(edges[-1] + total_w)
    edges.append(edges[-1] + pct_w)

    row_h = 14.0
    head_h = 20.0

    def letterhead(y_pos: float) -> float:
        """Logo and school name on one line. ``y_pos`` is the baseline of the
        school name; the two text lines run from there down to roughly
        ``y_pos - 17``, so the logo is centred on that block rather than hung
        from the first baseline."""
        text_left = left
        logo_size = 38.0
        if branding.has_logo:
            try:
                text_block_top = y_pos + 12          # cap height of the 14pt line
                text_block_bottom = y_pos - 17       # descender of the 10pt line
                logo_bottom = (text_block_top + text_block_bottom) / 2 - logo_size / 2
                pdf.drawImage(
                    ImageReader(branding.logo_stream()), left, logo_bottom,
                    width=logo_size, height=logo_size,
                    preserveAspectRatio=True, anchor="c", mask="auto",
                )
                text_left = left + logo_size + 12
            except Exception:  # noqa: BLE001 - never fail an export over a logo
                LOGGER.warning("pdf_logo_skipped", exc_info=True)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(text_left, y_pos, branding.school_name.upper())
        pdf.setFont("Helvetica", 10)
        pdf.drawString(text_left, y_pos - 14, "Laporan Presensi Siswa")
        y_pos -= 30
        pdf.setLineWidth(1.1)
        pdf.line(left, y_pos, right, y_pos)
        pdf.setLineWidth(0.5)
        return y_pos - 16

    def draw_header(y_pos: float) -> float:
        """Header band with ruled cells. Returns the baseline of the first row."""
        top = y_pos
        bottom = y_pos - head_h
        pdf.setFillColorRGB(0.93, 0.95, 0.96)
        pdf.rect(left, bottom, table_right - left, head_h, stroke=0, fill=1)
        pdf.setFillColorRGB(0, 0, 0)

        pdf.setFont("Helvetica-Bold", 7.5)
        labels = ["No", "NISN", "Nama"]
        for index, label in enumerate(labels):
            pdf.drawString(edges[index] + 3, bottom + 7, label)
        base = len(labels)
        for index, column in enumerate(recap.columns):
            centre = edges[base + index] + cell_w / 2
            pdf.drawCentredString(centre, bottom + 11, f"P{column.meeting_number}")
            pdf.setFont("Helvetica", 5.2)
            pdf.drawCentredString(
                centre, bottom + 3,
                column.meeting_date.strftime("%d/%m") if column.meeting_date else "-",
            )
            pdf.setFont("Helvetica-Bold", 7.5)
        base += meeting_count
        for index, label in enumerate(("H", "S", "I", "A")):
            pdf.drawCentredString(edges[base + index] + total_w / 2, bottom + 7, label)
        pdf.drawCentredString(edges[base + 4] + pct_w / 2, bottom + 7, "%")

        _rules(top, bottom)
        return bottom

    def _rules(top: float, bottom: float) -> None:
        """Vertical rules for one band, plus its top and bottom lines."""
        pdf.setStrokeColorRGB(0.72, 0.76, 0.8)
        for x in edges:
            pdf.line(x, top, x, bottom)
        pdf.line(left, top, table_right, top)
        pdf.line(left, bottom, table_right, bottom)

    y = page_height - 44
    y = letterhead(y)

    pdf.setFont("Helvetica", 9)
    for label, value in (
        ("Mata Pelajaran", f"{schedule.subject_name or '-'} ({schedule.subject_code or '-'})"),
        ("Kelas", f"{schedule.class_code or '-'} - {schedule.class_name or '-'}"),
        ("Periode", f"{schedule.academic_year} {schedule.semester.capitalize()}"),
        ("Guru", schedule.lecturer_name or "-"),
        ("Pertemuan Terlaksana", f"{recap.held_meetings} dari {recap.total_meetings}"),
    ):
        pdf.drawString(left, y, f"{label:<22}: {value}")
        y -= 12
    y -= 8

    y = draw_header(y)

    for row in recap.rows:
        if y - row_h < 56:
            pdf.showPage()
            y = page_height - 44
            y = letterhead(y)
            y = draw_header(y)
        top = y
        bottom = y - row_h
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillColorRGB(0, 0, 0)
        text_y = bottom + 4.5
        pdf.drawString(edges[0] + 3, text_y, str(row.no))
        pdf.drawString(edges[1] + 3, text_y, (row.student_id or "-")[:14])
        pdf.drawString(edges[2] + 3, text_y, (row.full_name or "-")[:30])
        base = 3
        for index, value in enumerate(row.cells):
            unheld = recap.columns[index].status != "held" if index < len(recap.columns) else True
            pdf.drawCentredString(
                edges[base + index] + cell_w / 2, text_y,
                "" if (value is None and unheld) else (value or "-"),
            )
        base += meeting_count
        for index, value in enumerate((row.hadir, row.sakit, row.izin, row.alpha)):
            pdf.drawCentredString(edges[base + index] + total_w / 2, text_y, str(value))
        pdf.drawCentredString(edges[base + 4] + pct_w / 2, text_y, f"{row.attendance_percent:g}%")
        _rules(top, bottom)
        y = bottom

    pdf.setStrokeColorRGB(0, 0, 0)
    y -= 16
    pdf.setFont("Helvetica-Oblique", 7.5)
    pdf.drawString(left, y, "Keterangan: H = Hadir   A = Alpa   S = Sakit   I = Izin")
    y -= 10
    pdf.drawString(
        left, y,
        "Persentase kehadiran = Hadir / pertemuan yang sudah dilaksanakan x 100. "
        "Kolom kosong = pertemuan belum dilaksanakan.",
    )

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    filename = f"presensi-{schedule.schedule_code}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _validate_schedule_refs(request: ClassScheduleWrite, session: AsyncSession) -> None:
    """Reject unknown class/subject ids with a clear 404 instead of a FK error."""
    if await session.get(ClassGroup, request.class_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kelas tidak ditemukan.")
    if await session.get(Subject, request.subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mata pelajaran tidak ditemukan.")
