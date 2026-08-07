"""Maps endpoints — list, retrieve, save, and edit named pipeline maps."""

from fastapi import APIRouter, HTTPException

from ..schemas import PipelineMapCreateRequest, PipelineMapInfo, PipelineMapLayoutUpdateRequest
from backend.pipemapping.dev_pipeline_map import (
    _all_dev_pipeline_maps,
    delete_dev_pipeline_map,
    register_dev_pipeline_map,
    update_dev_pipeline_map_node_positions,
)

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
    node_positions = {
        node_id: pos.model_dump()
        for node_id, pos in (body.pipeline_map.node_positions or {}).items()
    }
    register_dev_pipeline_map(
        map_name=body.name,
        merge_definitions=merge_definitions,
        merge_pipe_inputs=merge_pipe_inputs,
        selected_plant_indexes=body.pipeline_map.selected_plant_indexes or [],
        storage_name=(body.pipeline_map.storage_name or "Storage").strip() or "Storage",
        node_positions=node_positions,
    )
    return PipelineMapInfo(
        name=body.name,
        merge_count=len(merge_definitions),
        merge_names=list(merge_pipe_inputs.keys()),
    )


@router.put("/{name}", response_model=PipelineMapInfo)
def update_map(name: str, body: PipelineMapCreateRequest) -> PipelineMapInfo:
    """Overwrite an existing named pipeline map with new definitions."""
    all_maps = _all_dev_pipeline_maps()
    if name not in all_maps:
        raise HTTPException(404, f"Map '{name}' not found.")

    merge_definitions = [
        {"merge_name": md.merge_name, "sources": [list(s) for s in md.sources]}
        for md in body.pipeline_map.merge_definitions
    ]
    merge_pipe_inputs = {
        merge_name: inp.model_dump()
        for merge_name, inp in body.pipeline_map.merge_pipe_inputs.items()
    }
    node_positions = {
        node_id: pos.model_dump()
        for node_id, pos in (body.pipeline_map.node_positions or {}).items()
    }

    # Keep the original map key stable for edits.
    register_dev_pipeline_map(
        map_name=name,
        merge_definitions=merge_definitions,
        merge_pipe_inputs=merge_pipe_inputs,
        selected_plant_indexes=body.pipeline_map.selected_plant_indexes or [],
        storage_name=(body.pipeline_map.storage_name or "Storage").strip() or "Storage",
        node_positions=node_positions,
    )

    return PipelineMapInfo(
        name=name,
        merge_count=len(merge_definitions),
        merge_names=list(merge_pipe_inputs.keys()),
    )


@router.put("/{name}/layout", response_model=PipelineMapInfo)
def update_map_layout(name: str, body: PipelineMapLayoutUpdateRequest) -> PipelineMapInfo:
    """Persist node positions for an existing map layout."""
    all_maps = _all_dev_pipeline_maps()
    if name not in all_maps:
        raise HTTPException(404, f"Map '{name}' not found.")

    node_positions = {
        node_id: pos.model_dump()
        for node_id, pos in body.node_positions.items()
    }
    update_dev_pipeline_map_node_positions(name, node_positions)
    updated_map = _all_dev_pipeline_maps()[name]

    return PipelineMapInfo(
        name=name,
        merge_count=len(updated_map.get("merge_definitions", [])),
        merge_names=list((updated_map.get("merge_pipe_inputs") or {}).keys()),
    )


@router.delete("/{name}", status_code=204)
def delete_map(name: str) -> None:
    """Delete a saved pipeline map by name."""
    all_maps = _all_dev_pipeline_maps()
    if name not in all_maps:
        raise HTTPException(404, f"Map '{name}' not found.")

    delete_dev_pipeline_map(name)
