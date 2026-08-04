"""Flow resolver module for calculating merge properties in topological order.

Handles dependency resolution for merges that feed into other merges (cascading merges).
Processes merge definitions in topological order to ensure downstream merges can use
upstream merge outputs as inputs.

Main entry points:
- build_merge_inputs_from_definitions: Resolve ordered merge definitions
- build_merge_inputs_from_pipe_graph: Convert graph to merge definitions and resolve
"""

from typing import Any

from .calculations import _build_merge_input_from_source_states, _build_plant_source_dict
from .topology import build_merge_definitions

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
                # Downstream merges can only use merges that were already resolved.
                if source_value not in resolved_merges:
                    raise ValueError(f"Merge '{merge_name}' depends on unknown merge '{source_value}'.")

                # Reuse the computed merge output as an input source dict.
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

            # Any other source type is not supported.
            raise ValueError(f"Unsupported source type '{source_type}' for merge '{merge_name}'.")

        # Run the actual mixing calculation for this merge node.
        resolved_merges[merge_name] = _build_merge_input_from_source_states(
            source_dicts,
            merge_name=merge_name,
        )

    # Return all computed merges keyed by merge name.
    return resolved_merges


def build_merge_inputs_from_pipe_graph(
    graph,
    node_types: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Build merge inputs directly from the pipeline graph created in pipemapping.py."""
    # First convert the graph into plain merge definitions.
    merge_definitions = build_merge_definitions(graph, node_types)
    # Then resolve those definitions into calculated merge inputs.
    return build_merge_inputs_from_definitions(merge_definitions)
