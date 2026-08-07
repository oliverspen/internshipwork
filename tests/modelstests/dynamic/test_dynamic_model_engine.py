import importlib

import pytest


dynamic_model_engine = importlib.import_module("backend.models.dynamic.dynamic_model_engine")


def test_delay_time_matches_manual_formula():
    pipe_length_m = 1000.0
    flowrate_kg_per_h = 3600.0
    pipe_diameter_m = 1.0
    density_kg_per_m3 = 1.0

    actual = dynamic_model_engine.delay_time_s(
        pipe_length_m=pipe_length_m,
        flowrate_kg_per_h=flowrate_kg_per_h,
        pipe_diameter_m=pipe_diameter_m,
        density_kg_per_m3=density_kg_per_m3,
    )

    assert actual == pytest.approx(785.3981)


def test_delay_time_scales_linearly_with_pipe_length():
    base = dynamic_model_engine.delay_time_s(
        pipe_length_m=100.0,
        flowrate_kg_per_h=5000.0,
        pipe_diameter_m=0.4,
        density_kg_per_m3=2.0,
    )
    doubled = dynamic_model_engine.delay_time_s(
        pipe_length_m=200.0,
        flowrate_kg_per_h=5000.0,
        pipe_diameter_m=0.4,
        density_kg_per_m3=2.0,
    )

    assert doubled == 2.0 * base


def test_latest_arrived_state_returns_empty_dict_when_history_is_empty():
    assert dynamic_model_engine._latest_arrived_state([], current_time_days=1.0) == {}


def test_run_dynamic_merges_returns_empty_when_dt_is_not_positive():
    result = dynamic_model_engine.run_dynamic_merges(
        duration_days=1.0,
        dt_days=0.0,
        dynamic_profile={"plant_profiles": {}},
        evaluate_merge=lambda _merge_name, _merge_values, _time_days: {},
    )

    assert result == []


def test_run_dynamic_merges_returns_empty_when_merge_definitions_missing(monkeypatch):
    base_config = {
        "p_bara": 1.0,
        "merge_definitions": [],
        "merge_pipe_inputs": {},
        "plant_inputs": [
            {
                "name": "Plant 1",
                "flowrate": 100.0,
                "temperature_celsius": 20.0,
                "stream_phase": "gas",
                "pipediameter": 1.0,
                "pipelength": 1.0,
                "inlet_conc": {},
            }
        ],
    }

    monkeypatch.setattr(dynamic_model_engine, "resolve_merge_input_config", lambda: base_config)

    result = dynamic_model_engine.run_dynamic_merges(
        duration_days=1.0,
        dt_days=0.5,
        dynamic_profile={"plant_profiles": {}},
        evaluate_merge=lambda _merge_name, _merge_values, _time_days: {},
    )

    assert result == []


