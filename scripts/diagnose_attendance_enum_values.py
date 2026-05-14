from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
API_APP = ROOT / "apps" / "api-python"

for path in (ROOT, API_APP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.core.config import get_settings  # noqa: E402
from db.domain.attendance import CANONICAL_ATTENDANCE_DECISIONS, CANONICAL_ATTENDANCE_EVENT_TYPES, CANONICAL_SESSION_KINDS  # noqa: E402
from db.models.database import build_engine  # noqa: E402


async def distinct_invalid_values(connection, table: str, column: str, allowed: tuple[str, ...]) -> list[str]:
    allowed_values = ", ".join(f"'{value}'" for value in allowed)
    result = await connection.execute(
        text(
            f"""
            SELECT DISTINCT {column}
            FROM {table}
            WHERE {column} IS NULL
               OR lower(trim({column})) NOT IN ({allowed_values})
            ORDER BY {column}
            """
        )
    )
    return [str(row[0]) for row in result.fetchall()]


async def main() -> int:
    engine = build_engine(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            checks = [
                ("attendance_sessions", "session_kind", CANONICAL_SESSION_KINDS),
                ("attendance_logs", "decision", CANONICAL_ATTENDANCE_DECISIONS),
                ("attendance_logs", "event_type", CANONICAL_ATTENDANCE_EVENT_TYPES),
            ]
            found = False
            for table, column, allowed in checks:
                values = await distinct_invalid_values(connection, table, column, allowed)
                for value in values:
                    found = True
                    print(f"Invalid {table}.{column}: {value}")
            if not found:
                print("No invalid attendance enum values found.")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

