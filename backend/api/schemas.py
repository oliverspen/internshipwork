"""Pydantic request/response models for the pipeline simulation API."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class PlantInput(BaseModel):
    name: str
    inlet_conc: dict[str, float]
    stream_phase: Literal["gas", "liquid"]
    flowrate: float
    temperature_celsius: float
    pipelength: float
    pipediameter: float


class MergePipeInput(BaseModel):
    pipelength: float
    pipediameter: float


class MergeDefinition(BaseModel):
    merge_name: str
    # Each source is ["plant", <int index>] or ["merge", "<merge name>"]
    sources: list[tuple[str, int | str]]


class PipelineMap(BaseModel):
    merge_definitions: list[MergeDefinition]
    merge_pipe_inputs: dict[str, MergePipeInput]
    storage_name: str | None = "Storage"


class SimulationRequest(BaseModel):
    # Use a saved map by name, or supply an inline pipeline_map.
    map_name: str | None = None
    pipeline_map: PipelineMap | None = None
    # Optional per-request plant overrides (must match index order used in merge sources).
    plant_inputs: list[PlantInput] | None = None
    p_bara: float | None = None
    # Optional dynamic-model timing overrides (days).
    duration_days: float | None = None
    dt_days: float | None = None
    # Optional dynamic profile overrides for plant variable changes.
    dynamic_profile: dict[str, Any] | None = None


class SessionInfo(BaseModel):
    session_id: str
    model: str
    pipeline_map_name: str | None = None
    html_url: str | None
    graph_urls: list[str] = Field(default_factory=list)
    summary_excel_url: str | None = None


class SimulationResponse(BaseModel):
    session_id: str | None
    model: str
    results: list[dict[str, Any]]
    html_url: str | None = None
    graph_urls: list[str] = Field(default_factory=list)
    summary_excel_url: str | None = None


class ConfigUpdateRequest(BaseModel):
    p_bara: float
    plant_inputs: list[PlantInput]
    merge_pipe_inputs: dict[str, MergePipeInput]
    storage_name: str | None = "Storage"


class PipelineMapCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Display name for the map; spaces are allowed.")
    pipeline_map: PipelineMap


class PipelineMapInfo(BaseModel):
    name: str
    merge_count: int
    merge_names: list[str]
