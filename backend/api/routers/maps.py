"""Maps endpoints — list, retrieve, and save named pipeline maps."""

from fastapi import APIRouter, HTTPException

from ..schemas import PipelineMap, PipelineMapCreateRequest, PipelineMapInfo
from backend.pipemapping.dev_pipeline_map import _all_dev_pipeline_maps, register_dev_pipeline_map

router = APIRouter()


@router.get("/", response_model=list[PipelineMapInfo])
def list_maps() -> list[PipelineMapInfo]:
    """List all saved pipeline maps."""
    return [
        PipelineMapInfo(
            name=name,
            merge_count=len(data["merge_definitions"]),
            merge_names=list(data["merge_pipe_inputs"].keys()),
        )
        for name, data in _all_dev_pipeline_maps().items()
    ]


@router.get("/{name}")
def get_map(name: str):
    """Return the full definition of a saved pipeline map."""
    all_maps = _all_dev_pipeline_maps()
    if name not in all_maps:
        raise HTTPException(404, f"Map '{name}' not found.")
    return all_maps[name]


@router.post("/", response_model=PipelineMapInfo, status_code=201)
def create_map(body: PipelineMapCreateRequest) -> PipelineMapInfo:
    """Save a new named pipeline map for reuse."""
    merge_definitions = [
        {"merge_name": md.merge_name, "sources": [list(s) for s in md.sources]}
        for md in body.pipeline_map.merge_definitions
    ]
    merge_pipe_inputs = {
        name: inp.model_dump()
        for name, inp in body.pipeline_map.merge_pipe_inputs.items()
    }
    register_dev_pipeline_map(
        map_name=body.name,
        merge_definitions=merge_definitions,
        merge_pipe_inputs=merge_pipe_inputs,
        storage_name=(body.pipeline_map.storage_name or "Storage").strip() or "Storage",
    )
    return PipelineMapInfo(
        name=body.name,
        merge_count=len(merge_definitions),
        merge_names=list(merge_pipe_inputs.keys()),
    )


@router.put("/{name}", response_model=PipelineMapInfo)
def update_map(name: str, body: PipelineMap) -> PipelineMapInfo:
    """Update an existing named pipeline map."""
    all_maps = _all_dev_pipeline_maps()
    if name not in all_maps:
        raise HTTPException(404, f"Map '{name}' not found.")

    merge_definitions = [
        {"merge_name": md.merge_name, "sources": [list(s) for s in md.sources]}
        for md in body.merge_definitions
    ]
    merge_pipe_inputs = {
        merge_name: merge_pipe_input.model_dump()
        for merge_name, merge_pipe_input in body.merge_pipe_inputs.items()
    }

    register_dev_pipeline_map(
        map_name=name,
        merge_definitions=merge_definitions,
        merge_pipe_inputs=merge_pipe_inputs,
        storage_name=(body.storage_name or "Storage").strip() or "Storage",
    )

    return PipelineMapInfo(
        name=name,
        merge_count=len(merge_definitions),
        merge_names=list(merge_pipe_inputs.keys()),
    )
