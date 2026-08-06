import importlib

import pytest


pipeline = importlib.import_module("backend.models.phpitz_reactive.pipeline")


def test_to_phpitz_input_uses_existing_ppm_molar():
    source_state = {"ppm_molar": {"H2O": 1, "SO2": 2.2, "NO2": 0.3, "NO": 0.6}}

    out = pipeline.to_phpitz_reactive_input_from_source_state(source_state)

    assert out == {"H2O": 1.0, "O2": 0.0, "N2": 0.0, "SO2": 2.2, "NO2": 0.3, "H2S": 0.0, "NO": 0.6, "H2SO4": 0.0, "HNO3": 0.0, "S8": 0.0, "NH3": 0.0, "N2O": 0.0, "N2O4": 0.0, "NH4HSO4": 0.0, "HCHO": 0.0, "CH3CHO": 0.0, "CH3COCH3": 0.0, "HCOOH": 0.0, "CH3COOH": 0.0}


def test_source_results_for_phpitz_no_merges_includes_all_plants(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "get_input_config",
        lambda: {"merge_definitions": [], "plant_inputs": [{"name": "A"}, {"name": "B"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_build_plant_source_dict",
        lambda idx: {"plant_idx": idx, "stream_phase": "gas", "temperature_kelvin": 300.0},
    )

    rows = pipeline.source_results_for_phpitz_reactive()

    assert [r[0] for r in rows] == ["plant", "plant"]
    assert [r[1] for r in rows] == [0, 1]


def test_source_results_for_phpitz_with_merges_builds_plants_then_merges(monkeypatch):
    merge_definitions = [
        {"merge_name": "Merge A", "sources": [("plant", 2), ("plant", 0)]},
        {"merge_name": "Merge B", "sources": [("merge", "Merge A"), ("plant", 2)]},
    ]
    monkeypatch.setattr(
        pipeline,
        "get_input_config",
        lambda: {"merge_definitions": merge_definitions, "plant_inputs": [{}, {}, {}]},
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

    rows = pipeline.source_results_for_phpitz_reactive()

    assert [r[0] for r in rows] == ["plant", "plant", "merge", "merge"]
    assert [r[1] for r in rows[:2]] == [0, 2]
    assert [r[1] for r in rows[2:]] == ["Merge A", "Merge B"]
