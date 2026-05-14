from __future__ import annotations

from pathlib import Path
import os
import sys


REPO_ROOT = Path("D:/cnn/attendance-system")
API_APP = REPO_ROOT / "apps" / "api-python"
MODEL_ROOT = Path("D:/cnn/attendance-system/models/insightface")
MODEL_DIR = MODEL_ROOT / "models" / "buffalo_l"


def main() -> int:
    model_root_text = str(MODEL_ROOT).replace("\\", "/")
    if not model_root_text.lower().startswith("d:/cnn/attendance-system/models"):
        print(f"Unsafe model root for this deployment mode: {MODEL_ROOT}", file=sys.stderr)
        return 1
    if model_root_text.lower().startswith("e:/"):
        print(f"Model root must not be on drive E: {MODEL_ROOT}", file=sys.stderr)
        return 1

    # Ensure FaceAnalysis sees an explicit D-drive model directory and never falls
    # back to the default user cache when the model is missing.
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(API_APP))

    root = "D:/cnn/attendance-system/models/insightface"
    os.environ["INSIGHTFACE_MODEL_ROOT"] = root
    os.environ["INSIGHTFACE_MODEL_NAME"] = "buffalo_l"
    os.environ["INSIGHTFACE_ALLOWED_PROVIDERS"] = "CPUExecutionProvider"
    os.environ["MODEL_DIR"] = "D:/cnn/attendance-system/models"
    os.environ["DATA_DIR"] = "D:/cnn/attendance-system/data"
    os.environ["OBJECT_STORAGE_ROOT"] = "D:/cnn/attendance-system/data/object-storage"
    os.environ["OBJECT_STORAGE_MODE"] = "local"

    from insightface.app import FaceAnalysis

    print("Python import OK: insightface.app.FaceAnalysis")
    print("Trying FaceAnalysis(name='buffalo_l', root=root, providers=['CPUExecutionProvider'])")
    try:
        app = FaceAnalysis(name="buffalo_l", root=root, providers=["CPUExecutionProvider"])
    except Exception as exc:
        print(f"FaceAnalysis init failed: {exc!r}")
        if not any(MODEL_DIR.glob("*.onnx")):
            print(f"No ONNX files found in {MODEL_DIR}")
            return 2
        return 1

    print(f"FaceAnalysis model_dir: {app.model_dir}")
    print("Loaded model tasks: " + ", ".join(sorted(app.models.keys())))

    from app.core.config import get_settings

    settings = get_settings()
    print(f"API settings model root: {settings.insightface_model_root}")
    print(f"API settings model name: {settings.insightface_model_name}")
    print("API settings providers : " + ", ".join(settings.insightface_allowed_providers))

    if settings.insightface_model_root.replace("\\", "/") != root:
        raise RuntimeError("API settings do not point to the local InsightFace model root")
    if settings.insightface_model_name != "buffalo_l":
        raise RuntimeError("API settings do not use buffalo_l")
    if settings.insightface_allowed_providers != ["CPUExecutionProvider"]:
        raise RuntimeError("API settings providers are not CPUExecutionProvider")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
