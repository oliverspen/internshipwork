import importlib

import pytest


MODULES = [
    "backend.pipemapping",
    "backend.pipemapping.dev_pipeline_map",
    "backend.pipemapping.dialogs",
    "backend.pipemapping.workflow",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_pipemapping_module_import_smoke(module_name):
    module = importlib.import_module(module_name)
    assert module is not None
