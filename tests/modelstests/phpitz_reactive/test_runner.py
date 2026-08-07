import importlib


phpitz_runner = importlib.import_module("backend.models.phpitz_reactive.runner")


def test_run_reaction_uses_shared_storage_builder(monkeypatch):
    source_rows = [
        ("plant", 0, {"stream_phase": "gas", "density_kg_per_m3": 2.0, "temperature_kelvin": 300.0, "total_massflow": 5.0}),
    ]
    config = {
        "p_bara": 10.0,
        "merge_definitions": [],
        "storage_name": "Tank",
        "plant_inputs": [{"name": "Plant 1"}],
    }

    captured: dict[str, object] = {}

    monkeypatch.setattr(phpitz_runner, "source_results_for_phpitz_reactive", lambda: source_rows)
    monkeypatch.setattr(phpitz_runner, "to_phpitz_reactive_input_from_source_state", lambda state: {"SO2": 1.0})
    monkeypatch.setattr(phpitz_runner, "run_model_with_fallback", lambda *args, **kwargs: {"SO2": 2.0})
    monkeypatch.setattr(phpitz_runner, "get_input_config", lambda: config)

    def fake_build_storage_row(results, merge_definitions, storage_name, pressure_bara):
        captured["results_len"] = len(results)
        captured["merge_definitions"] = merge_definitions
        captured["storage_name"] = storage_name
        captured["pressure_bara"] = pressure_bara
        return {
            "source_type": "storage",
            "source_name": storage_name,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "temperature_kelvin": 300.0,
            "total_massflow": 5.0,
            "phpitz_reactive_input": {"SO2": 2.0},
            "final": {},
        }

    monkeypatch.setattr(phpitz_runner, "build_storage_row", fake_build_storage_row)
    monkeypatch.setattr(phpitz_runner, "build_graph_from_merge_definitions", lambda *args, **kwargs: ("graph", {"Storage": "storage"}))
    monkeypatch.setattr(phpitz_runner, "save_phpitz_reactive_results", lambda *args, **kwargs: None)

    results = phpitz_runner.run_reaction()

    assert captured["results_len"] == 1
    assert captured["merge_definitions"] == []
    assert captured["storage_name"] == "Tank"
    assert captured["pressure_bara"] == 10.0
    assert results[-1]["source_type"] == "storage"


def test_run_reaction_executes_progress_and_storage(monkeypatch):
    source_rows = [
        ("plant", 0, {"stream_phase": "gas", "density_kg_per_m3": 2.0, "temperature_kelvin": 300.0, "total_massflow": 5.0}),
        ("merge", "Merge A", {"stream_phase": "gas", "density_kg_per_m3": 2.1, "temperature_kelvin": 301.0, "total_massflow": 7.0}),
    ]
    config = {
        "p_bara": 10.0,
        "merge_definitions": [{"merge_name": "Merge A", "sources": [("plant", 0)]}],
        "storage_name": "Storage",
        "plant_inputs": [{"name": "Plant 1"}],
    }

    monkeypatch.setattr(phpitz_runner, "source_results_for_phpitz_reactive", lambda: source_rows)
    monkeypatch.setattr(
        phpitz_runner,
        "to_phpitz_reactive_input_from_source_state",
        lambda state: {"SO2": float(state["total_massflow"])},
    )
    monkeypatch.setattr(
        phpitz_runner,
        "run_model_with_fallback",
        lambda model_id, input_concentrations, **kwargs: {"SO2": input_concentrations["SO2"] + 1.0},
    )
    monkeypatch.setattr(phpitz_runner, "get_input_config", lambda: config)
    monkeypatch.setattr(phpitz_runner, "build_graph_from_merge_definitions", lambda *args, **kwargs: ("graph", {"Storage": "storage"}))
    monkeypatch.setattr(phpitz_runner, "save_phpitz_reactive_results", lambda *args, **kwargs: None)

    progress: list[tuple[int, int, str | None]] = []
    results = phpitz_runner.run_reaction(progress_callback=lambda c, t, lbl: progress.append((c, t, lbl)))

    assert len(results) == 3
    assert results[-1]["source_type"] == "storage"
    assert progress[0] == (0, 2, "Starting")
    assert progress[-1] == (2, 2, "Completed")


