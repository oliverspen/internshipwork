import importlib

import pytest


MODULES = [
    "internshipwork.merge",
    "internshipwork.mergeflow",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_merge_module_import_smoke(module_name):
    module = importlib.import_module(module_name)
    assert module is not None
