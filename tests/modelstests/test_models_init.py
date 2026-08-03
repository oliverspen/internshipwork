import backend.models as models


def test_models_package_has_expected_docstring():
    assert isinstance(models.__doc__, str)
    assert "Core chemistry model packages" in models.__doc__
