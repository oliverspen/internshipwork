"""Debug and test entry point for merge_support module.

Run with: python -m merge_support
Displays the active input configuration with enriched merge pipe metrics.
"""

from pprint import pprint

from pathlib import Path
import sys

# Support direct execution: python merge_support/__main__.py
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.user_inputs import get_input_config
from backend.merge_support import (
    build_merge_definitions,
    build_merge_input,
    build_merge_inputs_from_definitions,
    build_merge_inputs_from_pipe_graph,
)


def _build_config_with_merge_metrics(input_config: dict[str, object]) -> dict[str, object]:
    enriched_config = dict(input_config)
    merge_definitions = enriched_config.get("merge_definitions")
    merge_pipe_inputs = enriched_config.get("merge_pipe_inputs", {})

    enriched_merge_pipe_inputs: dict[str, dict[str, float]] = dict(merge_pipe_inputs)
    if merge_definitions:
        merge_results = build_merge_inputs_from_definitions(merge_definitions)
        for merge_name, merge_result in merge_results.items():
            if merge_name not in enriched_merge_pipe_inputs:
                continue

            enriched_merge_pipe_inputs[merge_name] = {
                **enriched_merge_pipe_inputs[merge_name],
                "merge_flow_speed": merge_result["flow_speed"],
                "merge_pipe_time": merge_result["pipe_time"],
                "merge_total_massflow": merge_result["total_massflow"],
                "merge_stream_phase": merge_result["stream_phase"],
                "merge_density_kg_per_m3": merge_result["density_kg_per_m3"],
            }

    enriched_config["merge_pipe_inputs"] = enriched_merge_pipe_inputs
    return enriched_config



def run_merge_support() -> None:
    print("merge_support loaded.")
    print("Active input config (from input_config.json unless overridden):")
    input_config = get_input_config()
    pprint(_build_config_with_merge_metrics(input_config))
    print("Available functions:")
    print("- build_merge_definitions")
    print("- build_merge_input")
    print("- build_merge_inputs_from_definitions")
    print("- build_merge_inputs_from_pipe_graph")


if __name__ == "__main__":
    run_merge_support()