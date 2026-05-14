from __future__ import annotations

import re
from typing import Literal, TypeAlias, cast


SessionKind: TypeAlias = Literal["lecture", "lab", "exam", "other"]
AttendanceDecision: TypeAlias = Literal["accepted", "rejected", "manual_approved", "manual_rejected"]
AttendanceEventType: TypeAlias = Literal["checkin", "checkout", "recognition_attempt"]
RecognitionDecision: TypeAlias = Literal["accepted", "rejected"]
RecognitionStatus: TypeAlias = Literal[
    "recognized",
    "unknown",
    "rejected",
    "cooldown",
    "session_inactive",
    "no_matching_session",
    "multiple_matching_sessions",
]

CANONICAL_SESSION_KINDS: tuple[SessionKind, ...] = ("lecture", "lab", "exam", "other")
CANONICAL_ATTENDANCE_DECISIONS: tuple[AttendanceDecision, ...] = (
    "accepted",
    "rejected",
    "manual_approved",
    "manual_rejected",
)
CANONICAL_ATTENDANCE_EVENT_TYPES: tuple[AttendanceEventType, ...] = ("checkin", "checkout", "recognition_attempt")
CANONICAL_RECOGNITION_STATUSES: tuple[RecognitionStatus, ...] = (
    "recognized",
    "unknown",
    "rejected",
    "cooldown",
    "session_inactive",
    "no_matching_session",
    "multiple_matching_sessions",
)
ATTENDANCE_SUCCESS_DECISIONS: tuple[str, ...] = ("accepted", "manual_approved", "recognized")
COOLDOWN_REASONS: tuple[str, ...] = ("cooldown", "person_on_cooldown")

_TOKEN_RE = re.compile(r"[^a-z0-9_]+")


def normalize_token(value: object, *, default: str = "") -> str:
    token = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    token = _TOKEN_RE.sub("_", token).strip("_")
    return token or default


def normalize_session_kind(value: object) -> SessionKind:
    token = normalize_token(value)
    if token == "class":
        # Legacy app data used "class" for a normal teaching session.
        return "lecture"
    if token in CANONICAL_SESSION_KINDS:
        return cast(SessionKind, token)
    return "other"


def normalize_attendance_reason(value: object | None) -> str:
    token = normalize_token(value, default="unspecified")
    aliases = {
        "person_on_cooldown": "cooldown",
        "cooldown_period": "cooldown",
        "recognized": "multi_frame_confirm_passed",
    }
    return aliases.get(token, token)


def normalize_attendance_decision(value: object, reason: object | None = None) -> AttendanceDecision:
    token = normalize_token(value)
    reason_token = normalize_attendance_reason(reason) if reason is not None else ""
    if token in CANONICAL_ATTENDANCE_DECISIONS:
        return cast(AttendanceDecision, token)
    if token in {"recognized", "accept", "success", "present"}:
        return "accepted"
    if token == "cooldown" or reason_token == "cooldown":
        return "rejected"
    return "rejected"


def normalize_attendance_log_fields(value: object, reason: object | None = None) -> tuple[AttendanceDecision, str]:
    normalized_reason = normalize_attendance_reason(reason)
    return normalize_attendance_decision(value, normalized_reason), normalized_reason


def normalize_attendance_event_type(value: object) -> AttendanceEventType:
    token = normalize_token(value)
    if token in {"recognize", "recognized", "recognition", "recognition_attempted"}:
        return "recognition_attempt"
    if token in CANONICAL_ATTENDANCE_EVENT_TYPES:
        return cast(AttendanceEventType, token)
    return "recognition_attempt"


def normalize_recognition_status(
    value: object | None = None,
    *,
    decision: object | None = None,
    reason: object | None = None,
) -> RecognitionStatus:
    status_token = normalize_token(value)
    if status_token in CANONICAL_RECOGNITION_STATUSES:
        return cast(RecognitionStatus, status_token)

    decision_token = normalize_token(decision)
    if decision_token in {"recognized", "accepted", "manual_approved"}:
        return "recognized"
    if decision_token == "cooldown":
        return "cooldown"
    if decision_token == "unknown":
        return "unknown"
    if decision_token in {"session_inactive", "no_matching_session", "multiple_matching_sessions"}:
        return cast(RecognitionStatus, decision_token)

    reason_token = normalize_attendance_reason(reason)
    if reason_token == "cooldown":
        return "cooldown"
    if reason_token in {
        "session_inactive",
        "attendance_session_inactive",
        "attendance_session_not_started",
        "attendance_session_ended",
        "attendance_session_deleted",
    }:
        return "session_inactive"
    if reason_token in {"no_matching_session", "multiple_matching_sessions"}:
        return cast(RecognitionStatus, reason_token)
    if reason_token in {"no_match_within_threshold", "distance_above_threshold", "multi_frame_confirm_failed"}:
        return "unknown"
    return "rejected"

