"""Pipeline/input helpers for TOCOMO execution."""

from typing import Any

from backend.merge_support import build_merge_inputs_from_definitions
from backend.merge_support.calculations import _bara_to_pa, _build_plant_source_dict, _concentration_to_molar_ppm
from backend.pipemapping.workflow import build_pipe_graph_with_inputs_interactive
from backend.user_inputs import get_input_config


def resolve_merge_input_config(use_dev_pipeline_map: bool = False) -> dict[str, object]:
    """Load merge config from dev map or interactive pipeline builder."""
    # Note: when use_dev_pipeline_map=True, the map should already be loaded in global
    # input_config by the caller (main.py calls apply_dev_pipeline_map before runners).

    input_config = get_input_config()
    if input_config.get("merge_definitions"):
        # Reuse existing config when already provided by caller/workflow.
        return input_config

    # Fallback to interactive graph construction when no merge topology exists.
    _graph, _node_types, generated_config = build_pipe_graph_with_inputs_interactive()
    return generated_config


def to_tocomo_input_from_source_state(source_state: dict[str, Any]) -> dict[str, float]:
    """Convert source state (plant/merge) into TOCOMO molar-ppm input.
    
    Species are now consistently capitalized (O2, H2O, etc.) throughout the system.
    """
    # Species supported by TOCOMO model (now in capitalized form matching AcidWatch output).
    supported_species = ("H2O", "O2", "SO2", "NO2", "H2S")

    if "ppm_molar" in source_state:
        # Plants/merges may already provide molar ppm; use directly when present.
        ppm_molar = source_state["ppm_molar"]
        return {
            species: float(ppm_molar.get(species, 0.0))
            for species in supported_species
        }

    # Otherwise, derive molar ppm from concentration + pressure + temperature.
    input_config = get_input_config()
    pressure_pa = _bara_to_pa(float(input_config["p_bara"]))
    temperature_kelvin = float(source_state["temperature_kelvin"])
    initial_conc = source_state["initial_merge_conc"]
    return {
        species: float(
            _concentration_to_molar_ppm(
                float(initial_conc.get(species, 0.0)),
                pressure_pa,
                temperature_kelvin,
            )
        )
        for species in supported_species
    }


def source_results_for_tocomo(
    use_dev_pipeline_map: bool,
) -> list[tuple[str, str | int, dict[str, Any]]]:
    """Collect all plant and merge source states to evaluate with TOCOMO."""
    input_config = resolve_merge_input_config(use_dev_pipeline_map=use_dev_pipeline_map)
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
