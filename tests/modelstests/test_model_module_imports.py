import importlib

import pytest


MODULES = [
    "backend.models.dynamic.delay",
    "backend.models.dynamic.phpitz_dynamic_model",
    "backend.models.dynamic.runner",
    "backend.models.dynamic.tocomo_dynamic_model",
    "backend.models.phpitz_reactive.pipeline",
    "backend.models.phpitz_reactive.runner",
    "backend.models.tocomo.pipeline",
    "backend.models.tocomo.runner",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_model_module_import_smoke(module_name):
    module = importlib.import_module(module_name)
    assert module is not None
