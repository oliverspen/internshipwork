import importlib

import pytest


MODULES = [
    "internshipwork.pipemapping",
    "internshipwork.pipemapping.dev_pipeline_map",
    "internshipwork.pipemapping.dialogs",
    "internshipwork.pipemapping.workflow",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_pipemapping_module_import_smoke(module_name):
    module = importlib.import_module(module_name)
    assert module is not None
