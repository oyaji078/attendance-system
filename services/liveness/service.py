from __future__ import annotations

import cv2
import numpy as np

from services.recognition.types import LivenessResult


class HeuristicPassiveLivenessService:
    async def score(self, frame: np.ndarray) -> LivenessResult:
        grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(grayscale)) / 255.0
        blur = float(cv2.Laplacian(grayscale, cv2.CV_64F).var())
        blur_normalized = min(1.0, blur / 150.0)
        brightness_normalized = 1.0 - min(abs(brightness - 0.5) / 0.5, 1.0)
        score = round((0.55 * blur_normalized) + (0.45 * brightness_normalized), 4)
        return LivenessResult(
            score=score,
            mode="heuristic_passive_baseline",
            implemented=True,
            details={"blur_normalized": blur_normalized, "brightness_normalized": brightness_normalized},
        )

