import importlib

import pytest


MODULES = [
    "internshipwork.models.dynamic.delay",
    "internshipwork.models.dynamic.phpitz_dynamic_model",
    "internshipwork.models.dynamic.runner",
    "internshipwork.models.dynamic.tocomo_dynamic_model",
    "internshipwork.models.phpitz_reactive.pipeline",
    "internshipwork.models.phpitz_reactive.runner",
    "internshipwork.models.tocomo.pipeline",
    "internshipwork.models.tocomo.runner",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_model_module_import_smoke(module_name):
    module = importlib.import_module(module_name)
    assert module is not None
