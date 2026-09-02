"""The attendance percentage rule (spec §6).

    Persentase = Jumlah Hadir / Pertemuan yang Sudah Dilaksanakan x 100

A meeting that has not happened is not an Alpha — it must not enter the
denominator at all.
"""

from __future__ import annotations

import pytest

from services.academic.recap import (
    attendance_percent,
    average_percent,
    held_meeting_count,
    tally_student,
)


def test_percent_uses_held_meetings_as_denominator():
    assert attendance_percent(9, 12) == 75.0


def test_percent_uses_only_meetings_already_held():
    # 5 held, student present at 4 -> 80%, not 4/12.
    assert attendance_percent(4, 5) == 80.0


def test_percent_is_zero_when_nothing_held_yet():
    # No completed meeting means there is no attendance to report, and dividing
    # by zero is not an answer.
    assert attendance_percent(0, 0) == 0.0
    assert attendance_percent(3, 0) == 0.0


def test_held_meeting_count_ignores_planned_and_cancelled():
    statuses = ["held", "held", "planned", "cancelled", "held"]
    assert held_meeting_count(statuses) == 3


def test_tally_counts_each_status_separately():
    cells = ["H", "H", "A", "H"]
    statuses = ["held"] * 4
    tally = tally_student(cells, statuses)
    assert (tally.hadir, tally.sakit, tally.izin, tally.alpha) == (3, 0, 0, 1)
    assert tally.held_meetings == 4
    assert tally.attendance_percent == 75.0


def test_tally_handles_all_four_statuses():
    tally = tally_student(["H", "S", "I", "A"], ["held"] * 4)
    assert (tally.hadir, tally.sakit, tally.izin, tally.alpha) == (1, 1, 1, 1)
    assert tally.attendance_percent == 25.0


def test_unheld_meetings_are_not_counted_as_alpha():
    # 12 planned meetings, only 5 held, student present at 4 of them.
    cells = ["H", "H", "H", "A", "H"] + [None] * 7
    statuses = ["held"] * 5 + ["planned"] * 7
    tally = tally_student(cells, statuses)
    assert tally.held_meetings == 5
    assert tally.hadir == 4
    # The 7 empty future meetings did not become Alpha.
    assert tally.alpha == 1
    assert tally.attendance_percent == 80.0


def test_records_on_a_cancelled_meeting_are_excluded():
    # A meeting later marked cancelled must not drag the percentage down.
    cells = ["H", "A", "H"]
    statuses = ["held", "cancelled", "held"]
    tally = tally_student(cells, statuses)
    assert tally.held_meetings == 2
    assert tally.hadir == 2
    assert tally.alpha == 0
    assert tally.attendance_percent == 100.0


def test_missing_record_on_a_held_meeting_is_not_counted_as_present():
    cells = ["H", None, "H"]
    statuses = ["held"] * 3
    tally = tally_student(cells, statuses)
    assert tally.hadir == 2
    assert tally.held_meetings == 3
    assert tally.attendance_percent == pytest.approx(66.67)


def test_tally_rejects_misaligned_input():
    with pytest.raises(ValueError):
        tally_student(["H", "H"], ["held"])


def test_average_percent_over_class():
    assert average_percent([100.0, 75.0, 50.0]) == 75.0
    assert average_percent([]) == 0.0