def test_run_reaction_with_saving_calls_output_pipeline(monkeypatch):
    source_rows = [
        ("plant", 0, {"stream_phase": "gas", "density_kg_per_m3": 2.0, "temperature_kelvin": 300.0, "total_massflow": 5.0}),
    ]
    config = {
        "p_bara": 10.0,
        "merge_definitions": [],
        "storage_name": "Storage",
        "plant_inputs": [{"name": "Plant 1"}],
        "pipeline_map_name": "demo",
    }

    captured: dict[str, object] = {}

    monkeypatch.setattr(phpitz_runner, "source_results_for_phpitz_reactive", lambda: source_rows)
    monkeypatch.setattr(phpitz_runner, "to_phpitz_reactive_input_from_source_state", lambda state: {"SO2": 1.0})
    monkeypatch.setattr(phpitz_runner, "run_model_with_fallback", lambda *args, **kwargs: {"SO2": 2.0})
    monkeypatch.setattr(phpitz_runner, "get_input_config", lambda: config)
    monkeypatch.setattr(
        phpitz_runner,
        "build_graph_from_merge_definitions",
        lambda *args, **kwargs: ("graph", {"Storage": "storage"}),
    )
    monkeypatch.setattr(
        phpitz_runner,
        "build_storage_row",
        lambda *args, **kwargs: {
            "source_type": "storage",
            "source_name": "Storage",
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "temperature_kelvin": 300.0,
            "total_massflow": 5.0,
            "phpitz_reactive_input": {"SO2": 2.0},
            "final": {},
        },
    )

    def fake_save(results, pipeline_map_name, graph, node_types, plant_names):
        captured["pipeline_map_name"] = pipeline_map_name
        captured["graph"] = graph
        captured["node_types"] = node_types
        captured["plant_names"] = plant_names
        captured["results_len"] = len(results)

    monkeypatch.setattr(phpitz_runner, "save_phpitz_reactive_results", fake_save)

    results = phpitz_runner.run_reaction()

    assert results
    assert results[0]["final"]["SO2"] == 2.0
    assert captured["pipeline_map_name"] == "demo"
    assert captured["graph"] == "graph"
    assert captured["node_types"] == {"Storage": "storage"}
    assert captured["plant_names"] == {0: "Plant 1"}
    assert captured["results_len"] == 2


def test_run_reaction_acidwatch_values(monkeypatch):
    source_row = (
        "plant",
        0,
        {
            "stream_phase": "gas",
            "density_kg_per_m3": 2.0,
            "temperature_kelvin": 298.15,
            "total_massflow": 5.0,
        },
    )
    config = {
        "p_bara": 10,
        "merge_definitions": [],
        "storage_name": "Storage",
        "plant_inputs": [{"name": "Plant 1"}],
    }

    pitz_input = {"O2": 1, "H2O": 2, "H2S": 3, "SO2": 4, "NO2": 5, "N2": 6, "NO": 7, "H2SO4": 8, "HNO3": 9, "S8": 10, 
    "NH3": 11, "N2O": 12, "N2O4": 13, "NH4HSO4": 14, "HCHO": 15, "CH3CHO": 16, "CH3COCH3": 17, "HCOOH": 18, "CH3COOH": 19}
    expected_final = expected_final = {
    "O2": 3.36,
    "H2O": 1.72,
    "H2S": 0.00,
    "SO2": 0.04,
    "NO2": 56.93,
    "N2": 6.00,
    "NO": 0.01,
    "H2SO4": 14.96,
    "HNO3": 1.65,
    "S8": 10.00,
    "NH3": 11.00,
    "N2O": 0.00,
    "N2O4": 0.21,
    "NH4HSO4": 14.00,
    "HCHO": 15.00,
    "CH3CHO": 16.00,
    "CH3COCH3": 17.00,
    "HCOOH": 18.00,
    "CH3COOH": 19.00
}
    captured: dict[str, object] = {}

    monkeypatch.setattr(phpitz_runner, "source_results_for_phpitz_reactive", lambda: [source_row])
    monkeypatch.setattr(phpitz_runner, "to_phpitz_reactive_input_from_source_state", lambda _state: pitz_input)

    def fake_run_model(model_id, input_concentrations, **kwargs):
        captured["model_id"] = model_id
        captured["input_concentrations"] = input_concentrations
        captured["kwargs"] = kwargs
        return expected_final

    monkeypatch.setattr(phpitz_runner, "run_model_with_fallback", fake_run_model)
    monkeypatch.setattr(phpitz_runner, "get_input_config", lambda: config)
    monkeypatch.setattr(phpitz_runner, "build_storage_row", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        phpitz_runner,
        "build_graph_from_merge_definitions",
        lambda *args, **kwargs: ("graph", {"Storage": "storage"}),
    )
    monkeypatch.setattr(phpitz_runner, "save_phpitz_reactive_results", lambda *args, **kwargs: None)

    results = phpitz_runner.run_reaction()

    assert results[0]["final"] == expected_final
    assert captured["model_id"] == "phpitz_reactive"
    assert captured["input_concentrations"] == pitz_input
    assert captured["kwargs"] == {"temperature_kelvin": 298.15, "pressure_bara": 10}
