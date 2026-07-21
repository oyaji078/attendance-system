import asyncio
from datetime import date as date_type, datetime
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csrf import csrf_dependency
from app.core.file_security import secure_file_path
from app.core.security import hash_password
from app.core.dependencies import AppContainer, get_admin_service, get_attendance_session_service, get_container, get_session, require_admin
from db.domain.attendance import normalize_attendance_decision, normalize_attendance_event_type, normalize_attendance_reason
from db.models.entities import AdminUser, AttendanceLog, AttendanceSession, ClassGroup, DeviceConfig, FaceSample, Lecturer, Person
from db.repositories.device_configs import DeviceConfigRepository
from db.schemas.academic import ClassListResponse, ClassRead, ClassWrite, LecturerListResponse, LecturerRead, LecturerWrite, NextIdResponse
from db.schemas.admin import AdminActionResponse, AdminMetricsResponse, AdminPersonResponse
from db.schemas.admin_extended import AttendanceLogAdminRead, AttendanceLogListResponse, AttendanceLogUpdateRequest, DeviceConfigListResponse
from db.schemas.attendance_sessions import AttendanceSessionCreateRequest, AttendanceSessionListResponse, AttendanceSessionNextCodeResponse, AttendanceSessionRead, AttendanceSessionUpdateRequest
from db.schemas.auth import AdminUserCreateRequest, AdminUserListResponse, AdminUserRead, AdminUserUpdateRequest
from db.schemas.device import DeviceConfigRead, DeviceConfigWrite
from db.schemas.persons import PersonCreateRequest, PersonListResponse, PersonRead, PersonUpdateRequest
from services.attendance.session_service import AttendanceSessionConflictError, AttendanceSessionService
from services.auth_service import admin_user_read
from services.recognition.admin_service import AdminService, PersonConflictError

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin), Depends(csrf_dependency)])

ALLOWED_USER_ROLES = {"admin", "lecturer"}


async def _invalidate_persons_cache(container: AppContainer) -> None:
    await container.cache.invalidate_prefix("persons:")


async def _invalidate_lecturers_cache(container: AppContainer) -> None:
    await container.cache.invalidate_prefix("lecturers:")


async def _invalidate_classes_cache(container: AppContainer) -> None:
    await container.cache.invalidate_prefix("classes:")


def device_read(config: DeviceConfig, heartbeat: object | None = None) -> DeviceConfigRead:
    return DeviceConfigRead(
        id=config.id,
        device_code=config.device_code,
        device_name=config.device_name,
        location_hint=config.location_hint,
        det_thresh=config.det_thresh,
        det_size=[config.det_size_width, config.det_size_height],
        max_faces=config.max_faces,
        min_face_width_px=config.min_face_width_px,
        min_brightness=config.min_brightness,
        min_blur_score=config.min_blur_score,
        similarity_threshold=config.similarity_threshold,
        candidate_margin_threshold=config.candidate_margin_threshold,
        liveness_threshold=config.liveness_threshold,
        multi_frame_confirm=config.multi_frame_confirm,
        accepted_per_pose=config.accepted_per_pose,
        cooldown_seconds=config.cooldown_seconds,
        is_enabled=config.is_enabled,
        updated_at=config.updated_at,
        heartbeat=None if heartbeat is None else heartbeat,
    )


def class_read(row: tuple[ClassGroup, str | None, int]) -> ClassRead:
    class_group, lecturer_name, total_students = row
    return ClassRead(
        class_id=class_group.id,
        class_code=class_group.class_code,
        class_name=class_group.class_name,
        lecturer_id=class_group.lecturer_id,
        lecturer_name=lecturer_name,
        description=class_group.description,
        is_active=class_group.is_active,
        total_students=int(total_students or 0),
        created_at=class_group.created_at,
        updated_at=class_group.updated_at,
    )


def lecturer_read(lecturer: Lecturer) -> LecturerRead:
    return LecturerRead(
        lecturer_id=lecturer.id,
        lecturer_code=lecturer.lecturer_code,
        full_name=lecturer.full_name,
        email=lecturer.email,
        department=lecturer.department,
        is_active=lecturer.is_active,
        created_at=lecturer.created_at,
        updated_at=lecturer.updated_at,
    )


def admin_account_read(row: tuple[AdminUser, str | None]) -> AdminUserRead:
    user, lecturer_name = row
    return admin_user_read(user, lecturer_name=lecturer_name)


