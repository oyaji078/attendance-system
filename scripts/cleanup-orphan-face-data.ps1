param(
  [switch]$Apply,
  [switch]$DeleteFiles
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = "D:\PythonVenvs\attendance-api\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

$ExistingPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$Root;$Root\apps\api-python;$ExistingPythonPath"
$env:FACE_CLEANUP_APPLY = if ($Apply) { "1" } else { "0" }
$env:FACE_CLEANUP_DELETE_FILES = if ($DeleteFiles) { "1" } else { "0" }

$Code = @'
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
APPLY = os.environ.get("FACE_CLEANUP_APPLY") == "1"
DELETE_FILES = os.environ.get("FACE_CLEANUP_DELETE_FILES") == "1"


def normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(Path(value).resolve()).lower()
    except Exception:
        return value.lower()


async def scalar(session, sql: str) -> int:
    result = await session.execute(text(sql))
    return int(result.scalar_one() or 0)


async def execute_count(session, sql: str) -> int:
    result = await session.execute(text(sql))
    return int(result.rowcount or 0)


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    template_condition = """
        ft.is_active = TRUE
        AND ft.deleted_at IS NULL
        AND EXISTS (
            SELECT 1
            FROM persons p
            WHERE p.id = ft.person_id
              AND (p.is_active = FALSE OR p.is_deleted = TRUE OR p.primary_template_id IS NULL OR p.primary_template_id <> ft.id)
        )
    """
    sample_condition = """
        fs.is_active = TRUE
        AND fs.is_deleted = FALSE
        AND EXISTS (
            SELECT 1
            FROM persons p
            WHERE p.id = fs.person_id
              AND (
                p.is_active = FALSE
                OR p.is_deleted = TRUE
                OR p.primary_template_id IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM face_templates ft
                    WHERE ft.person_id = p.id
                      AND ft.is_active = TRUE
                      AND ft.deleted_at IS NULL
                )
              )
        )
    """
    invalid_primary_condition = """
        p.primary_template_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM face_templates ft
            WHERE ft.id = p.primary_template_id
              AND ft.is_active = TRUE
              AND ft.deleted_at IS NULL
        )
    """

    async with engine.begin() as session:
        planned = {
            "templates_to_deactivate": await scalar(session, f"SELECT count(*) FROM face_templates ft WHERE {template_condition}"),
            "samples_to_hide": await scalar(session, f"SELECT count(*) FROM face_samples fs WHERE {sample_condition}"),
            "invalid_primary_template_refs_to_clear": await scalar(session, f"SELECT count(*) FROM persons p WHERE {invalid_primary_condition}"),
        }

        referenced_rows = await session.execute(
            text(
                """
                SELECT image_uri AS path FROM face_samples WHERE image_uri IS NOT NULL
                UNION
                SELECT captured_image_uri AS path FROM attendance_logs WHERE captured_image_uri IS NOT NULL
                """
            )
        )
        referenced_any = {normalize_path(row.path) for row in referenced_rows if normalize_path(row.path)}

        if APPLY:
            planned["templates_deactivated"] = await execute_count(
                session,
                f"""
                UPDATE face_templates ft
                SET is_active = FALSE,
                    deleted_at = COALESCE(deleted_at, now())
                WHERE {template_condition}
                """,
            )
            planned["samples_hidden"] = await execute_count(
                session,
                f"""
                UPDATE face_samples fs
                SET is_active = FALSE,
                    is_deleted = TRUE,
                    deleted_at = COALESCE(deleted_at, now())
                WHERE {sample_condition}
                """,
            )
            planned["primary_template_refs_cleared"] = await execute_count(
                session,
                f"""
                UPDATE persons p
                SET primary_template_id = NULL
                WHERE {invalid_primary_condition}
                """,
            )
        else:
            await session.rollback()

    root = Path(settings.object_storage_root).resolve()
    image_files = []
    if root.exists():
        image_files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
    unreferenced = [path for path in image_files if normalize_path(str(path)) not in referenced_any]
    planned["unreferenced_image_files"] = len(unreferenced)
    planned["sample_unreferenced_image_files"] = [str(path) for path in unreferenced[:25]]
    planned["files_deleted"] = 0

    if APPLY and DELETE_FILES:
        deleted = 0
        for path in unreferenced:
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                continue
            try:
                resolved.unlink()
                deleted += 1
            except FileNotFoundError:
                pass
        planned["files_deleted"] = deleted

    print("Face data cleanup")
    print(f"- mode: {'APPLY' if APPLY else 'DRY RUN'}")
    print(f"- delete_files: {DELETE_FILES}")
    for key, value in planned.items():
        if not isinstance(value, list):
            print(f"- {key}: {value}")
    if not APPLY:
        print("No changes were written. Re-run with -Apply to update DB rows.")
    elif not DELETE_FILES:
        print("DB rows were updated. No physical files were deleted because -DeleteFiles was not passed.")
    await engine.dispose()


asyncio.run(main())
'@

$Temp = New-TemporaryFile
try {
  Set-Content -LiteralPath $Temp -Value $Code -Encoding UTF8
  Push-Location $Root
  & $Python $Temp
  Pop-Location
} finally {
  Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
}
