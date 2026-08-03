"""Compatibility shim for legacy ASGI target `api.app:app`."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("backend.api.app")
