"""Live-infrastructure integrity tests for attendance.

These tests exercise the real PostgreSQL unique index and real Redis token
atomicity. They skip automatically when the local dev infrastructure
(docker-compose.infra.yml) is not running, so the suite stays green in
environments without Postgres/Redis.

All database writes happen inside a transaction that is rolled back — no data
is persisted.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy.exc import IntegrityError

DATABASE_URL = (
    "postgresql+asyncpg://"
    f"{os.environ.get('POSTGRES_USER', 'attendance')}:{os.environ.get('POSTGRES_PASSWORD', 'attendance')}"
    f"@{os.environ.get('POSTGRES_HOST', '127.0.0.1')}:{os.environ.get('POSTGRES_PORT', '5432')}"
    f"/{os.environ.get('POSTGRES_DB', 'attendance')}"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")


def _database_available() -> bool:
    async def probe() -> bool:
        from db.models.database import build_engine

        try:
            engine = build_engine(DATABASE_URL)
            async with engine.connect():
                pass
            await engine.dispose()
            return True
        except Exception:
            return False

    return asyncio.run(probe())


def _redis_available() -> bool:
    async def probe() -> bool:
        from redis.asyncio import Redis

        try:
            client = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
            await client.ping()
            await client.aclose()
            return True
        except Exception:
            return False

    return asyncio.run(probe())


requires_database = pytest.mark.skipif(not _database_available(), reason="PostgreSQL dev infrastructure not running")
requires_redis = pytest.mark.skipif(not _redis_available(), reason="Redis dev infrastructure not running")


def _make_graph(session):
    from db.models.entities import AttendanceSession, ClassGroup, Person

    class_group = ClassGroup(id=uuid4(), class_code=f"ITG-{uuid4().hex[:8]}", class_name="Integrity Test Class")
    person = Person(id=uuid4(), student_id=f"ITG-{uuid4().hex[:8]}", full_name="Integrity Test", class_id=class_group.id)
    attendance_session = AttendanceSession(
        id=uuid4(),
        session_code=f"ITG-{uuid4().hex[:8]}",
        session_name="Integrity Test Session",
        session_kind="lecture",
        class_id=class_group.id,
        cooldown_seconds=30,
        is_active=True,
    )
    session.add_all([class_group, person, attendance_session])
    return person, attendance_session


def _accepted_log(session_id, person_id):
    from db.models.entities import AttendanceLog

    return AttendanceLog(
        id=uuid4(),
        session_id=session_id,
        person_id=person_id,
        device_code="gate-a01",
        event_type="checkin",
        decision="accepted",
        reason="confirmed_by_user",
        frame_count=0,
    )


@requires_database
def test_daily_unique_index_blocks_second_accepted_log() -> None:
    async def scenario() -> None:
        from db.models.database import build_engine, build_session_factory

        engine = build_engine(DATABASE_URL)
        factory = build_session_factory(engine)
        try:
            async with factory() as session:
                person, attendance_session = _make_graph(session)
                await session.flush()
                session.add(_accepted_log(attendance_session.id, person.id))
                await session.flush()
                session.add(_accepted_log(attendance_session.id, person.id))
                with pytest.raises(IntegrityError) as excinfo:
                    await session.flush()
                assert "uq_attendance_logs_accepted_once_per_day" in str(excinfo.value.orig)
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@requires_database
def test_daily_unique_index_allows_rejected_log_same_day() -> None:
    async def scenario() -> None:
        from db.models.database import build_engine, build_session_factory
        from db.models.entities import AttendanceLog

        engine = build_engine(DATABASE_URL)
        factory = build_session_factory(engine)
        try:
            async with factory() as session:
                person, attendance_session = _make_graph(session)
                await session.flush()
                session.add(_accepted_log(attendance_session.id, person.id))
                await session.flush()
                # A rejected attempt the same day must not be blocked.
                session.add(
                    AttendanceLog(
                        id=uuid4(),
                        session_id=attendance_session.id,
                        person_id=person.id,
                        device_code="gate-a01",
                        event_type="checkin",
                        decision="rejected",
                        reason="cooldown",
                        frame_count=0,
                    )
                )
                await session.flush()
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@requires_redis
def test_pending_token_single_use_under_real_redis_concurrency() -> None:
    async def scenario() -> None:
        from redis.asyncio import Redis

        from services.attendance.cache import RedisStateCache
        from services.recognition.recognition_service import RecognitionService

        client = Redis.from_url(REDIS_URL, decode_responses=True)
        cache = RedisStateCache(client, 30, 15)
        service = RecognitionService(
            session=None,
            device_repository=None,
            attendance_repository=None,
            frame_processor=None,
            decision_engine=None,
            audit_logger=None,
            cache=cache,
        )
        person_id = uuid4()
        try:
            for _ in range(20):
                token = await service._generate_pending_token(
                    person_id=person_id, session_code="ITG-S", device_code="gate-a01", class_id=None
                )
                results = await asyncio.gather(
                    service._validate_pending_token(
                        token, person_id=person_id, session_code="ITG-S", device_code="gate-a01", class_id=None
                    ),
                    service._validate_pending_token(
                        token, person_id=person_id, session_code="ITG-S", device_code="gate-a01", class_id=None
                    ),
                )
                assert sorted(results) == [False, True], f"token replay detected: {results}"
        finally:
            await client.aclose()

    asyncio.run(scenario())
