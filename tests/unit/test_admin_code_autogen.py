"""Auto-generation of lecturer/class codes when the admin leaves them blank."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")

from app.api.routes.admin import resolve_class_code, resolve_lecturer_code


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


class FakeSession:
    """Returns a fixed set of existing codes for any select()."""

    def __init__(self, existing):
        self._existing = existing
        self.executed = 0

    async def execute(self, _statement):
        self.executed += 1
        return FakeScalarResult(self._existing)


def test_lecturer_code_generated_when_blank() -> None:
    session = FakeSession([])
    code = asyncio.run(resolve_lecturer_code(session, None))
    assert code == "DSN-0001"
    assert session.executed == 1


def test_lecturer_code_fills_first_gap() -> None:
    session = FakeSession(["DSN-0001", "DSN-0003"])
    code = asyncio.run(resolve_lecturer_code(session, "   "))
    assert code == "DSN-0002"


def test_lecturer_code_preserves_explicit_value() -> None:
    session = FakeSession(["DSN-0001"])
    code = asyncio.run(resolve_lecturer_code(session, "PROF-BUDI"))
    assert code == "PROF-BUDI"
    assert session.executed == 0  # no scan when a code is supplied


def test_class_code_generated_when_blank() -> None:
    session = FakeSession(["KLS-0001", "KLS-0002"])
    code = asyncio.run(resolve_class_code(session, ""))
    assert code == "KLS-0003"


def test_class_code_preserves_explicit_value() -> None:
    session = FakeSession([])
    code = asyncio.run(resolve_class_code(session, "TI5A"))
    assert code == "TI5A"


def test_code_generation_ignores_malformed_existing() -> None:
    session = FakeSession(["KLS-abc", "KLS-0002", None, "KLS-"])
    code = asyncio.run(resolve_class_code(session, None))
    # Only KLS-0002 is a valid numbered code, so the next free slot is 0001.
    assert code == "KLS-0001"
