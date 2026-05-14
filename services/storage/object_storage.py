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

    async def delete_paths(self, paths: list[str]) -> int:
        root = self.root.resolve()

        def delete_one(path_value: str) -> bool:
            target = Path(path_value).resolve()
            if not target.is_relative_to(root):
                return False
            if not target.is_file():
                return False
            target.unlink()
            return True

        deleted = 0
        for path in paths:
            if await asyncio.to_thread(delete_one, path):
                deleted += 1
        return deleted
