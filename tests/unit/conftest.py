from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PARENT_CONFTEST = Path(__file__).resolve().parent.parent / "conftest.py"
if PARENT_CONFTEST.exists():
    spec = importlib.util.spec_from_file_location("tests_conftest", PARENT_CONFTEST)
    if spec is not None and spec.loader is not None:
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        make_player = _mod.make_player
else:
    pass
