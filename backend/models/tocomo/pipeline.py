"""Pipeline/input helpers for TOCOMO execution."""

from typing import Any

from backend.merge_support import build_merge_inputs_from_definitions
from backend.merge_support.calculations import _build_plant_source_dict
from backend.user_inputs import get_input_config


def to_tocomo_input_from_source_state(source_state: dict[str, Any]) -> dict[str, float]:
    """Convert source state (plant/merge) into TOCOMO molar-ppm input.
    
    Species are now consistently capitalized (O2, H2O, etc.) throughout the system.
    """
    supported_species = ("H2O", "O2", "SO2", "NO2", "H2S")
    ppm_molar = source_state["ppm_molar"]
    return {
        species: float(ppm_molar.get(species, 0.0))
        for species in supported_species
    }


def source_results_for_tocomo() -> list[tuple[str, str | int, dict[str, Any]]]:
    """Collect all plant and merge source states to evaluate with TOCOMO."""
    input_config = get_input_config()
    merge_definitions = input_config.get("merge_definitions")
    if not merge_definitions:
        raise ValueError("merge_definitions are required to run TOCOMO across the network.")

    # Collect unique plants used as merge sources.
    plant_indices: set[int] = set()
    for merge_definition in merge_definitions:
        for source_type, source_value in merge_definition["sources"]:
            if source_type == "plant":
                plant_indices.add(int(source_value))

    # Evaluate plants first, then merges in configured order.
    source_rows: list[tuple[str, str | int, dict[str, Any]]] = []
    for plant_idx in sorted(plant_indices):
        source_rows.append(("plant", plant_idx, _build_plant_source_dict(plant_idx)))

    merge_results = build_merge_inputs_from_definitions(merge_definitions)
    for merge_definition in merge_definitions:
        merge_name = str(merge_definition["merge_name"])
        source_rows.append(("merge", merge_name, merge_results[merge_name]))

    return source_rows
