from __future__ import annotations

import base64
import binascii


def decode_frame_b64(frame_b64: str) -> bytes:
    payload = frame_b64.split(",", maxsplit=1)[-1]
    try:
        decoded = base64.b64decode(payload, validate=True)
    except binascii.Error as exc:
        raise ValueError("invalid base64 frame payload") from exc
    if not decoded:
        raise ValueError("frame payload decoded to empty bytes")
    return decoded
