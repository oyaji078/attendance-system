from __future__ import annotations

from db.domain.attendance import normalize_attendance_decision, normalize_attendance_event_type, normalize_attendance_reason
from db.repositories.attendance import AttendanceRepository
from db.schemas.attendance import AttendanceLogItem, AttendanceLogsResponse, AttendanceStatusResponse


class AttendanceReadService:
    def __init__(self, attendance_repository: AttendanceRepository) -> None:
        self.attendance_repository = attendance_repository

    async def status(self, session_code: str) -> AttendanceStatusResponse | None:
        projection = await self.attendance_repository.get_status(session_code)
        if projection is None:
            return None
        return AttendanceStatusResponse(
            session_code=projection.session.session_code,
            session_name=projection.session.session_name,
            is_active=projection.session.is_active,
            total_logs=projection.total_logs,
            recognized=projection.recognized,
            cooldown=projection.cooldown,
            unknown=projection.unknown,
            last_event_at=projection.last_event_at,
        )

    async def logs(self, session_code: str) -> AttendanceLogsResponse:
        rows = await self.attendance_repository.list_logs(session_code)
        return AttendanceLogsResponse(
            session_code=session_code,
            items=[
                AttendanceLogItem(
                    id=log.id,
                    student_id=person.student_id if person else None,
                    full_name=person.full_name if person else None,
                    decision=normalize_attendance_decision(log.decision, log.reason),
                    reason=normalize_attendance_reason(log.reason),
                    confidence=log.confidence,
                    device_code=log.device_code,
                    event_type=normalize_attendance_event_type(log.event_type),
                    created_at=log.created_at,
                )
                for log, person in rows
            ],
        )
