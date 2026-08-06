"""Pytest bootstrap for source-layout imports.

Enables imports like backend.constants when running tests from the
repository root without installing the project as a package.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
