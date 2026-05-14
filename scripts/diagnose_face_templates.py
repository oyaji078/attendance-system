from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import asyncpg


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env.local-api"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        os.environ.setdefault(key.strip(), raw.strip())


async def connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "attendance"),
        password=os.environ.get("POSTGRES_PASSWORD", "attendance"),
        database=os.environ.get("POSTGRES_DB", "attendance"),
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose active face template distances.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--warning-threshold", type=float, default=0.08)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    load_env_file(args.env_file)
    conn = await connect()
    try:
        counts = await conn.fetchrow(
            """
            SELECT
                (SELECT count(*) FROM persons) AS total_persons,
                (SELECT count(*) FROM persons WHERE is_active = true) AS active_persons,
                (SELECT count(*) FROM face_templates) AS total_templates,
                (SELECT count(*) FROM face_templates WHERE is_active = true) AS active_templates
            """
        )
        dimensions = await conn.fetch(
            """
            SELECT vector_dims(embedding) AS dimension, count(*) AS template_count
            FROM face_templates
            GROUP BY vector_dims(embedding)
            ORDER BY dimension
            """
        )
        pairs = await conn.fetch(
            """
            SELECT
                p1.student_id AS student_id_1,
                p1.full_name AS full_name_1,
                p2.student_id AS student_id_2,
                p2.full_name AS full_name_2,
                ft1.id::text AS template_id_1,
                ft2.id::text AS template_id_2,
                (ft1.embedding <=> ft2.embedding) AS distance
            FROM face_templates ft1
            JOIN persons p1 ON p1.id = ft1.person_id
            JOIN face_templates ft2 ON ft1.id < ft2.id
            JOIN persons p2 ON p2.id = ft2.person_id
            WHERE ft1.is_active = true
              AND ft2.is_active = true
            ORDER BY ft1.embedding <=> ft2.embedding
            LIMIT $1
            """,
            args.limit,
        )
        sample_pairs = await conn.fetch(
            """
            SELECT
                p1.student_id AS student_id_1,
                p1.full_name AS full_name_1,
                p2.student_id AS student_id_2,
                p2.full_name AS full_name_2,
                fs1.pose AS pose_1,
                fs2.pose AS pose_2,
                fs1.id::text AS sample_id_1,
                fs2.id::text AS sample_id_2,
                (fs1.embedding <=> fs2.embedding) AS distance
            FROM face_samples fs1
            JOIN persons p1 ON p1.id = fs1.person_id
            JOIN face_samples fs2 ON fs1.id < fs2.id
            JOIN persons p2 ON p2.id = fs2.person_id
            WHERE p1.is_active = true
              AND p2.is_active = true
              AND p1.id <> p2.id
            ORDER BY fs1.embedding <=> fs2.embedding
            LIMIT $1
            """,
            args.limit,
        )
    finally:
        await conn.close()

    print("Face template diagnostics")
    print(f"Total persons: {counts['total_persons']}")
    print(f"Active persons: {counts['active_persons']}")
    print(f"Total templates: {counts['total_templates']}")
    print(f"Active templates: {counts['active_templates']}")
    print("Template vector dimensions:")
    for row in dimensions:
        print(f"  dimension {row['dimension']}: {row['template_count']} templates")

    print(f"Closest active template pairs (limit {args.limit}):")
    if not pairs:
        print("  No active template pairs found.")
        return

    suspicious_count = 0
    for row in pairs:
        distance = float(row["distance"])
        label_1 = f"{row['full_name_1']} ({row['student_id_1']})"
        label_2 = f"{row['full_name_2']} ({row['student_id_2']})"
        marker = "WARNING" if distance < args.warning_threshold else "OK"
        print(f"  {marker}: {label_1} <-> {label_2} distance={distance:.6f}")
        if distance < args.warning_threshold:
            suspicious_count += 1
            print(
                f"    Template {row['full_name_1']} and {row['full_name_2']} are too similar. "
                "Enrollment samples may be duplicated, poor quality, or need re-enrollment."
            )

    print(f"Suspiciously close pairs below {args.warning_threshold:.3f}: {suspicious_count}")

    print(f"Closest cross-person sample pairs (limit {args.limit}):")
    if not sample_pairs:
        print("  No cross-person sample pairs found.")
        return

    sample_warning_count = 0
    sample_threshold = max(args.warning_threshold, 0.12)
    for row in sample_pairs:
        distance = float(row["distance"])
        label_1 = f"{row['full_name_1']} ({row['student_id_1']}, {row['pose_1']})"
        label_2 = f"{row['full_name_2']} ({row['student_id_2']}, {row['pose_2']})"
        marker = "WARNING" if distance < sample_threshold else "OK"
        print(f"  {marker}: {label_1} <-> {label_2} distance={distance:.6f}")
        if distance < sample_threshold:
            sample_warning_count += 1
            print(
                f"    Template {row['full_name_1']} dan {row['full_name_2']} terlalu dekat. "
                "Disarankan re-enrollment dengan pencahayaan dan jarak yang lebih konsisten."
            )

    print(f"Suspiciously close cross-person sample pairs below {sample_threshold:.3f}: {sample_warning_count}")


if __name__ == "__main__":
    asyncio.run(main())
