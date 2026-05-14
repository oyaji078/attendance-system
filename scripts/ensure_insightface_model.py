from __future__ import annotations

from pathlib import Path
import sys


MODEL_ROOT = Path("D:/cnn/attendance-system/models/insightface")
MODEL_DIR = MODEL_ROOT / "models" / "buffalo_l"
EXPECTED_FILES = (
    "1k3d68.onnx",
    "2d106det.onnx",
    "det_10g.onnx",
    "genderage.onnx",
    "w600k_r50.onnx",
)


def missing_files() -> list[str]:
    return [file_name for file_name in EXPECTED_FILES if not (MODEL_DIR / file_name).is_file()]


def main() -> int:
    model_root_text = str(MODEL_ROOT).replace("\\", "/")
    if not model_root_text.lower().startswith("d:/cnn/attendance-system/models"):
        print(f"Unsafe model root for this deployment mode: {MODEL_ROOT}", file=sys.stderr)
        return 1
    if model_root_text.lower().startswith("e:/"):
        print(f"Model root must not be on drive E: {MODEL_ROOT}", file=sys.stderr)
        return 1

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    missing_before = missing_files()
    if missing_before:
        print("Downloading buffalo_l with InsightFace storage helper...")
        print(f"Target root: {MODEL_ROOT}")
        from insightface.utils.storage import download

        download("models", "buffalo_l", force=True, root=str(MODEL_ROOT))
    else:
        print("buffalo_l files already exist. Skipping download.")

    missing_after = missing_files()
    if missing_after:
        print("Model is still incomplete after download:", file=sys.stderr)
        for file_name in missing_after:
            print(f"- {file_name}", file=sys.stderr)
        return 1

    print("Validating buffalo_l with FaceAnalysis...")
    from insightface.app import FaceAnalysis

    app = FaceAnalysis(name="buffalo_l", root=str(MODEL_ROOT), providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(320, 320))
    print(f"Model directory: {app.model_dir}")
    print("Loaded model tasks: " + ", ".join(sorted(app.models.keys())))
    print(f"Model root: {MODEL_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
