import importlib


def test_pipeline_map_create_request_allows_spaces_in_name():
    schemas = importlib.import_module("internshipwork.api.schemas")

    req = schemas.PipelineMapCreateRequest(
        name="North Sea Export",
        pipeline_map={
            "merge_definitions": [],
            "merge_pipe_inputs": {},
            "storage_name": "Storage",
        },
    )

    assert req.name == "North Sea Export"
