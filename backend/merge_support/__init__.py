"""Merge support module for calculating equilibrium conditions at merge nodes.

This package provides utilities to calculate thermodynamic properties and fluid dynamics
for nodes where multiple streams are combined (merged) in a pipeline network. It converts
plant stream specifications into merge inlet conditions and handles downstream merge
calculations that depend on upstream merge results.

Key workflows:
1. Build merge topology from pipeline graph (topology module)
2. Calculate merge stream properties from source inputs (calculations module)
3. Resolve merge dependencies in topological order (flow module)

Public API:
- build_merge_definitions: Convert graph topology to merge definitions
- build_merge_input: Calculate single merge from plant streams
- build_merge_inputs_from_definitions: Resolve ordered merge definitions
- build_merge_inputs_from_pipe_graph: Convert graph directly to merge inputs
- run_merge_support: Display merge calculations for debugging
"""

from .calculations import build_merge_input
from .flow import build_merge_inputs_from_definitions, build_merge_inputs_from_pipe_graph
from .topology import build_merge_definitions
from backend.user_inputs import get_input_config


def run_merge_support() -> None:
    """Display calculated merge densities from active input configuration."""
    input_config = get_input_config()
    merge_definitions = input_config.get("merge_definitions")

    if not merge_definitions:
        return

    merge_results = build_merge_inputs_from_definitions(merge_definitions)
    print("Calculated merge densities:")
    for merge_name, merge_result in merge_results.items():
        print(
            f"- {merge_name}: phase={merge_result['stream_phase']}, "
            f"density={merge_result['density_kg_per_m3']:.5f} kg/m^3"
        )

__all__ = [
    "build_merge_definitions",
    "build_merge_input",
    "build_merge_inputs_from_definitions",
    "build_merge_inputs_from_pipe_graph",
    "run_merge_support",
]
