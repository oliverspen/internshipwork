import importlib


pipeline = importlib.import_module("backend.models.tocomo.pipeline")


def test_to_tocomo_input_from_source_state_uses_existing_ppm_molar():
    source_state = {"ppm_molar": {"H2O": 1, "SO2": 2.2, "NO2": 0.3}}

    output = pipeline.to_tocomo_input_from_source_state(source_state)

    assert output == {"H2O": 1.0, "O2": 0.0, "SO2": 2.2, "NO2": 0.3, "H2S": 0.0}


def test_source_results_for_tocomo_no_merges_includes_all_plants(monkeypatch):
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

    rows = pipeline.source_results_for_tocomo()

    assert [r[0] for r in rows] == ["plant", "plant"]
    assert [r[1] for r in rows] == [0, 1]


def test_source_results_for_tocomo_builds_plants_then_merges(monkeypatch):
    merge_definitions = [
        {"merge_name": "Merge A", "sources": [("plant", 2), ("plant", 0)]},
        {"merge_name": "Merge B", "sources": [("merge", "Merge A"), ("plant", 2)]},
    ]
    monkeypatch.setattr(
        pipeline,
        "get_input_config",
        lambda: {"merge_definitions": merge_definitions},
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

    rows = pipeline.source_results_for_tocomo()

    assert [r[0] for r in rows] == ["plant", "plant", "merge", "merge"]
    assert [r[1] for r in rows[:2]] == [0, 2]
    assert [r[1] for r in rows[2:]] == ["Merge A", "Merge B"]
