"""Reset an admin account password directly in the database.

Usage:
    python scripts/reset_admin_password.py --username admin
    python scripts/reset_admin_password.py --username admin --password "NewPass123!"

Without --password a random one is generated and printed once. Run from the
project root with the project virtualenv (the PowerShell wrapper handles both).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "apps" / "api-python") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "api-python"))


def database_url() -> str:
    user = os.environ.get("POSTGRES_USER", "attendance")
    password = os.environ.get("POSTGRES_PASSWORD", "attendance")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "attendance")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


async def reset(username: str, new_password: str) -> int:
    from sqlalchemy import text

    from app.core.security import hash_password
    from db.models.database import build_engine

    engine = build_engine(database_url())
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            result = await connection.execute(
                text(
                    "UPDATE admin_users SET password_hash = :hash, is_active = true, updated_at = now() "
                    "WHERE lower(username) = lower(:username)"
                ),
                {"hash": hash_password(new_password), "username": username},
            )
            await transaction.commit()
            if result.rowcount == 0:
                print(f"ERROR: admin user '{username}' not found.")
                return 1
            print(f"Password for '{username}' has been reset.")
            return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="new password (min 8 chars); omit to generate one")
    args = parser.parse_args()
    password = args.password or secrets.token_urlsafe(12)
    if len(password) < 8:
        parser.error("password must be at least 8 characters")
    exit_code = asyncio.run(reset(args.username, password))
    if exit_code == 0 and not args.password:
        print(f"Generated password (save it now, it is not stored anywhere else): {password}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
