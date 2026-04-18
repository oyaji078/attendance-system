from __future__ import annotations

import pytest

pytest.importorskip("numpy")

from services.recognition.template_builder import TemplateBuilder


def test_template_builder_returns_unit_vector() -> None:
    template = TemplateBuilder().build([[1.0, 0.0, 0.0], [0.8, 0.2, 0.0], [0.9, 0.1, 0.0]])
    norm = sum(value * value for value in template) ** 0.5
    assert pytest.approx(norm, rel=1e-5) == 1.0

