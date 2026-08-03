import pytest

import backend.models._acidwatch_helpers as helpers


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _Row:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _ILoc:
    def __init__(self, data):
        self._data = data

    def __getitem__(self, _idx):
        return _Row(self._data)


class _FakeDF:
    def __init__(self, row=None, empty=False):
        self.empty = empty
        self.iloc = _ILoc(row or {})


def test_extract_result_concentrations_direct_format():
    result = helpers.extract_result_concentrations({"concentrations": {"SO2": 1, "CO2": "2.5"}})
    assert result == {"SO2": 1.0, "CO2": 2.5}


def test_extract_result_concentrations_phase_format_uses_last_valid_phase():
    result = helpers.extract_result_concentrations(
        {
            "phases": [
                {"concentrations": {"SO2": 0.1}},
                {"concentrations": {"SO2": 0.2, "CO2": 0.3}},
            ]
        }
    )
    assert result == {"SO2": 0.2, "CO2": 0.3}


def test_extract_result_concentrations_raises_for_unsupported_shape():
    with pytest.raises(ValueError, match="Unsupported simulation result shape"):
        helpers.extract_result_concentrations({"unexpected": "shape"})


def test_run_model_compat_raises_if_start_fails():
    class _Session:
        def post(self, _path, json):
            return _Response(500, {"error": "start failed"})

    with pytest.raises(RuntimeError, match="Couldn't start model run"):
        helpers.run_model_compat(
            _Session(),
            "tocomo",
            {"SO2": 1.0},
            {},
            temperature=300.0,
            pressure=1.0,
            retries=1,
        )


def test_run_model_compat_returns_concentrations_when_done(monkeypatch):
    monkeypatch.setattr(helpers.time, "sleep", lambda _s: None)

    class _Session:
        def __init__(self):
            self.calls = 0

        def post(self, _path, json):
            assert json["conditions"]["temperature"] == 300.0
            assert json["conditions"]["pressure"] == 1.0
            return _Response(200, "00000000-0000-0000-0000-000000000123")

        def get(self, _path):
            self.calls += 1
            if self.calls == 1:
                return _Response(200, {"status": "running"})
            return _Response(
                200,
                {
                    "status": "done",
                    "results": [{"concentrations": {"SO2": 2.2, "CO2": 3.3}}],
                },
            )

    result = helpers.run_model_compat(
        _Session(),
        "tocomo",
        {"SO2": 1.0},
        {"k": 1},
        temperature=300.0,
        pressure=1.0,
        retries=3,
    )
    assert result == {"SO2": 2.2, "CO2": 3.3}


def test_run_model_compat_returns_empty_dict_for_empty_results(monkeypatch):
    monkeypatch.setattr(helpers.time, "sleep", lambda _s: None)

    class _Session:
        def post(self, _path, json):
            return _Response(200, "00000000-0000-0000-0000-000000000123")

        def get(self, _path):
            return _Response(200, {"status": "done", "results": []})

    result = helpers.run_model_compat(
        _Session(),
        "tocomo",
        {"SO2": 1.0},
        {},
        temperature=300.0,
        pressure=1.0,
        retries=1,
    )
    assert result == {}


def test_run_model_compat_raises_on_poll_failure(monkeypatch):
    monkeypatch.setattr(helpers.time, "sleep", lambda _s: None)

    class _Session:
        def post(self, _path, json):
            return _Response(200, "00000000-0000-0000-0000-000000000123")

        def get(self, _path):
            return _Response(500, {"error": "poll failed"})

    with pytest.raises(RuntimeError, match="Couldn't poll model run"):
        helpers.run_model_compat(
            _Session(),
            "tocomo",
            {"SO2": 1.0},
            {},
            temperature=300.0,
            pressure=1.0,
            retries=1,
        )


def test_run_model_compat_raises_on_retry_timeout(monkeypatch):
    monkeypatch.setattr(helpers.time, "sleep", lambda _s: None)

    class _Session:
        def post(self, _path, json):
            return _Response(200, "00000000-0000-0000-0000-000000000123")

        def get(self, _path):
            return _Response(200, {"status": "running"})

    with pytest.raises(RuntimeError, match="Out of retries"):
        helpers.run_model_compat(
            _Session(),
            "tocomo",
            {"SO2": 1.0},
            {},
            temperature=300.0,
            pressure=1.0,
            retries=2,
        )


def test_run_model_with_fallback_primary_success(monkeypatch):
    class _ClientCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run_model(self, model_id, input_concentrations, params, *, temperature, pressure):
            assert model_id == "tocomo"
            assert input_concentrations == {"SO2": 1.0}
            assert params == {"alpha": 1}
            assert temperature == 300.0
            assert pressure == 1.0
            return _FakeDF(row={"SO2": 10, "CO2": "20.5"}, empty=False)

    monkeypatch.setattr(helpers, "Client", lambda: _ClientCtx())

    result = helpers.run_model_with_fallback(
        "tocomo",
        {"SO2": 1.0},
        temperature_kelvin=300.0,
        pressure_bara=1.0,
        params={"alpha": 1},
    )
    assert result == {"SO2": 10.0, "CO2": 20.5}


def test_run_model_with_fallback_returns_empty_dict_when_df_empty(monkeypatch):
    class _ClientCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run_model(self, *args, **kwargs):
            return _FakeDF(empty=True)

    monkeypatch.setattr(helpers, "Client", lambda: _ClientCtx())

    result = helpers.run_model_with_fallback(
        "tocomo",
        {"SO2": 1.0},
        temperature_kelvin=300.0,
        pressure_bara=1.0,
    )
    assert result == {}


def test_run_model_with_fallback_uses_compat_when_primary_fails(monkeypatch):
    class _ClientCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run_model(self, *args, **kwargs):
            raise RuntimeError("primary failed")

    calls = {}

    def _fake_compat(session, model_id, concs, params, *, temperature, pressure, retries=120):
        calls["called"] = True
        calls["model_id"] = model_id
        calls["concs"] = concs
        calls["params"] = params
        calls["temperature"] = temperature
        calls["pressure"] = pressure
        return {"SO2": 4.2}

    monkeypatch.setattr(helpers, "Client", lambda: _ClientCtx())
    monkeypatch.setattr(helpers, "run_model_compat", _fake_compat)

    result = helpers.run_model_with_fallback(
        "tocomo",
        {"SO2": 1.0},
        temperature_kelvin=300.0,
        pressure_bara=1.0,
        params={"alpha": 1},
    )

    assert result == {"SO2": 4.2}
    assert calls["called"] is True
    assert calls["model_id"] == "tocomo"
