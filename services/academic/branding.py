"""School identity shared by every exported document.

Both exports (PDF and Excel) render the same letterhead, so the logo and school
name are read here once instead of being wired separately into each writer.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from io import BytesIO
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AppSetting

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Branding:
    school_name: str = "Sistem Absensi"
    logo_bytes: bytes | None = None

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_bytes)

    def logo_stream(self) -> BytesIO | None:
        # A fresh stream per call: both writers consume it, and a rewound shared
        # buffer is an easy way to ship an empty image into one of them.
        return BytesIO(self.logo_bytes) if self.logo_bytes else None


def decode_logo(data_uri: str | None) -> bytes | None:
    """Bytes from a validated data URI, or ``None`` if it cannot be used.

    Never raises: a corrupt logo must not take an export down with it.
    """
    if not data_uri or "," not in data_uri:
        return None
    try:
        return base64.b64decode(data_uri.split(",", 1)[1], validate=True)
    except (binascii.Error, ValueError):
        LOGGER.warning("export_logo_unreadable")
        return None


async def load_branding(session: AsyncSession) -> Branding:
    rows = (await session.execute(
        select(AppSetting).where(AppSetting.key.in_(("school_name", "school_logo")))
    )).scalars().all()
    values = {row.key: row.value for row in rows}
    return Branding(
        school_name=(values.get("school_name") or "Sistem Absensi").strip() or "Sistem Absensi",
        logo_bytes=decode_logo(values.get("school_logo")),
    )