def test_run_dynamic_merges_uses_current_flowrate_for_downstream_merge(monkeypatch):
    runtime_state: dict[str, object] = {}

    base_config = {
        "p_bara": 1.0,
        "merge_definitions": [{"merge_name": "Merge 1", "sources": [("plant", 0)]}],
        "merge_pipe_inputs": {"Merge 1": {"pipediameter": 1.0, "pipelength": 1.0}},
        "plant_inputs": [
            {
                "name": "Plant 1",
                "flowrate": 100.0,
                "temperature_celsius": 20.0,
                "stream_phase": "gas",
                "pipediameter": 1.0,
                "pipelength": 1.0,
                "inlet_conc": {},
            }
        ],
    }

    def fake_set_runtime_input_config(config):
        runtime_state["config"] = config

    def fake_get_input_config():
        return runtime_state["config"]

    def fake_clear_runtime_input_config():
        runtime_state.clear()

    def fake_build_plant_source_dict(_stream_idx):
        current_config = fake_get_input_config()
        plant_input = current_config["plant_inputs"][0]
        return {
            "source_type": "plant",
            "source_name": 0,
            "temperature_kelvin": 293.15,
            "stream_phase": "gas",
            "total_massflow": float(plant_input["flowrate"]),
            "initial_merge_conc": {},
            "pipe_time": 172800.0,
        }

    monkeypatch.setattr(dynamic_model_engine, "resolve_merge_input_config", lambda: base_config)
    monkeypatch.setattr(
        dynamic_model_engine,
        "build_merge_inputs_from_definitions",
        lambda _definitions: {"Merge 1": {"pipe_time": 172800.0}},
    )
    monkeypatch.setattr(
        dynamic_model_engine,
        "_build_merge_input_from_source_states",
        lambda source_dicts, merge_name=None: {
            "sources": [item["source_name"] for item in source_dicts],
            "temperature_kelvin": 293.15,
            "total_massflow": sum(float(item["total_massflow"]) for item in source_dicts),
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "pipe_time": 172800.0,
            "initial_merge_conc": {},
            "pipe_length": 1.0,
            "pipe_diameter": 1.0,
            "ppm_molar": {},
        },
    )
    monkeypatch.setattr(dynamic_model_engine, "set_runtime_input_config", fake_set_runtime_input_config)
    monkeypatch.setattr(dynamic_model_engine, "get_input_config", fake_get_input_config)
    monkeypatch.setattr(dynamic_model_engine, "clear_runtime_input_config", fake_clear_runtime_input_config)
    monkeypatch.setattr(dynamic_model_engine, "_build_plant_source_dict", fake_build_plant_source_dict)

    dynamic_profile = {
        "plant_profiles": {
            "Plant 1": {
                "flowrate": [(0.0, 100.0), (1.0, 250.0)],
            }
        }
    }

    results = dynamic_model_engine.run_dynamic_merges(
        duration_days=1.0,
        dt_days=1.0,
        dynamic_profile=dynamic_profile,
        evaluate_merge=lambda _merge_name, _merge_values, _time_days: {},
    )

    assert [row["flow_kg_per_h"] for row in results] == [100.0, 250.0]


def test_run_dynamic_merges_reports_progress_each_timestep(monkeypatch):
    runtime_state: dict[str, object] = {}

    base_config = {
        "p_bara": 1.0,
        "merge_definitions": [{"merge_name": "Merge 1", "sources": [("plant", 0)]}],
        "merge_pipe_inputs": {"Merge 1": {"pipediameter": 1.0, "pipelength": 1.0}},
        "plant_inputs": [
            {
                "name": "Plant 1",
                "flowrate": 100.0,
                "temperature_celsius": 20.0,
                "stream_phase": "gas",
                "pipediameter": 1.0,
                "pipelength": 1.0,
                "inlet_conc": {},
            }
        ],
    }

    def fake_set_runtime_input_config(config):
        runtime_state["config"] = config

    def fake_get_input_config():
        return runtime_state["config"]

    def fake_clear_runtime_input_config():
        runtime_state.clear()

    def fake_build_plant_source_dict(_stream_idx):
        return {
            "source_type": "plant",
            "source_name": 0,
            "temperature_kelvin": 293.15,
            "stream_phase": "gas",
            "total_massflow": 100.0,
            "initial_merge_conc": {},
            "pipe_time": 0.0,
        }

    monkeypatch.setattr(dynamic_model_engine, "resolve_merge_input_config", lambda: base_config)
    monkeypatch.setattr(
        dynamic_model_engine,
        "build_merge_inputs_from_definitions",
        lambda _definitions: {"Merge 1": {"pipe_time": 0.0}},
    )
    monkeypatch.setattr(
        dynamic_model_engine,
        "_build_merge_input_from_source_states",
        lambda source_dicts, merge_name=None: {
            "sources": [item["source_name"] for item in source_dicts],
            "temperature_kelvin": 293.15,
            "total_massflow": 100.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "pipe_time": 0.0,
            "initial_merge_conc": {},
            "pipe_length": 1.0,
            "pipe_diameter": 1.0,
            "ppm_molar": {},
        },
    )
    monkeypatch.setattr(dynamic_model_engine, "set_runtime_input_config", fake_set_runtime_input_config)
    monkeypatch.setattr(dynamic_model_engine, "get_input_config", fake_get_input_config)
    monkeypatch.setattr(dynamic_model_engine, "clear_runtime_input_config", fake_clear_runtime_input_config)
    monkeypatch.setattr(dynamic_model_engine, "_build_plant_source_dict", fake_build_plant_source_dict)

    progress_events: list[tuple[int, int, str | None]] = []

    dynamic_model_engine.run_dynamic_merges(
        duration_days=1.0,
        dt_days=0.5,
        dynamic_profile={"plant_profiles": {}},
        evaluate_merge=lambda _merge_name, _merge_values, _time_days: {},
        progress_callback=lambda completed, total, label: progress_events.append(
            (completed, total, label)
        ),
    )

    # Initial event plus one update per simulated timestep (0.0, 0.5, 1.0).
    assert len(progress_events) == 4
    assert progress_events[0][0] == 0
    assert progress_events[-1][0] == progress_events[-1][1]


