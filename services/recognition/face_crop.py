from __future__ import annotations

import cv2
import numpy as np


def crop_face_jpeg(frame: np.ndarray, bbox: tuple[float, float, float, float] | list[float], margin_ratio: float = 0.28) -> bytes:
    """Crop a face region using backend detection coordinates and encode as JPEG."""
    frame_height, frame_width = frame.shape[:2]
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame has invalid dimensions")

    x1, y1, x2, y2 = [float(value) for value in bbox]
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    margin_x = box_width * margin_ratio
    margin_y = box_height * margin_ratio

    left = max(0, int(round(x1 - margin_x)))
    top = max(0, int(round(y1 - margin_y)))
    right = min(frame_width, int(round(x2 + margin_x)))
    bottom = min(frame_height, int(round(y2 + margin_y * 1.15)))

    if right <= left or bottom <= top:
        raise ValueError("face crop is empty")

    crop = frame[top:bottom, left:right]
    ok, encoded = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise ValueError("face crop could not be encoded")
    return encoded.tobytes()
