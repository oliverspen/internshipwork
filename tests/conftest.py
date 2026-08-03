"""Pytest bootstrap for source-layout imports.

Enables imports like internshipwork.constants when running tests from the
repository root without installing the project as a package.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Provide a namespace package alias so tests can import internshipwork.*
if "internshipwork" not in sys.modules:
    pkg = types.ModuleType("internshipwork")
    pkg.__path__ = [str(ROOT)]
    sys.modules["internshipwork"] = pkg


# Legacy module aliases now point directly to backend.* implementations.
_LEGACY_TO_BACKEND = {
    "api": "backend.api",
    "constants": "backend.constants",
    "merge": "backend.merge",
    "mergeflow": "backend.mergeflow",
    "merge_support": "backend.merge_support",
    "models": "backend.models",
    "output": "backend.output",
    "pipemapping": "backend.pipemapping",
    "user_inputs": "backend.user_inputs",
}

for legacy_name, backend_name in _LEGACY_TO_BACKEND.items():
    sys.modules[f"internshipwork.{legacy_name}"] = importlib.import_module(backend_name)
