from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from services.recognition.recognition_service import RecognitionService


class FakeAtomicRedis:
    """In-memory redis exposing the atomic GETDEL used for pending tokens."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def getdel(self, key: str) -> str | None:
        # dict.pop is atomic within the event loop — mirrors Redis GETDEL.
        value = self.store.pop(key, None)
        await asyncio.sleep(0)  # yield so concurrent validators interleave
        return value


class FakeCache:
    def __init__(self) -> None:
        self.redis = FakeAtomicRedis()


def _service(cache: FakeCache) -> RecognitionService:
    return RecognitionService(
        session=None,
        device_repository=None,
        attendance_repository=None,
        frame_processor=None,
        decision_engine=None,
        audit_logger=None,
        cache=cache,
    )


def _issue_token(service: RecognitionService, *, person_id, session_code, device_code, class_id):
    return asyncio.run(
        service._generate_pending_token(
            person_id=person_id, session_code=session_code, device_code=device_code, class_id=class_id
        )
    )


def test_valid_token_passes_and_is_single_use() -> None:
    cache = FakeCache()
    service = _service(cache)
    person_id, class_id = uuid4(), uuid4()
    token = _issue_token(service, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=class_id)

    first = asyncio.run(
        service._validate_pending_token(token, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=class_id)
    )
    second = asyncio.run(
        service._validate_pending_token(token, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=class_id)
    )
    assert first is True
    assert second is False  # reuse rejected


def test_token_bound_to_person_session_device() -> None:
    person_id, other_person = uuid4(), uuid4()

    scenarios = [
        {"person_id": other_person, "session_code": "S1", "device_code": "gate-a01"},  # person B
        {"person_id": person_id, "session_code": "S2", "device_code": "gate-a01"},     # session B
        {"person_id": person_id, "session_code": "S1", "device_code": "gate-b02"},     # device B
    ]
    for claim in scenarios:
        cache = FakeCache()
        service = _service(cache)
        token = _issue_token(service, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=None)
        result = asyncio.run(service._validate_pending_token(token, class_id=None, **claim))
        assert result is False, f"mismatched claim must be rejected: {claim}"
        # A mismatched claim burns the token: the rightful claim can no longer use it.
        replay = asyncio.run(
            service._validate_pending_token(
                token, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=None
            )
        )
        assert replay is False


def test_token_bound_to_class_when_both_sides_have_class() -> None:
    cache = FakeCache()
    service = _service(cache)
    person_id, class_a, class_b = uuid4(), uuid4(), uuid4()
    token = _issue_token(service, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=class_a)
    result = asyncio.run(
        service._validate_pending_token(token, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=class_b)
    )
    assert result is False


def test_missing_or_unknown_token_rejected() -> None:
    cache = FakeCache()
    service = _service(cache)
    assert asyncio.run(
        service._validate_pending_token("", person_id=uuid4(), session_code="S1", device_code="gate-a01", class_id=None)
    ) is False
    assert asyncio.run(
        service._validate_pending_token("nope", person_id=uuid4(), session_code="S1", device_code="gate-a01", class_id=None)
    ) is False


def test_malformed_token_payload_rejected() -> None:
    cache = FakeCache()
    service = _service(cache)
    cache.redis.store["pending-attendance:broken"] = "{not json"
    assert asyncio.run(
        service._validate_pending_token("broken", person_id=uuid4(), session_code="S1", device_code="gate-a01", class_id=None)
    ) is False


def test_concurrent_validation_only_one_wins() -> None:
    cache = FakeCache()
    service = _service(cache)
    person_id = uuid4()
    token = _issue_token(service, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=None)

    async def race():
        return await asyncio.gather(
            service._validate_pending_token(token, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=None),
            service._validate_pending_token(token, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=None),
        )

    results = asyncio.run(race())
    assert sorted(results) == [False, True], f"exactly one concurrent confirm may win, got {results}"


def test_token_payload_content_binds_expected_fields() -> None:
    cache = FakeCache()
    service = _service(cache)
    person_id, class_id = uuid4(), uuid4()
    token = _issue_token(service, person_id=person_id, session_code="S1", device_code="gate-a01", class_id=class_id)
    payload = json.loads(cache.redis.store[f"pending-attendance:{token}"])
    assert payload["person_id"] == str(person_id)
    assert payload["session_code"] == "S1"
    assert payload["device_code"] == "gate-a01"
    assert payload["class_id"] == str(class_id)
