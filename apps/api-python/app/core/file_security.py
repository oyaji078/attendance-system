from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status


def secure_file_path(base_dir: str | Path, requested_path: str | Path) -> Path:
    base = Path(base_dir).resolve()
    requested = Path(requested_path)
    if not requested.is_absolute():
        requested = (base / requested).resolve()
    else:
        requested = requested.resolve()
    try:
        requested.relative_to(base)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses file ditolak.",
        )
    if not requested.exists() or not requested.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File tidak ditemukan.",
        )
    return requested
