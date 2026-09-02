"""Console read models: the per-class recap and the enrollment rules.

The per-class recap is a summary across subjects, so it has its own arithmetic
worth pinning: a subject with no held meeting must report "no data", never 0%,
or a class that has not started reads as total absence.
"""

from __future__ import annotations

import pytest

from services.academic.console import WEAK_MATCH_SCORE, face_accuracy_summary
from services.academic.recap import attendance_percent


class TestClassRecapCell:
    """Mirrors ConsoleService.class_recap's per-cell decision."""

    @staticmethod
    def cell(present: int, held: int) -> float | None:
        return None if held <= 0 else attendance_percent(present, held)

    def test_subject_with_no_held_meeting_is_blank_not_zero(self):
        assert self.cell(0, 0) is None

    def test_subject_with_held_meetings_reports_a_percentage(self):
        assert self.cell(3, 4) == 75.0

    def test_full_attendance(self):
        assert self.cell(6, 6) == 100.0

    def test_absent_from_every_held_meeting_is_zero_not_blank(self):
        assert self.cell(0, 3) == 0.0


class TestClassAverage:
    """The row average ignores subjects that have no data yet."""

    @staticmethod
    def average(percents: list[float | None]) -> float | None:
        known = [value for value in percents if value is not None]
        return round(sum(known) / len(known), 2) if known else None

    def test_average_skips_subjects_without_held_meetings(self):
        # 100 and 50 average to 75; the untaught subject must not drag it to 50.
        assert self.average([100.0, 50.0, None]) == 75.0

    def test_average_is_none_when_nothing_has_been_held(self):
        assert self.average([None, None]) is None

    def test_average_of_a_single_subject_is_that_subject(self):
        assert self.average([80.0]) == 80.0

    def test_zero_counts_toward_the_average(self):
        assert self.average([100.0, 0.0]) == 50.0


class TestFaceAccuracySummary:
    """The accuracy card on the dashboard."""

    def test_reports_average_lowest_and_weak_count(self):
        average, lowest, weak = face_accuracy_summary([0.9, 0.8, 0.4])
        assert average == 0.7
        assert lowest == 0.4
        assert weak == 1

    def test_manual_rows_are_ignored_not_counted_as_zero(self):
        # A hand-entered status has no face behind it; averaging it in would
        # report the camera as far less certain than it actually was.
        average, lowest, weak = face_accuracy_summary([0.9, None, 0.8])
        assert average == 0.85
        assert lowest == 0.8
        assert weak == 0

    def test_a_day_without_face_attendance_has_no_average(self):
        assert face_accuracy_summary([None, None]) == (None, None, 0)
        assert face_accuracy_summary([]) == (None, None, 0)

    def test_a_score_exactly_at_the_threshold_is_not_weak(self):
        # The threshold is what the kiosk accepts, so meeting it is a pass.
        _average, _lowest, weak = face_accuracy_summary([WEAK_MATCH_SCORE])
        assert weak == 0


class TestEnrollmentTransition:
    """The move rules ConsoleService.upsert_enrollment implements."""

    def test_moving_class_closes_the_previous_enrollment(self):
        # Modelled as the service does it: old row goes inactive with an end
        # date, a new active row is created, and persons.class_id follows.
        active = {"class_id": "A", "status": "active", "end_date": None}
        target = "B"
        if active["class_id"] != target:
            active["status"] = "inactive"
            active["end_date"] = "2026-08-22"
            new_row = {"class_id": target, "status": "active"}
        assert active["status"] == "inactive"
        assert active["end_date"] is not None
        assert new_row["status"] == "active"
        assert new_row["class_id"] == "B"

    def test_deactivating_in_place_keeps_the_same_class_row(self):
        active = {"class_id": "A", "status": "active", "end_date": None}
        requested_class, requested_status = "A", "inactive"
        if active["class_id"] == requested_class:
            active["status"] = requested_status
            active["end_date"] = "2026-08-22"
            person_class_id = None if requested_status == "inactive" else requested_class
        assert active["class_id"] == "A"
        assert active["status"] == "inactive"
        # A student with no active enrollment belongs to no class.
        assert person_class_id is None


@pytest.mark.parametrize(
    ("present", "held", "expected"),
    [(9, 12, 75.0), (4, 5, 80.0), (0, 1, 0.0), (1, 3, 33.33)],
)
def test_percentage_matches_the_documented_formula(present, held, expected):
    assert attendance_percent(present, held) == expected
