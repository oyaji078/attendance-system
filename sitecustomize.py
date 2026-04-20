from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_APP = ROOT / "apps" / "api-python"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(API_APP) not in sys.path:
    sys.path.insert(0, str(API_APP))
