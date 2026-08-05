import importlib

import pytest


pipeline = importlib.import_module("internshipwork.models.phpitz_reactive.pipeline")


def test_resolve_merge_input_config_reuses_existing_config(monkeypatch):
    config = {"merge_definitions": [{"merge_name": "M1", "sources": [("plant", 0)]}]}
    monkeypatch.setattr(pipeline, "get_input_config", lambda: config)

    assert pipeline.resolve_merge_input_config(use_dev_pipeline_map=True) is config


def test_resolve_merge_input_config_falls_back_to_interactive(monkeypatch):
    generated = {"merge_definitions": [{"merge_name": "M2", "sources": [("plant", 1)]}]}
    monkeypatch.setattr(pipeline, "get_input_config", lambda: {})
    monkeypatch.setattr(
        pipeline,
        "build_pipe_graph_with_inputs_interactive",
        lambda: (object(), {"x": "plant"}, generated),
    )

    assert pipeline.resolve_merge_input_config(use_dev_pipeline_map=False) == generated


def test_to_phpitz_input_uses_existing_ppm_molar():
    source_state = {"ppm_molar": {"H2O": 1, "SO2": 2.2, "NO2": 0.3, "NO": 0.6}}

    out = pipeline.to_phpitz_reactive_input_from_source_state(source_state)

    assert out == {"H2O": 1.0, "O2": 0.0, "N2": 0.0, "SO2": 2.2, "NO2": 0.3, "H2S": 0.0, "NO": 0.6}


def test_to_phpitz_input_converts_from_initial_conc(monkeypatch):
    monkeypatch.setattr(pipeline, "get_input_config", lambda: {"p_bara": 9.0})
    monkeypatch.setattr(pipeline, "_bara_to_pa", lambda p_bara: p_bara * 100.0)
    monkeypatch.setattr(
        pipeline,
        "_concentration_to_molar_ppm",
        lambda conc, pressure_pa, temperature_kelvin: conc + pressure_pa / 1000.0 + temperature_kelvin / 1000.0,
    )

    source_state = {
        "temperature_kelvin": 300.0,
        "initial_merge_conc": {"SO2": 1.0, "NO2": 2.0, "NO": 0.7, "N2": 4.0},
    }

    out = pipeline.to_phpitz_reactive_input_from_source_state(source_state)

    assert out["SO2"] == pytest.approx(2.2)
    assert out["NO2"] == pytest.approx(3.2)
    assert out["NO"] == pytest.approx(1.9)
    assert out["N2"] == pytest.approx(5.2)


def test_source_results_for_phpitz_no_merges_includes_all_plants(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "resolve_merge_input_config",
        lambda **kwargs: {"merge_definitions": [], "plant_inputs": [{"name": "A"}, {"name": "B"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_build_plant_source_dict",
        lambda idx: {"plant_idx": idx, "stream_phase": "gas", "temperature_kelvin": 300.0},
    )

    rows = pipeline.source_results_for_phpitz_reactive(use_dev_pipeline_map=False)

    assert [r[0] for r in rows] == ["plant", "plant"]
    assert [r[1] for r in rows] == [0, 1]


def test_source_results_for_phpitz_with_merges_builds_plants_then_merges(monkeypatch):
    merge_definitions = [
        {"merge_name": "Merge A", "sources": [("plant", 2), ("plant", 0)]},
        {"merge_name": "Merge B", "sources": [("merge", "Merge A"), ("plant", 2)]},
    ]
    monkeypatch.setattr(
        pipeline,
        "resolve_merge_input_config",
        lambda **kwargs: {"merge_definitions": merge_definitions, "plant_inputs": [{}, {}, {}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_build_plant_source_dict",
        lambda idx: {"plant_idx": idx, "stream_phase": "gas", "temperature_kelvin": 300.0},
    )
    monkeypatch.setattr(
        pipeline,
        "build_merge_inputs_from_definitions",
        lambda defs: {str(d["merge_name"]): {"merge": str(d["merge_name"])} for d in defs},
    )

    rows = pipeline.source_results_for_phpitz_reactive(use_dev_pipeline_map=True)

    assert [r[0] for r in rows] == ["plant", "plant", "merge", "merge"]
    assert [r[1] for r in rows[:2]] == [0, 2]
    assert [r[1] for r in rows[2:]] == ["Merge A", "Merge B"]
