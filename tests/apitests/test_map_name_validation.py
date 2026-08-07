import importlib

import pytest


def test_pipeline_map_create_request_allows_spaces_in_name():
    pytest.importorskip("pydantic")
    schemas = importlib.import_module("backend.api.schemas")

    req = schemas.PipelineMapCreateRequest(
        name="North Sea Export",
        pipeline_map={
            "merge_definitions": [],
            "merge_pipe_inputs": {},
            "selected_plant_indexes": [0, 2],
            "storage_name": "Storage",
        },
    )

    assert req.name == "North Sea Export"
    assert req.pipeline_map.selected_plant_indexes == [0, 2]