def attendance_log_admin_read(
    row: tuple[AttendanceLog, Person | None, AttendanceSession | None, ClassGroup | None],
    no: int,
) -> AttendanceLogAdminRead:
    log, person, attendance_session, class_group = row
    return AttendanceLogAdminRead(
        log_id=log.id,
        no=no,
        student_id=person.student_id if person else None,
        full_name=person.full_name if person else None,
        email=person.email if person else None,
        class_code=class_group.class_code if class_group else None,
        class_name=class_group.class_name if class_group else None,
        session_code=attendance_session.session_code if attendance_session else None,
        decision=normalize_attendance_decision(log.decision, log.reason),
        reason=normalize_attendance_reason(log.reason),
        confidence=log.confidence,
        device_code=log.device_code,
        event_type=normalize_attendance_event_type(log.event_type),
        captured_image_url=f"/admin/attendance-logs/{log.id}/image" if log.captured_image_uri else None,
        created_at=log.created_at,
    )


def normalize_user_role(role: str) -> str:
    normalized = (role or "admin").strip().lower()
    if normalized == "dosen":
        normalized = "lecturer"
    if normalized not in ALLOWED_USER_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role akun hanya boleh admin atau dosen.")
    return normalized


def normalized_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


async def validated_account_lecturer_id(role: str, lecturer_id: UUID | None, session: AsyncSession) -> UUID | None:
    if role == "admin":
        return None
    if lecturer_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pilih data dosen untuk akun dosen.")
    lecturer = await session.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosen tidak ditemukan.")
    if not lecturer.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dosen nonaktif tidak dapat diberi akun login.")
    return lecturer_id


async def active_admin_count(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(AdminUser.id)).where(AdminUser.role == "admin", AdminUser.is_active.is_(True))
    )
    return int(result.scalar_one())


