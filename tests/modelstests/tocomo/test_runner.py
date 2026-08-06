import importlib


tocomo_runner = importlib.import_module("backend.models.tocomo.runner")


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

    monkeypatch.setattr(tocomo_runner, "source_results_for_tocomo", lambda: source_rows)
    monkeypatch.setattr(tocomo_runner, "to_tocomo_input_from_source_state", lambda state: {"SO2": 1.0})
    monkeypatch.setattr(tocomo_runner, "run_model_with_fallback", lambda *args, **kwargs: {"SO2": 2.0})
    monkeypatch.setattr(tocomo_runner, "get_input_config", lambda: config)

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
            "tocomo_input": {"SO2": 2.0},
            "final": {},
        }

    monkeypatch.setattr(tocomo_runner, "build_storage_row", fake_build_storage_row)
    monkeypatch.setattr(tocomo_runner, "build_graph_from_merge_definitions", lambda *args, **kwargs: ("graph", {"Storage": "storage"}))
    monkeypatch.setattr(tocomo_runner, "save_tocomo_results", lambda *args, **kwargs: None)

    results = tocomo_runner.run_reaction()

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

    monkeypatch.setattr(tocomo_runner, "source_results_for_tocomo", lambda: source_rows)
    monkeypatch.setattr(
        tocomo_runner,
        "to_tocomo_input_from_source_state",
        lambda state: {"SO2": float(state["total_massflow"])},
    )
    monkeypatch.setattr(
        tocomo_runner,
        "run_model_with_fallback",
        lambda model_id, input_concentrations, **kwargs: {"SO2": input_concentrations["SO2"] + 1.0},
    )
    monkeypatch.setattr(tocomo_runner, "get_input_config", lambda: config)
    monkeypatch.setattr(tocomo_runner, "build_graph_from_merge_definitions", lambda *args, **kwargs: ("graph", {"Storage": "storage"}))
    monkeypatch.setattr(tocomo_runner, "save_tocomo_results", lambda *args, **kwargs: None)

    progress: list[tuple[int, int, str | None]] = []
    results = tocomo_runner.run_reaction(progress_callback=lambda c, t, lbl: progress.append((c, t, lbl)))

    assert len(results) == 3
    assert results[-1]["source_type"] == "storage"
    assert progress[0] == (0, 2, "Starting")
    assert progress[-1] == (2, 2, "Completed")


def test_run_reaction_saves_output_pipeline(monkeypatch):
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

    monkeypatch.setattr(tocomo_runner, "source_results_for_tocomo", lambda: source_rows)
    monkeypatch.setattr(tocomo_runner, "to_tocomo_input_from_source_state", lambda state: {"SO2": 1.0})
    monkeypatch.setattr(tocomo_runner, "run_model_with_fallback", lambda *args, **kwargs: {"SO2": 2.0})
    monkeypatch.setattr(tocomo_runner, "get_input_config", lambda: config)
    monkeypatch.setattr(
        tocomo_runner,
        "build_graph_from_merge_definitions",
        lambda *args, **kwargs: ("graph", {"Storage": "storage"}),
    )
    monkeypatch.setattr(
        tocomo_runner,
        "build_storage_row",
        lambda *args, **kwargs: {
            "source_type": "storage",
            "source_name": "Storage",
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "temperature_kelvin": 300.0,
            "total_massflow": 5.0,
            "tocomo_input": {"SO2": 2.0},
            "final": {},
        },
    )

    def fake_save(results, pipeline_map_name, graph, node_types, plant_names):
        captured["pipeline_map_name"] = pipeline_map_name
        captured["graph"] = graph
        captured["node_types"] = node_types
        captured["plant_names"] = plant_names
        captured["results_len"] = len(results)

    monkeypatch.setattr(tocomo_runner, "save_tocomo_results", fake_save)

    results = tocomo_runner.run_reaction()

    assert results
    assert results[0]["final"]["SO2"] == 2.0
    assert captured["pipeline_map_name"] == "demo"
    assert captured["graph"] == "graph"
    assert captured["node_types"] == {"Storage": "storage"}
    assert captured["plant_names"] == {0: "Plant 1"}
    assert captured["results_len"] == 2
