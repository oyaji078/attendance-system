param()

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = "D:\PythonVenvs\attendance-api\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

$ExistingPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$Root;$Root\apps\api-python;$ExistingPythonPath"

$Code = @'
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


async def scalar(session, sql: str) -> int:
    result = await session.execute(text(sql))
    return int(result.scalar_one() or 0)


def normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(Path(value).resolve()).lower()
    except Exception:
        return value.lower()


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as session:
        report: dict[str, object] = {}
        report["active_persons"] = await scalar(session, "SELECT count(*) FROM persons WHERE is_active = TRUE AND is_deleted = FALSE")
        report["inactive_or_deleted_persons"] = await scalar(session, "SELECT count(*) FROM persons WHERE is_active = FALSE OR is_deleted = TRUE")
        report["active_templates_for_active_persons"] = await scalar(
            session,
            """
            SELECT count(*)
            FROM face_templates ft
            JOIN persons p ON p.id = ft.person_id
            WHERE ft.is_active = TRUE
              AND ft.deleted_at IS NULL
              AND p.is_active = TRUE
              AND p.is_deleted = FALSE
            """,
        )
        report["inactive_templates"] = await scalar(session, "SELECT count(*) FROM face_templates WHERE is_active = FALSE OR deleted_at IS NOT NULL")
        report["orphan_templates"] = await scalar(
            session,
            """
            SELECT count(*)
            FROM face_templates ft
            LEFT JOIN persons p ON p.id = ft.person_id
            WHERE p.id IS NULL OR p.is_active = FALSE OR p.is_deleted = TRUE
            """,
        )
        report["templates_still_searchable_but_should_not_be"] = await scalar(
            session,
            """
            SELECT count(*)
            FROM face_templates ft
            LEFT JOIN persons p ON p.id = ft.person_id
            WHERE ft.is_active = TRUE
              AND ft.deleted_at IS NULL
              AND (p.id IS NULL OR p.is_active = FALSE OR p.is_deleted = TRUE OR p.primary_template_id IS NULL OR p.primary_template_id <> ft.id)
            """,
        )
        report["orphan_samples"] = await scalar(
            session,
            """
            SELECT count(*)
            FROM face_samples fs
            LEFT JOIN persons p ON p.id = fs.person_id
            WHERE fs.is_active = TRUE
              AND fs.is_deleted = FALSE
              AND (p.id IS NULL OR p.is_active = FALSE OR p.is_deleted = TRUE)
            """,
        )
        report["images_referenced_by_inactive_or_deleted_data"] = await scalar(
            session,
            """
            SELECT count(*)
            FROM face_samples fs
            LEFT JOIN persons p ON p.id = fs.person_id
            WHERE fs.image_uri IS NOT NULL
              AND (fs.is_active = FALSE OR fs.is_deleted = TRUE OR p.id IS NULL OR p.is_active = FALSE OR p.is_deleted = TRUE)
            """,
        )

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

        active_rows = await session.execute(
            text(
                """
                SELECT fs.image_uri AS path
                FROM face_samples fs
                JOIN persons p ON p.id = fs.person_id
                WHERE fs.image_uri IS NOT NULL
                  AND fs.is_active = TRUE
                  AND fs.is_deleted = FALSE
                  AND p.is_active = TRUE
                  AND p.is_deleted = FALSE
                """
            )
        )
        referenced_active = {normalize_path(row.path) for row in active_rows if normalize_path(row.path)}

    root = Path(settings.object_storage_root)
    image_files = []
    if root.exists():
        image_files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
    unreferenced = [str(path) for path in image_files if normalize_path(str(path)) not in referenced_any]
    not_active = [str(path) for path in image_files if normalize_path(str(path)) not in referenced_active]
    report["storage_root"] = str(root)
    report["image_files_total"] = len(image_files)
    report["orphan_image_files_unreferenced"] = len(unreferenced)
    report["image_files_not_referenced_by_active_face_data"] = len(not_active)
    report["sample_unreferenced_image_files"] = unreferenced[:25]
    report["sample_non_active_image_files"] = not_active[:25]

    print("Face data audit")
    for key, value in report.items():
        if not isinstance(value, list):
            print(f"- {key}: {value}")
    print("\nJSON report:")
    print(json.dumps(report, indent=2, default=str))
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
