"""Recognition threshold calibration harness.

Usage (real calibration — requires a labeled face dataset):

    python scripts/calibrate_thresholds.py --dataset D:/path/to/dataset

    Dataset layout: one directory per person, >= 2 face images each:
        dataset/
          person_001/ a.jpg b.jpg c.jpg
          person_002/ a.jpg b.jpg

    The harness embeds every image with the SAME pipeline used in production
    (InsightFace buffalo_l, L2-normalized, cosine distance), then reports the
    genuine/impostor distance distributions and the threshold + margin that
    meet a target false-accept rate.

Self-test (validates the calibration math with synthetic embeddings only —
NOT a real calibration):

    python scripts/calibrate_thresholds.py --self-test

Output thresholds map to settings:
    similarity(distance) threshold -> DEVICE similarity_threshold
    candidate margin               -> DEVICE candidate_margin_threshold
    confidence (1 - distance)      -> RECOGNITION_CONFIDENCE_THRESHOLD
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(1.0 - np.dot(a, b))


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    return matrix / np.clip(np.linalg.norm(matrix, axis=-1, keepdims=True), 1e-12, None)


def pair_distances(embeddings_by_person: dict[str, list[np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    genuine: list[float] = []
    impostor: list[float] = []
    people = list(embeddings_by_person)
    for person in people:
        for a, b in itertools.combinations(embeddings_by_person[person], 2):
            genuine.append(cosine_distance(a, b))
    for pa, pb in itertools.combinations(people, 2):
        for a in embeddings_by_person[pa]:
            for b in embeddings_by_person[pb]:
                impostor.append(cosine_distance(a, b))
    return np.asarray(genuine), np.asarray(impostor)


def calibrate(genuine: np.ndarray, impostor: np.ndarray, target_far: float = 0.001) -> dict[str, float]:
    """Pick the distance threshold whose false-accept rate <= target_far,
    then report the false-reject rate that threshold costs."""
    if genuine.size == 0 or impostor.size == 0:
        raise ValueError("need both genuine and impostor pairs to calibrate")
    candidates = np.unique(np.concatenate([genuine, impostor]))
    best = None
    for threshold in candidates:
        far = float((impostor <= threshold).mean())
        if far <= target_far:
            frr = float((genuine > threshold).mean())
            best = {"distance_threshold": float(threshold), "far": far, "frr": frr}
    if best is None:
        # even the smallest threshold admits impostors — report the floor
        threshold = float(candidates[0])
        best = {
            "distance_threshold": threshold,
            "far": float((impostor <= threshold).mean()),
            "frr": float((genuine > threshold).mean()),
        }
    # candidate margin: gap between worst genuine and best impostor
    best["suggested_margin"] = max(0.0, float(impostor.min() - genuine.max()))
    best["confidence_threshold"] = 1.0 - best["distance_threshold"]
    return best


def describe(name: str, values: np.ndarray) -> str:
    return (
        f"{name:9s} n={values.size:6d} mean={values.mean():.4f} std={values.std():.4f} "
        f"min={values.min():.4f} p5={np.percentile(values, 5):.4f} "
        f"p95={np.percentile(values, 95):.4f} max={values.max():.4f}"
    )


def run_dataset(dataset_dir: Path, target_far: float) -> int:
    from services.recognition.pipeline import InsightFaceEmbeddingPipeline  # heavy import

    import asyncio

    from app.core.config import get_settings

    settings = get_settings()
    pipeline = InsightFaceEmbeddingPipeline(
        settings.insightface_model_name, settings.insightface_model_root, settings.insightface_allowed_providers
    )

    async def embed_all() -> dict[str, list[np.ndarray]]:
        by_person: dict[str, list[np.ndarray]] = {}
        for person_dir in sorted(p for p in dataset_dir.iterdir() if p.is_dir()):
            for image_path in sorted(person_dir.glob("*")):
                if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                    continue
                analysis = await pipeline.analyze(
                    frame_bytes=image_path.read_bytes(),
                    det_thresh=0.6,
                    det_size=(settings.default_detection_size_width, settings.default_detection_size_height),
                    max_faces=1,
                )
                if not analysis.faces:
                    print(f"  skip (no face): {image_path}")
                    continue
                embedding = np.asarray(analysis.faces[0].embedding, dtype=np.float32)
                by_person.setdefault(person_dir.name, []).append(l2_normalize(embedding))
        return by_person

    by_person = asyncio.run(embed_all())
    usable = {k: v for k, v in by_person.items() if len(v) >= 2}
    if len(usable) < 2:
        print("ERROR: need >= 2 persons with >= 2 usable images each")
        return 1
    genuine, impostor = pair_distances(usable)
    print(describe("genuine", genuine))
    print(describe("impostor", impostor))
    result = calibrate(genuine, impostor, target_far)
    print(f"\nRecommended (target FAR <= {target_far}):")
    for key, value in result.items():
        print(f"  {key}: {value:.4f}")
    return 0


def run_self_test() -> int:
    """Validate the calibration math with synthetic clustered embeddings.
    This does NOT calibrate production thresholds."""
    rng = np.random.default_rng(2026)
    by_person: dict[str, list[np.ndarray]] = {}
    for person in range(20):
        centroid = l2_normalize(rng.normal(size=512).astype(np.float32))
        # noise norm ~= 0.015 * sqrt(512) ~= 0.34 relative to the unit centroid,
        # giving clearly clustered classes like a real embedding space.
        samples = l2_normalize(centroid + rng.normal(scale=0.015, size=(8, 512)).astype(np.float32))
        by_person[f"synthetic_{person:02d}"] = list(samples)
    genuine, impostor = pair_distances(by_person)
    print("[SELF-TEST — synthetic embeddings, NOT a real calibration]")
    print(describe("genuine", genuine))
    print(describe("impostor", impostor))
    result = calibrate(genuine, impostor, target_far=0.001)
    print("\ncalibrate() output:")
    for key, value in result.items():
        print(f"  {key}: {value:.4f}")
    ok = (
        genuine.mean() < impostor.mean()
        and genuine.max() < 1.0
        and result["far"] <= 0.001
        and 0.0 < result["distance_threshold"] < 1.0
        and result["frr"] < 0.05
    )
    print("\nSELF-TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="labeled dataset directory (one subdir per person)")
    parser.add_argument("--target-far", type=float, default=0.001, help="target false-accept rate (default 0.1%%)")
    parser.add_argument("--self-test", action="store_true", help="validate calibration math with synthetic data")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if args.dataset is None:
        parser.error("--dataset is required unless --self-test is given")
    return run_dataset(args.dataset, args.target_far)


if __name__ == "__main__":
    raise SystemExit(main())
