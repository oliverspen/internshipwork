import backend.models.api_client as api_client


def test_post_model_delegates_to_run_model_with_fallback(monkeypatch):
    captured = {}

    def _fake_run_model_with_fallback(model_id, input_concentrations, *, temperature_kelvin, pressure_bara, params=None):
        captured["model_id"] = model_id
        captured["input_concentrations"] = input_concentrations
        captured["temperature_kelvin"] = temperature_kelvin
        captured["pressure_bara"] = pressure_bara
        captured["params"] = params
        return {"SO2": 1.23}

    monkeypatch.setattr(api_client, "run_model_with_fallback", _fake_run_model_with_fallback)

    result = api_client.post_model(
        "tocomo",
        {"SO2": 1.0},
        temperature_kelvin=300.0,
        pressure_bara=1.0,
    )

    assert result == {"SO2": 1.23}
    assert captured == {
        "model_id": "tocomo",
        "input_concentrations": {"SO2": 1.0},
        "temperature_kelvin": 300.0,
        "pressure_bara": 1.0,
        "params": None,
    }
