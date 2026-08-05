"""Flow resolver module for calculating merge properties in topological order.

Handles dependency resolution for merges that feed into other merges (cascading merges).
Processes merge definitions in topological order to ensure downstream merges can use
upstream merge outputs as inputs.

Main entry point:
- build_merge_inputs_from_definitions: Resolve ordered merge definitions
"""

from typing import Any

from .calculations import _build_merge_input_from_source_states, _build_plant_source_dict

def build_merge_inputs_from_definitions(
    merge_definitions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build merge inputs from ordered plant/merge source definitions."""
    # This dictionary stores finished merge results by merge name.
    resolved_merges: dict[str, dict[str, Any]] = {}

    # Process merges in the order supplied by the topology helper.
    for merge_definition in merge_definitions:
        merge_name = merge_definition["merge_name"]
        # Gather all source dicts that feed into this merge.
        source_dicts: list[dict[str, Any]] = []

        # Each source is either a plant stream or an already-computed merge.
        for source_type, source_value in merge_definition["sources"]:
            if source_type == "plant":
                # Convert the plant index into the standard source dict structure.
                source_dicts.append(_build_plant_source_dict(int(source_value)))
                continue

            if source_type == "merge":
                merge_source = resolved_merges[source_value]
                source_dicts.append(
                    {
                        "source_type": "merge",
                        "source_name": source_value,
                        "temperature_kelvin": merge_source["temperature_kelvin"],
                        "total_massflow": merge_source["total_massflow"],
                        "stream_phase": merge_source["stream_phase"],
                        "initial_merge_conc": merge_source["initial_merge_conc"],
                    }
                )
                continue

        # Run the actual mixing calculation for this merge node.
        resolved_merges[merge_name] = _build_merge_input_from_source_states(
            source_dicts,
            merge_name=merge_name,
        )

    # Return all computed merges keyed by merge name.
    return resolved_merges
