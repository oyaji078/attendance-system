from __future__ import annotations

import asyncio
from pathlib import Path


class LocalObjectStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def put_bytes(self, object_key: str, payload: bytes) -> str:
        target_path = self.root / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target_path.write_bytes, payload)
        return target_path.as_posix()

