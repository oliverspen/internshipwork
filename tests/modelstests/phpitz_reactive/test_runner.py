import importlib
from pathlib import Path


phpitz_runner = importlib.import_module("internshipwork.models.phpitz_reactive.runner")


def test_build_storage_row_mixes_terminal_rows_weighted():
    results = [
        {
            "source_type": "merge",
            "source_name": "Merge A",
            "stream_phase": "gas",
            "density_kg_per_m3": 2.0,
            "temperature_kelvin": 300.0,
            "total_massflow": 10.0,
            "final": {"SO2": 2.0},
        },
        {
            "source_type": "merge",
            "source_name": "Merge B",
            "stream_phase": "liquid",
            "density_kg_per_m3": 4.0,
            "temperature_kelvin": 320.0,
            "total_massflow": 30.0,
            "final": {"SO2": 6.0},
        },
    ]
    merge_definitions = [
        {"merge_name": "Merge A", "sources": [("plant", 0)]},
        {"merge_name": "Merge B", "sources": [("plant", 1)]},
    ]

    storage = phpitz_runner._build_storage_row(results, merge_definitions)

    assert storage is not None
    assert storage["stream_phase"] == "liquid"
    assert storage["total_massflow"] == 40.0
    assert storage["density_kg_per_m3"] == 3.5
    assert storage["temperature_kelvin"] == 315.0
    assert storage["tocomo_input"]["SO2"] == 5.0


def test_run_reaction_without_saving_executes_progress_and_storage(monkeypatch):
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

    monkeypatch.setattr(phpitz_runner, "source_results_for_phpitz_reactive", lambda **kwargs: source_rows)
    monkeypatch.setattr(
        phpitz_runner,
        "to_phpitz_reactive_input_from_source_state",
        lambda state: {"SO2": float(state["total_massflow"])},
    )
    monkeypatch.setattr(
        phpitz_runner,
        "post_model",
        lambda model_id, input_concentrations, **kwargs: {"SO2": input_concentrations["SO2"] + 1.0},
    )
    monkeypatch.setattr(phpitz_runner, "get_input_config", lambda: config)

    progress: list[tuple[int, int, str | None]] = []
    results = phpitz_runner.run_reaction(
        use_dev_pipeline_map=True,
        save_results=False,
        progress_callback=lambda c, t, lbl: progress.append((c, t, lbl)),
    )

    assert len(results) == 3
    assert results[-1]["source_type"] == "storage"
    assert progress[0] == (0, 2, "Starting")
    assert progress[-1] == (2, 2, "Completed")


def test_run_reaction_with_saving_calls_output_pipeline(monkeypatch, tmp_path: Path):
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

    monkeypatch.setattr(phpitz_runner, "source_results_for_phpitz_reactive", lambda **kwargs: source_rows)
    monkeypatch.setattr(phpitz_runner, "to_phpitz_reactive_input_from_source_state", lambda state: {"SO2": 1.0})
    monkeypatch.setattr(phpitz_runner, "post_model", lambda *args, **kwargs: {"SO2": 2.0})
    monkeypatch.setattr(phpitz_runner, "get_input_config", lambda: config)
    monkeypatch.setattr(phpitz_runner, "build_graph_from_merge_definitions", lambda *args, **kwargs: ("graph", {"Storage": "storage"}))

    session_dir = tmp_path / "session"
    session_dir.mkdir()
    monkeypatch.setattr(phpitz_runner, "save_phpitz_reactive_results", lambda *args, **kwargs: str(session_dir))

    results = phpitz_runner.run_reaction(use_dev_pipeline_map=False, save_results=True)

    assert results
    assert results[0]["final"]["SO2"] == 2.0
