from __future__ import annotations

import math

import pytest

pytest.importorskip("numpy")

from services.recognition.template_builder import TemplateBuilder


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def test_template_builder_returns_unit_vector() -> None:
    template = TemplateBuilder().build([[1.0, 0.0, 0.0], [0.8, 0.2, 0.0], [0.9, 0.1, 0.0]])
    norm = sum(value * value for value in template) ** 0.5
    assert pytest.approx(norm, rel=1e-5) == 1.0


def test_template_builder_filters_outlier() -> None:
    good = [[1.0, 0.0, 0.0], [0.98, 0.02, 0.0], [0.97, 0.03, 0.0], [0.99, 0.01, 0.0]]
    outlier = [0.0, 1.0, 0.0]
    template = TemplateBuilder().build(good + [outlier])

    good_avg = [sum(v) / len(v) for v in zip(*good)]
    sim_to_good = _cosine_sim(template, good_avg)
    sim_to_outlier = _cosine_sim(template, outlier)

    assert sim_to_good > sim_to_outlier
    assert sim_to_good > 0.95


def test_template_builder_does_not_over_filter_small_dataset() -> None:
    noisy = [
        [1.0, 0.0, 0.0],
        [0.6, 0.8, 0.0],
        [-0.5, 0.5, 0.7],
        [0.0, 1.0, 0.0],
    ]
    template = TemplateBuilder().build(noisy)
    norm = sum(v * v for v in template) ** 0.5
    assert pytest.approx(norm, rel=1e-5) == 1.0


def test_template_builder_keeps_minimum_half() -> None:
    embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [-1.0, 0.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.7, 0.7, 0.0],
        [0.0, 0.7, 0.7],
    ]
    template = TemplateBuilder().build(embeddings)
    norm = sum(v * v for v in template) ** 0.5
    assert pytest.approx(norm, rel=1e-5) == 1.0


def test_template_builder_raises_on_empty() -> None:
    with pytest.raises(ValueError, match="zero embeddings"):
        TemplateBuilder().build([])


def test_template_builder_raises_on_mixed_dimensions() -> None:
    with pytest.raises(ValueError, match="same dimension"):
        TemplateBuilder().build([[1.0, 0.0], [1.0, 0.0, 0.0]])
