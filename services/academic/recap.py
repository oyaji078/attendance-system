"""Attendance recap arithmetic.

Pure functions, no database and no ORM objects, so the percentage rule can be
tested directly and reused by any caller (API response, Excel export, PDF).

The rule (spec §6):

    Persentase Kehadiran = Jumlah Hadir / Jumlah Pertemuan yang Sudah
                           Dilaksanakan x 100

Only meetings with status ``held`` count toward the denominator. A meeting that
has not happened yet is *not* an Alpha — it simply does not participate, so a
student with 4 H out of 5 held meetings reads 80%, not 33% because the term
plans 12.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Statuses that are not "H" still consume a held meeting; they just are not
# presence. Kept explicit so a future status (e.g. "D" for dispensasi) has one
# obvious place to be classified.
PRESENT_STATUS = "H"
COUNTED_STATUSES: tuple[str, ...] = ("H", "S", "I", "A")


@dataclass(slots=True)
class StudentTally:
    hadir: int = 0
    sakit: int = 0
    izin: int = 0
    alpha: int = 0
    held_meetings: int = 0
    attendance_percent: float = 0.0
    cells: list[str | None] = field(default_factory=list)


_STATUS_FIELD = {"H": "hadir", "S": "sakit", "I": "izin", "A": "alpha"}


def held_meeting_count(meeting_statuses: list[str]) -> int:
    """Number of meetings that actually took place."""
    return sum(1 for status in meeting_statuses if status == "held")


def attendance_percent(present: int, held: int) -> float:
    """Percentage of held meetings the student was present for.

    Returns 0.0 when nothing has been held yet — with no meetings completed
    there is no attendance to report, and dividing by zero is not an answer.
    """
    if held <= 0:
        return 0.0
    return round((present / held) * 100.0, 2)


def tally_student(cells: list[str | None], meeting_statuses: list[str]) -> StudentTally:
    """Summarise one student's row.

    ``cells`` and ``meeting_statuses`` are aligned by index — ``cells[i]`` is the
    student's H/S/I/A for the meeting whose status is ``meeting_statuses[i]``,
    or ``None`` when no attendance was recorded for that student.
    """
    if len(cells) != len(meeting_statuses):
        raise ValueError("cells and meeting_statuses must have the same length")

    tally = StudentTally(cells=list(cells))
    for status, meeting_status in zip(cells, meeting_statuses, strict=True):
        # A record attached to a cancelled or not-yet-held meeting is ignored in
        # the totals: it would otherwise skew a recap taken mid-term.
        if meeting_status != "held":
            continue
        if status in _STATUS_FIELD:
            setattr(tally, _STATUS_FIELD[status], getattr(tally, _STATUS_FIELD[status]) + 1)
    tally.held_meetings = held_meeting_count(meeting_statuses)
    tally.attendance_percent = attendance_percent(tally.hadir, tally.held_meetings)
    return tally


def average_percent(percents: list[float]) -> float:
    if not percents:
        return 0.0
    return round(sum(percents) / len(percents), 2)
