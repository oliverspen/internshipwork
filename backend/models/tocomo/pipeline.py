"""Pipeline/input helpers for TOCOMO execution."""

from typing import Any

from backend.merge_support import build_merge_inputs_from_definitions
from backend.merge_support.calculations import _build_plant_source_dict
from backend.user_inputs import get_input_config


def to_tocomo_input_from_source_state(source_state: dict[str, Any]) -> dict[str, float]:
    supported_species = ("H2O", "O2", "SO2", "NO2", "H2S")
    ppm_molar = source_state["ppm_molar"]
    return {
        species: float(ppm_molar.get(species, 0.0))
        for species in supported_species
    }


def source_results_for_tocomo() -> list[tuple[str, str | int, dict[str, Any]]]:
    """Collect all plant and merge source states to evaluate with TOCOMO."""
    input_config = get_input_config()
    merge_definitions = input_config.get("merge_definitions") or []

    # Collect plant indices — from merge sources when merges exist, otherwise all plants.
    plant_indices: set[int] = set()
    if merge_definitions:
        for merge_definition in merge_definitions:
            for source_type, source_value in merge_definition["sources"]:
                if source_type == "plant":
                    plant_indices.add(int(source_value))
    else:
        # No merges: plants feed directly into storage — include all configured plants.
        plant_inputs = input_config.get("plant_inputs")
        plant_indices = set(range(len(plant_inputs)))

    # Add each plant source state in ascending index order.
    source_rows: list[tuple[str, str | int, dict[str, Any]]] = []
    for plant_idx in sorted(plant_indices):
        source_rows.append(("plant", plant_idx, _build_plant_source_dict(plant_idx)))

    # Compute merge stream compositions and append them after the plants.
    if merge_definitions:
        merge_results = build_merge_inputs_from_definitions(merge_definitions)
        for merge_definition in merge_definitions:
            merge_name = str(merge_definition["merge_name"])
            source_rows.append(("merge", merge_name, merge_results[merge_name]))

    return source_rows
