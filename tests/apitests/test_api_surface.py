import importlib

import pytest


def test_fastapi_app_includes_expected_routes():
    pytest.importorskip("fastapi")
    app_module = importlib.import_module("internshipwork.api.app")
    app = app_module.app

    path_map = app.openapi().get("paths", {})

    # Core API surface used by the frontend.
    assert "/api/config/" in path_map
    assert "/api/maps/" in path_map
    assert "/api/results/{model}" in path_map
    assert "/api/simulate/{model}" in path_map
    assert "/api/simulate/jobs/{job_id}" in path_map

    map_item = path_map.get("/api/maps/{name}", {})
    assert "get" in map_item
    assert "put" in map_item


def test_session_info_schema_supports_graph_urls():
    schemas = importlib.import_module("internshipwork.api.schemas")

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