async def read_admin_account(admin_id: UUID, session: AsyncSession) -> AdminUserRead:
    result = await session.execute(
        select(AdminUser, Lecturer.full_name)
        .outerjoin(Lecturer, Lecturer.id == AdminUser.lecturer_id)
        .where(AdminUser.id == admin_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    return admin_account_read(row)


async def guard_admin_account_lockout(
    user: AdminUser,
    *,
    next_role: str,
    next_active: bool,
    current_admin: AdminUser,
    session: AsyncSession,
) -> None:
    if user.id == current_admin.id and (next_role != "admin" or not next_active):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Akun yang sedang digunakan tidak bisa dinonaktifkan atau diubah menjadi dosen.")
    if user.role == "admin" and user.is_active and (next_role != "admin" or not next_active):
        if await active_admin_count(session) <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Minimal satu akun admin aktif harus tersedia.")


def normalize_class_code(class_code: str | None) -> str:
    value = re.sub(r"[^A-Za-z0-9]", "", (class_code or "AUTO")).upper()
    return value or "AUTO"


async def _next_sequential_code(session: AsyncSession, model, column, prefix: str) -> str:
    """Generate the next PREFIX-NNNN code by scanning existing values.

    Used to auto-assign lecturer/class codes when the admin leaves them blank,
    so the operator never has to invent identifiers by hand.
    """
    result = await session.execute(select(column).where(column.like(f"{prefix}-%")))
    used: set[int] = set()
    for value in result.scalars().all():
        match = re.search(r"-(\d+)$", value or "")
        if match:
            used.add(int(match.group(1)))
    candidate = 1
    while candidate in used:
        candidate += 1
    return f"{prefix}-{candidate:04d}"


async def resolve_lecturer_code(session: AsyncSession, provided: str | None) -> str:
    cleaned = (provided or "").strip()
    if cleaned:
        return cleaned
    return await _next_sequential_code(session, Lecturer, Lecturer.lecturer_code, "DSN")


async def resolve_class_code(session: AsyncSession, provided: str | None) -> str:
    cleaned = (provided or "").strip()
    if cleaned:
        return cleaned
    return await _next_sequential_code(session, ClassGroup, ClassGroup.class_code, "KLS")


@router.get("/admin/users", response_model=AdminUserListResponse)
async def list_admin_users(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AdminUserListResponse:
    count_result = await session.execute(select(func.count(AdminUser.id)))
    total = int(count_result.scalar_one())
    result = await session.execute(
        select(AdminUser, Lecturer.full_name)
        .outerjoin(Lecturer, Lecturer.id == AdminUser.lecturer_id)
        .order_by(AdminUser.created_at.desc(), AdminUser.username.asc())
        .offset(offset)
        .limit(limit)
    )
    return AdminUserListResponse(items=[admin_account_read(row) for row in result.all()], total=total, limit=limit, offset=offset, has_next=offset + limit < total)


@router.post("/admin/users", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def create_admin_user(request: AdminUserCreateRequest, session: AsyncSession = Depends(get_session)) -> AdminUserRead:
    role = normalize_user_role(request.role)
    lecturer_id = await validated_account_lecturer_id(role, request.lecturer_id, session)
    username = request.username.strip()
    full_name = request.full_name.strip()
    if not username or not full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username dan nama wajib diisi.")
    user = AdminUser(
        username=username,
        email=normalized_optional_text(request.email),
        full_name=full_name,
        password_hash=hash_password(request.password),
        role=role,
        lecturer_id=lecturer_id,
        is_active=request.is_active,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username atau email sudah digunakan.") from exc
    return await read_admin_account(user.id, session)


@router.put("/admin/users/{admin_id}", response_model=AdminUserRead)
async def update_admin_user(
    admin_id: UUID,
    request: AdminUserUpdateRequest,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminUserRead:
    user = await session.get(AdminUser, admin_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    role = normalize_user_role(request.role)
    lecturer_id = await validated_account_lecturer_id(role, request.lecturer_id, session)
    await guard_admin_account_lockout(user, next_role=role, next_active=request.is_active, current_admin=current_admin, session=session)
    username = request.username.strip()
    full_name = request.full_name.strip()
    if not username or not full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username dan nama wajib diisi.")
    user.username = username
    user.email = normalized_optional_text(request.email)
    user.full_name = full_name
    user.role = role
    user.lecturer_id = lecturer_id
    user.is_active = request.is_active
    if request.password:
        user.password_hash = hash_password(request.password)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username atau email sudah digunakan.") from exc
    return await read_admin_account(admin_id, session)


@router.patch("/admin/users/{admin_id}/deactivate", response_model=AdminUserRead)
async def deactivate_admin_user(
    admin_id: UUID,
    current_admin: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminUserRead:
    user = await session.get(AdminUser, admin_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    await guard_admin_account_lockout(user, next_role=user.role, next_active=False, current_admin=current_admin, session=session)
    user.is_active = False
    await session.commit()
    return await read_admin_account(admin_id, session)


@router.patch("/admin/users/{admin_id}/reactivate", response_model=AdminUserRead)
async def reactivate_admin_user(admin_id: UUID, session: AsyncSession = Depends(get_session)) -> AdminUserRead:
    user = await session.get(AdminUser, admin_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    if user.role == "lecturer":
        await validated_account_lecturer_id(user.role, user.lecturer_id, session)
    user.is_active = True
    await session.commit()
    return await read_admin_account(admin_id, session)


async def _merge_fresh_heartbeats(container: AppContainer, items: list[DeviceConfigRead]) -> list[DeviceConfigRead]:
    result: list[DeviceConfigRead] = []
    for item in items:
        try:
            heartbeat_raw = await container.cache.get_device_heartbeat(item.device_code)
        except Exception:
            logger.warning("Failed to read heartbeat for device %s", item.device_code)
            heartbeat_raw = None
        result.append(device_read_from_cached(item.model_dump(mode="json"), heartbeat_raw))
    return result


def device_read_from_cached(data: dict, heartbeat: dict | None) -> DeviceConfigRead:
    merged = {**data, "heartbeat": heartbeat}
    return DeviceConfigRead(**merged)


@router.get("/admin/devices/configs", response_model=list[DeviceConfigRead])
async def list_device_configs(container: AppContainer = Depends(get_container), session: AsyncSession = Depends(get_session)) -> list[DeviceConfigRead]:
    cached = await container.cache.get_cached("devices_configs")
    if cached is not None:
        items = [DeviceConfigRead(**item) for item in cached]
        return await _merge_fresh_heartbeats(container, items)
    repository = DeviceConfigRepository(session)
    items: list[DeviceConfigRead] = []
    for config in await repository.list_all():
        items.append(device_read(config, None))
    await container.cache.set_cached("devices_configs", [item.model_dump(mode="json") for item in items], 30)
    return await _merge_fresh_heartbeats(container, items)


@router.get("/admin/devices", response_model=DeviceConfigListResponse)
async def list_devices_paginated(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    container: AppContainer = Depends(get_container),
    session: AsyncSession = Depends(get_session),
) -> DeviceConfigListResponse:
    repository = DeviceConfigRepository(session)
    count_result = await session.execute(select(func.count(DeviceConfig.id)))
    total = int(count_result.scalar_one())
    configs = await repository.list_all(limit=limit, offset=offset)
    items: list[DeviceConfigRead] = []
    for config in configs:
        heartbeat = await container.cache.get_device_heartbeat(config.device_code)
        items.append(device_read(config, heartbeat))
    return DeviceConfigListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)


@router.put("/admin/devices/config/{device_code}", response_model=DeviceConfigRead)
async def update_device_config(device_code: str, request: DeviceConfigWrite, container: AppContainer = Depends(get_container), session: AsyncSession = Depends(get_session)) -> DeviceConfigRead:
    repository = DeviceConfigRepository(session)
    config = await repository.upsert(
        device_code,
        {
            "device_name": request.device_name,
            "location_hint": request.location_hint,
            "det_thresh": request.det_thresh,
            "det_size_width": request.det_size[0],
            "det_size_height": request.det_size[1],
            "max_faces": request.max_faces,
            "min_face_width_px": request.min_face_width_px,
            "min_brightness": request.min_brightness,
            "min_blur_score": request.min_blur_score,
            "similarity_threshold": request.similarity_threshold,
            "candidate_margin_threshold": request.candidate_margin_threshold,
            "liveness_threshold": request.liveness_threshold,
            "multi_frame_confirm": request.multi_frame_confirm,
            "accepted_per_pose": request.accepted_per_pose,
            "cooldown_seconds": request.cooldown_seconds,
            "is_enabled": request.is_enabled,
        },
    )
    await session.commit()
    await session.refresh(config)
    await container.cache.invalidate_device_config_cached(device_code)
    await container.cache.invalidate_prefix("devices_configs")
    await container.cache.invalidate_prefix("devices:")
    heartbeat = await container.cache.get_device_heartbeat(device_code)
    return device_read(config, heartbeat)


@router.post("/admin/reindex", response_model=AdminActionResponse)
async def admin_reindex(service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> AdminActionResponse:
    await service.reindex()
    await session.commit()
    return AdminActionResponse(status="ok", detail="HNSW index reindexed")


@router.post("/admin/rebuild-all-templates", response_model=AdminActionResponse)
async def rebuild_all_templates(service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> AdminActionResponse:
    rebuilt = await service.rebuild_all_templates()
    await session.commit()
    return AdminActionResponse(status="ok", detail=f"rebuilt {rebuilt} active templates")


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
async def admin_metrics(service: AdminService = Depends(get_admin_service), container: AppContainer = Depends(get_container)) -> AdminMetricsResponse:
    cached = await container.cache.get_cached("metrics")
    if cached is not None:
        return AdminMetricsResponse(**cached)
    result = await service.metrics()
    await container.cache.set_cached("metrics", result.model_dump(mode="json"), 15)
    return result


@router.get("/admin/person/{student_id}", response_model=AdminPersonResponse)
async def admin_person(student_id: str, service: AdminService = Depends(get_admin_service)) -> AdminPersonResponse:
    payload = await service.person_detail(student_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    return payload


@router.get("/admin/persons", response_model=PersonListResponse)
async def list_persons(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AdminService = Depends(get_admin_service),
    container: AppContainer = Depends(get_container),
) -> PersonListResponse:
    cache_key = f"persons:{limit}:{offset}"
    cached = await container.cache.get_cached(cache_key)
    if cached is not None:
        return PersonListResponse(**cached)
    items, total = await asyncio.gather(
        service.list_persons(limit=limit, offset=offset),
        service.count_persons(),
    )
    result = PersonListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)
    await container.cache.set_cached(cache_key, result.model_dump(mode="json"), 30)
    return result


@router.post("/admin/persons", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
async def create_person(request: PersonCreateRequest, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> PersonRead:
    try:
        payload = await service.create_person(request)
    except PersonConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    await _invalidate_persons_cache(container)
    return payload


@router.get("/admin/persons/{person_id}", response_model=PersonRead)
async def get_person(person_id: UUID, service: AdminService = Depends(get_admin_service)) -> PersonRead:
    payload = await service.get_person(person_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    return payload


@router.put("/admin/persons/{person_id}", response_model=PersonRead)
async def update_person(person_id: UUID, request: PersonUpdateRequest, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> PersonRead:
    try:
        payload = await service.update_person(person_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    await _invalidate_persons_cache(container)
    return payload


@router.patch("/admin/persons/{person_id}/deactivate", response_model=PersonRead)
async def deactivate_person(person_id: UUID, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> PersonRead:
    try:
        payload = await service.deactivate_person(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    await _invalidate_persons_cache(container)
    return payload


@router.patch("/admin/persons/{person_id}/reactivate", response_model=PersonRead)
async def reactivate_person(person_id: UUID, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> PersonRead:
    try:
        payload = await service.reactivate_person(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    await _invalidate_persons_cache(container)
    return payload


@router.delete("/admin/persons/{person_id}", response_model=AdminActionResponse)
async def delete_person(person_id: UUID, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AdminActionResponse:
    try:
        result = await service.delete_person(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahasiswa tidak ditemukan.") from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    await _invalidate_persons_cache(container)
    return AdminActionResponse(
        status="ok",
        detail=f"Mahasiswa dihapus dari daftar aktif. {result['templates_deactivated']} template wajah aktif dinonaktifkan.",
    )


@router.delete("/admin/persons/{person_id}/face-data", response_model=AdminActionResponse)
async def clear_person_face_data(person_id: UUID, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AdminActionResponse:
    try:
        result = await service.clear_person_face_data(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahasiswa tidak ditemukan.") from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    await _invalidate_persons_cache(container)
    return AdminActionResponse(
        status="ok",
        detail=(
            "Data wajah dinonaktifkan: "
            f"{result['samples_deleted']} sampel, "
            f"{result['templates_deleted']} template. "
            "Foto enrollment disembunyikan dari tampilan aktif."
        ),
    )


@router.get("/admin/persons/{person_id}/photo")
async def person_photo(person_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> FileResponse:
    result = await session.execute(
        select(FaceSample)
        .join(Person, Person.id == FaceSample.person_id)
        .where(
            FaceSample.person_id == person_id,
            FaceSample.image_uri.is_not(None),
            FaceSample.is_active.is_(True),
            FaceSample.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.is_deleted.is_(False),
        )
        .order_by(FaceSample.created_at.desc())
        .limit(1)
    )
    sample = result.scalar_one_or_none()
    if sample is None or not sample.image_uri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto wajah tidak tersedia.")
    path = secure_file_path(container.settings.object_storage_root, sample.image_uri)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/admin/ids/next", response_model=NextIdResponse)
async def next_entity_id(entity: str = "student", class_code: str | None = None, session: AsyncSession = Depends(get_session)) -> NextIdResponse:
    if entity != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Jenis ID belum didukung.")
    now = datetime.now().astimezone()
    prefix = f"{now:%y%m}-{normalize_class_code(class_code)}"
    result = await session.execute(select(Person.student_id).where(Person.student_id.like(f"{prefix}-%")))
    used_numbers: set[int] = set()
    for student_id in result.scalars().all():
        match = re.search(r"-(\d{4})$", student_id)
        if match:
            used_numbers.add(int(match.group(1)))
    next_number = 1
    while next_number in used_numbers:
        next_number += 1
    return NextIdResponse(id=f"{prefix}-{next_number:04d}")


@router.get("/admin/lecturers", response_model=LecturerListResponse)
async def list_lecturers(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> LecturerListResponse:
    cache_key = f"lecturers:{limit}:{offset}"
    cached = await container.cache.get_cached(cache_key)
    if cached is not None:
        return LecturerListResponse(**cached)
    count_result = await session.execute(select(func.count(Lecturer.id)))
    total = int(count_result.scalar_one())
    result = await session.execute(
        select(Lecturer).order_by(Lecturer.created_at.desc(), Lecturer.lecturer_code.asc()).offset(offset).limit(limit)
    )
    items = [lecturer_read(item) for item in result.scalars().all()]
    response = LecturerListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)
    await container.cache.set_cached(cache_key, response.model_dump(mode="json"), 60)
    return response


@router.post("/admin/lecturers", response_model=LecturerRead, status_code=status.HTTP_201_CREATED)
async def create_lecturer(request: LecturerWrite, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> LecturerRead:
    payload = request.model_dump()
    payload["lecturer_code"] = await resolve_lecturer_code(session, payload.get("lecturer_code"))
    lecturer = Lecturer(**payload)
    session.add(lecturer)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Kode dosen sudah digunakan.") from exc
    await session.refresh(lecturer)
    await container.cache.invalidate_cached("metrics")
    await _invalidate_lecturers_cache(container)
    return lecturer_read(lecturer)


@router.put("/admin/lecturers/{lecturer_id}", response_model=LecturerRead)
async def update_lecturer(lecturer_id: UUID, request: LecturerWrite, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> LecturerRead:
    lecturer = await session.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosen tidak ditemukan.")
    payload = request.model_dump()
    # A blank code on update keeps the existing one instead of nulling it.
    if not (payload.get("lecturer_code") or "").strip():
        payload["lecturer_code"] = lecturer.lecturer_code
    for key, value in payload.items():
        setattr(lecturer, key, value)
    await session.commit()
    await session.refresh(lecturer)
    await container.cache.invalidate_cached("metrics")
    await _invalidate_lecturers_cache(container)
    return lecturer_read(lecturer)


@router.patch("/admin/lecturers/{lecturer_id}/deactivate", response_model=LecturerRead)
async def deactivate_lecturer(lecturer_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> LecturerRead:
    lecturer = await session.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosen tidak ditemukan.")
    lecturer.is_active = False
    await session.commit()
    await session.refresh(lecturer)
    await container.cache.invalidate_cached("metrics")
    await _invalidate_lecturers_cache(container)
    return lecturer_read(lecturer)


@router.patch("/admin/lecturers/{lecturer_id}/reactivate", response_model=LecturerRead)
async def reactivate_lecturer(lecturer_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> LecturerRead:
    lecturer = await session.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosen tidak ditemukan.")
    lecturer.is_active = True
    await session.commit()
    await session.refresh(lecturer)
    await container.cache.invalidate_cached("metrics")
    await _invalidate_lecturers_cache(container)
    return lecturer_read(lecturer)


@router.get("/admin/classes", response_model=ClassListResponse)
async def list_classes(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> ClassListResponse:
    cache_key = f"classes:{limit}:{offset}"
    cached = await container.cache.get_cached(cache_key)
    if cached is not None:
        return ClassListResponse(**cached)
    count_result = await session.execute(select(func.count(ClassGroup.id)))
    total = int(count_result.scalar_one())
    result = await session.execute(
        select(ClassGroup, Lecturer.full_name, func.count(Person.id))
        .outerjoin(Lecturer, Lecturer.id == ClassGroup.lecturer_id)
        .outerjoin(Person, Person.class_id == ClassGroup.id)
        .group_by(ClassGroup.id, Lecturer.full_name)
        .order_by(ClassGroup.created_at.desc(), ClassGroup.class_code.asc())
        .offset(offset)
        .limit(limit)
    )
    items = [class_read(row) for row in result.all()]
    response = ClassListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)
    await container.cache.set_cached(cache_key, response.model_dump(mode="json"), 60)
    return response


@router.post("/admin/classes", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
async def create_class(request: ClassWrite, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> ClassRead:
    payload = request.model_dump()
    payload["class_code"] = await resolve_class_code(session, payload.get("class_code"))
    class_group = ClassGroup(**payload)
    session.add(class_group)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Kode kelas sudah digunakan.") from exc
    await session.refresh(class_group)
    lecturer_name = None
    if class_group.lecturer_id:
        lecturer = await session.get(Lecturer, class_group.lecturer_id)
        lecturer_name = lecturer.full_name if lecturer else None
    await container.cache.invalidate_cached("metrics")
    await _invalidate_classes_cache(container)
    return class_read((class_group, lecturer_name, 0))


@router.put("/admin/classes/{class_id}", response_model=ClassRead)
async def update_class(class_id: UUID, request: ClassWrite, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> ClassRead:
    class_group = await session.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kelas tidak ditemukan.")
    payload = request.model_dump()
    # A blank code on update keeps the existing one instead of nulling it.
    if not (payload.get("class_code") or "").strip():
        payload["class_code"] = class_group.class_code
    for key, value in payload.items():
        setattr(class_group, key, value)
    await session.commit()
    result = await session.execute(
        select(ClassGroup, Lecturer.full_name, func.count(Person.id))
        .outerjoin(Lecturer, Lecturer.id == ClassGroup.lecturer_id)
        .outerjoin(Person, Person.class_id == ClassGroup.id)
        .where(ClassGroup.id == class_id)
        .group_by(ClassGroup.id, Lecturer.full_name)
    )
    await container.cache.invalidate_cached("metrics")
    await _invalidate_classes_cache(container)
    return class_read(result.one())


@router.patch("/admin/classes/{class_id}/deactivate", response_model=ClassRead)
async def deactivate_class(class_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> ClassRead:
    class_group = await session.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kelas tidak ditemukan.")
    class_group.is_active = False
    await session.commit()
    result = await session.execute(
        select(ClassGroup, Lecturer.full_name, func.count(Person.id))
        .outerjoin(Lecturer, Lecturer.id == ClassGroup.lecturer_id)
        .outerjoin(Person, Person.class_id == ClassGroup.id)
        .where(ClassGroup.id == class_id)
        .group_by(ClassGroup.id, Lecturer.full_name)
    )
    await container.cache.invalidate_cached("metrics")
    await _invalidate_classes_cache(container)
    return class_read(result.one())


@router.patch("/admin/classes/{class_id}/reactivate", response_model=ClassRead)
async def reactivate_class(class_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> ClassRead:
    class_group = await session.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kelas tidak ditemukan.")
    class_group.is_active = True
    await session.commit()
    result = await session.execute(
        select(ClassGroup, Lecturer.full_name, func.count(Person.id))
        .outerjoin(Lecturer, Lecturer.id == ClassGroup.lecturer_id)
        .outerjoin(Person, Person.class_id == ClassGroup.id)
        .where(ClassGroup.id == class_id)
        .group_by(ClassGroup.id, Lecturer.full_name)
    )
    await container.cache.invalidate_cached("metrics")
    await _invalidate_classes_cache(container)
    return class_read(result.one())


WITA_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def session_date_matches(item: AttendanceSessionRead, selected_date: date_type | None) -> bool:
    if selected_date is None:
        return True
    if item.repeat_days is not None:
        day_name = WITA_DAY_NAMES[selected_date.weekday()]
        return day_name in item.repeat_days
    values = [value for value in (item.starts_at, item.ends_at) if value is not None]
    if not values:
        return True
    return any(value.astimezone().date() == selected_date for value in values)


@router.get("/admin/attendance-sessions", response_model=AttendanceSessionListResponse)
async def list_attendance_sessions(
    include_deleted: bool = False,
    class_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    date: date_type | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AttendanceSessionService = Depends(get_attendance_session_service),
) -> AttendanceSessionListResponse:
    try:
        items = await service.list_sessions(include_deleted=include_deleted)
    except TypeError:
        items = await service.list_sessions()
    if class_id is not None:
        items = [item for item in items if item.class_id == class_id]
    normalized_status = (status_filter or "").strip().lower()
    if normalized_status == "active":
        items = [item for item in items if item.is_active and not item.is_deleted]
    elif normalized_status == "inactive":
        items = [item for item in items if not item.is_active and not item.is_deleted]
    elif normalized_status in {"deleted", "archived"}:
        items = [item for item in items if item.is_deleted]
    items = [item for item in items if session_date_matches(item, date)]
    total = len(items)
    items = items[offset:offset + limit]
    return AttendanceSessionListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)


@router.post("/admin/attendance-sessions", response_model=AttendanceSessionRead, status_code=status.HTTP_201_CREATED)
async def create_attendance_session(
    request: AttendanceSessionCreateRequest,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> AttendanceSessionRead:
    try:
        payload = await service.create_session(request)
    except AttendanceSessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    return payload


@router.get("/admin/attendance-sessions/next-code", response_model=AttendanceSessionNextCodeResponse)
async def next_attendance_session_code(service: AttendanceSessionService = Depends(get_attendance_session_service)) -> AttendanceSessionNextCodeResponse:
    return AttendanceSessionNextCodeResponse(session_code=await service.next_session_code())


@router.get("/admin/attendance-sessions/{session_id}", response_model=AttendanceSessionRead)
async def get_attendance_session(session_id: UUID, service: AttendanceSessionService = Depends(get_attendance_session_service)) -> AttendanceSessionRead:
    payload = await service.get_session(session_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attendance session not found")
    return payload


@router.put("/admin/attendance-sessions/{session_id}", response_model=AttendanceSessionRead)
async def update_attendance_session(
    session_id: UUID,
    request: AttendanceSessionUpdateRequest,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> AttendanceSessionRead:
    try:
        payload = await service.update_session(session_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttendanceSessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    return payload


@router.patch("/admin/attendance-sessions/{session_id}/activate", response_model=AttendanceSessionRead)
async def activate_attendance_session(
    session_id: UUID,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> AttendanceSessionRead:
    try:
        payload = await service.activate_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    return payload


@router.patch("/admin/attendance-sessions/{session_id}/close", response_model=AttendanceSessionRead)
async def close_attendance_session(
    session_id: UUID,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> AttendanceSessionRead:
    try:
        payload = await service.close_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    return payload


@router.patch("/admin/attendance-sessions/{session_id}/deactivate", response_model=AttendanceSessionRead)
async def deactivate_attendance_session(
    session_id: UUID,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> AttendanceSessionRead:
    try:
        payload = await service.deactivate_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    return payload


@router.delete("/admin/attendance-sessions/{session_id}", response_model=AdminActionResponse)
async def delete_attendance_session(
    session_id: UUID,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> AdminActionResponse:
    try:
        result = await service.delete_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi absensi tidak ditemukan.") from exc
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    if result["status"] == "archived":
        return AdminActionResponse(status="ok", detail="Sesi diarsipkan. Riwayat absensi tidak akan hilang.")
    return AdminActionResponse(status="ok", detail="Sesi dihapus karena belum memiliki riwayat absensi.")


@router.get("/admin/attendance-logs", response_model=AttendanceLogListResponse)
async def list_attendance_logs(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AttendanceLogListResponse:
    count_result = await session.execute(
        select(func.count(AttendanceLog.id)).where(AttendanceLog.is_deleted.is_(False))
    )
    total = int(count_result.scalar_one())
    result = await session.execute(
        select(AttendanceLog, Person, AttendanceSession, ClassGroup)
        .outerjoin(Person, Person.id == AttendanceLog.person_id)
        .outerjoin(AttendanceSession, AttendanceSession.id == AttendanceLog.session_id)
        .outerjoin(ClassGroup, ClassGroup.id == Person.class_id)
        .where(AttendanceLog.is_deleted.is_(False))
        .order_by(AttendanceLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items: list[AttendanceLogAdminRead] = []
    for index, row in enumerate(result.all(), start=offset + 1):
        items.append(attendance_log_admin_read(row, index))
    return AttendanceLogListResponse(items=items, total=total, limit=limit, offset=offset, has_next=offset + limit < total)


@router.patch("/admin/attendance-logs/{log_id}", response_model=AttendanceLogAdminRead)
async def update_attendance_log(log_id: UUID, request: AttendanceLogUpdateRequest, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AttendanceLogAdminRead:
    log = await session.get(AttendanceLog, log_id)
    if log is None or log.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log absensi tidak ditemukan.")
    log.decision = normalize_attendance_decision(request.decision, request.reason)
    log.reason = normalize_attendance_reason(request.reason)
    await session.commit()
    result = await session.execute(
        select(AttendanceLog, Person, AttendanceSession, ClassGroup)
        .outerjoin(Person, Person.id == AttendanceLog.person_id)
        .outerjoin(AttendanceSession, AttendanceSession.id == AttendanceLog.session_id)
        .outerjoin(ClassGroup, ClassGroup.id == Person.class_id)
        .where(AttendanceLog.id == log_id)
    )
    row = result.one()
    await container.cache.invalidate_cached("metrics")
    return attendance_log_admin_read(row, 1)


@router.patch("/admin/attendance-logs/{log_id}/deactivate", response_model=AdminActionResponse)
async def deactivate_attendance_log(log_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AdminActionResponse:
    log = await session.get(AttendanceLog, log_id)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log absensi tidak ditemukan.")
    log.is_deleted = True
    await session.commit()
    await container.cache.invalidate_cached("metrics")
    return AdminActionResponse(status="ok", detail="Log absensi dinonaktifkan.")


@router.get("/admin/attendance-logs/{log_id}/image")
async def attendance_log_image(log_id: UUID, session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> FileResponse:
    log = await session.get(AttendanceLog, log_id)
    if log is None or not log.captured_image_uri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto absensi tidak tersedia.")
    path = secure_file_path(container.settings.object_storage_root, log.captured_image_uri)
    return FileResponse(path, media_type="image/jpeg")
