from __future__ import annotations

from pathlib import Path

_API_APP = Path(__file__).resolve().parent.parent / "apps" / "api-python" / "app"
__path__ = [str(_API_APP)]
