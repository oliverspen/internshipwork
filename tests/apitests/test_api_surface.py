import importlib

import pytest


def test_fastapi_app_includes_expected_routes():
    pytest.importorskip("fastapi")
    app_module = importlib.import_module("backend.api.app")
    app = app_module.app

    path_map = app.openapi().get("paths", {})

    # Core API surface used by the frontend.
    assert "/api/config/" in path_map
    assert "/api/maps/" in path_map
    assert "/api/results/{model}" in path_map
    assert "/api/simulate/{model}" in path_map
    assert "/api/simulate/jobs/{job_id}" in path_map


def test_session_info_schema_supports_graph_urls():
    pytest.importorskip("pydantic")
    schemas = importlib.import_module("backend.api.schemas")

    session = schemas.SessionInfo(
        session_id="20260731_120000_demo",
        model="phpitz_dynamic",
        pipeline_map_name="demo",
        html_url=None,
        graph_urls=["/results/phpitz_dynamic/20260731_120000_demo/graphs/flowgraph.png"],
        summary_excel_url="/results/phpitz_dynamic/20260731_120000_demo/dynamic_results.xlsx",
    )

    assert session.graph_urls
    assert session.graph_urls[0].endswith("flowgraph.png")


def test_build_config_from_request_filters_plants_for_no_merge_map(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    simulation = importlib.import_module("backend.api.routers.simulation")

    base_config = {
        "plant_inputs": [
            {
                "name": "Plant 1",
                "inlet_conc": {"O2": 1.0},
                "stream_phase": "gas",
                "flowrate": 10.0,
                "temperature_celsius": 25.0,
                "pipelength": 100.0,
                "pipediameter": 0.5,
            },
            {
                "name": "Plant 2",
                "inlet_conc": {"O2": 2.0},
                "stream_phase": "gas",
                "flowrate": 20.0,
                "temperature_celsius": 30.0,
                "pipelength": 200.0,
                "pipediameter": 0.6,
            },
            {
                "name": "Plant 3",
                "inlet_conc": {"O2": 3.0},
                "stream_phase": "gas",
                "flowrate": 30.0,
                "temperature_celsius": 35.0,
                "pipelength": 300.0,
                "pipediameter": 0.7,
            },
        ],
        "merge_pipe_inputs": {},
        "p_bara": 8.0,
        "storage_name": "Tank",
    }
    saved_maps = {
        "simple": {
            "merge_definitions": [],
            "merge_pipe_inputs": {},
            "selected_plant_indexes": [0, 2],
            "storage_name": "Tank",
        }
    }

    monkeypatch.setattr(simulation, "get_input_config", lambda: base_config)
    monkeypatch.setattr(simulation, "_all_dev_pipeline_maps", lambda: saved_maps)

    request = simulation.SimulationRequest(map_name="simple")
    config = simulation._build_config_from_request(request)

    assert [plant["name"] for plant in config["plant_inputs"]] == ["Plant 1", "Plant 3"]
    assert config["merge_definitions"] == []