def test_run_dynamic_merges_temperature_uses_pipe_delay(monkeypatch):
    runtime_state: dict[str, object] = {}

    base_config = {
        "p_bara": 1.0,
        "merge_definitions": [{"merge_name": "Merge 1", "sources": [("plant", 0)]}],
        "merge_pipe_inputs": {"Merge 1": {"pipediameter": 1.0, "pipelength": 1.0}},
        "plant_inputs": [
            {
                "name": "Plant 1",
                "flowrate": 100.0,
                "temperature_celsius": 20.0,
                "stream_phase": "gas",
                "pipediameter": 1.0,
                "pipelength": 1.0,
                "inlet_conc": {},
            }
        ],
    }

    def fake_set_runtime_input_config(config):
        runtime_state["config"] = config

    def fake_get_input_config():
        return runtime_state["config"]

    def fake_clear_runtime_input_config():
        runtime_state.clear()

    def fake_build_plant_source_dict(_stream_idx):
        current_config = fake_get_input_config()
        plant_input = current_config["plant_inputs"][0]
        temperature_kelvin = float(plant_input["temperature_celsius"]) + 273.15
        return {
            "source_type": "plant",
            "source_name": 0,
            "temperature_kelvin": temperature_kelvin,
            "stream_phase": "gas",
            "total_massflow": float(plant_input["flowrate"]),
            "initial_merge_conc": {},
            "pipe_time": 86400.0,
        }

    monkeypatch.setattr(dynamic_model_engine, "resolve_merge_input_config", lambda: base_config)
    monkeypatch.setattr(
        dynamic_model_engine,
        "build_merge_inputs_from_definitions",
        lambda _definitions: {"Merge 1": {"pipe_time": 86400.0}},
    )
    monkeypatch.setattr(
        dynamic_model_engine,
        "_build_merge_input_from_source_states",
        lambda source_dicts, merge_name=None: {
            "sources": [item["source_name"] for item in source_dicts],
            "temperature_kelvin": float(source_dicts[0]["temperature_kelvin"]),
            "total_massflow": sum(float(item["total_massflow"]) for item in source_dicts),
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "pipe_time": 86400.0,
            "initial_merge_conc": {},
            "pipe_length": 1.0,
            "pipe_diameter": 1.0,
            "ppm_molar": {},
        },
    )
    monkeypatch.setattr(dynamic_model_engine, "set_runtime_input_config", fake_set_runtime_input_config)
    monkeypatch.setattr(dynamic_model_engine, "get_input_config", fake_get_input_config)
    monkeypatch.setattr(dynamic_model_engine, "clear_runtime_input_config", fake_clear_runtime_input_config)
    monkeypatch.setattr(dynamic_model_engine, "_build_plant_source_dict", fake_build_plant_source_dict)

    dynamic_profile = {
        "plant_profiles": {
            "Plant 1": {
                "temperature_celsius": [(0.0, 20.0), (1.0, 80.0)],
            }
        }
    }

    results = dynamic_model_engine.run_dynamic_merges(
        duration_days=2.0,
        dt_days=1.0,
        dynamic_profile=dynamic_profile,
        evaluate_merge=lambda _merge_name, _merge_values, _time_days: {},
    )

    # With 1-day pipe delay: t=0 -> 20C, t=1 still sees t=0, t=2 sees t=1.
    assert [row["temperature_celsius"] for row in results] == pytest.approx([20.15, 20.15, 80.15])