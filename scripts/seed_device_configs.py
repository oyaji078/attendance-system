from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api-python"))

from app.core.config import get_settings  # noqa: E402
from db.models.database import build_engine, build_session_factory  # noqa: E402
from db.repositories.device_configs import DeviceConfigRepository  # noqa: E402


SEED_CONFIGS = [
    {
        "device_code": "gate-a01",
        "device_name": "Main Gate A01",
        "location_hint": "North gate",
        "det_thresh": 0.60,
        "det_size_width": 320,
        "det_size_height": 320,
        "max_faces": 1,
        "min_face_width_px": 160,
        "min_brightness": 75.0,
        "min_blur_score": 90.0,
        "similarity_threshold": 0.45,
        "liveness_threshold": 0.70,
        "multi_frame_confirm": 2,
        "accepted_per_pose": 4,
        "cooldown_seconds": 30,
        "is_enabled": True,
    }
]


async def main() -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    async with session_factory() as session:
        repository = DeviceConfigRepository(session)
        for config in SEED_CONFIGS:
            payload = dict(config)
            device_code = str(payload.pop("device_code"))
            await repository.upsert(device_code, payload)
        await session.commit()
    await engine.dispose()
    print(f"seeded {len(SEED_CONFIGS)} device configs")


if __name__ == "__main__":
    asyncio.run(main())
