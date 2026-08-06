"""High-level TOCOMO run orchestration."""

from typing import Callable

from backend.output import save_tocomo_results
from backend.user_inputs import get_input_config

from backend.models.acidwatch_run_file import run_model_with_fallback
from backend.models.storage_builder import build_storage_row
from backend.output.graph import build_graph_from_merge_definitions
from .pipeline import source_results_for_tocomo, to_tocomo_input_from_source_state


def run_reaction(
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> list[dict]:
    """Run TOCOMO chemistry simulation on plants, merges, and storage."""
    results: list[dict] = []
    # Build all source states (plants + merges) that should be evaluated.
    source_rows = source_results_for_tocomo()
    total_sources = len(source_rows)
    if progress_callback and total_sources > 0:
        progress_callback(0, total_sources, "Starting")
    runtime_config = get_input_config()
    pipeline_map_name = runtime_config.get("pipeline_map_name")
    pressure_bara = float(runtime_config.get("p_bara", 10.0))
    storage_name = str(runtime_config.get("storage_name") or "Storage")

    for idx, (source_type, source_name, source_state) in enumerate(source_rows, start=1):
        # Convert current source state to backend-ready TOCOMO input.
        input_concentrations = to_tocomo_input_from_source_state(source_state)
        source_label = f"{source_type} {source_name}"

        temperature_kelvin = float(source_state.get("temperature_kelvin", 298.15))
        final_values = run_model_with_fallback(
            "tocomo",
            input_concentrations,
            temperature_kelvin=temperature_kelvin,
            pressure_bara=pressure_bara,
        )

        results.append(
            {
                "source_type": source_type,
                "source_name": source_name,
                "stream_phase": source_state.get("stream_phase"),
                "density_kg_per_m3": source_state.get("density_kg_per_m3"),
                "temperature_kelvin": temperature_kelvin,
                "total_massflow": source_state.get("total_massflow"),
                "tocomo_input": input_concentrations,
                "final": final_values,
            }
        )
        if progress_callback and total_sources > 0:
            progress_callback(idx, total_sources, source_label)

    if results:
        merge_definitions = runtime_config.get("merge_definitions") or []
        storage_row = build_storage_row(
            results,
            merge_definitions,
            storage_name=storage_name,
            pressure_bara=pressure_bara,
        )
        if storage_row:
            results.append(storage_row)

    input_config = get_input_config()
    merge_definitions = input_config.get("merge_definitions") or []
    plant_inputs = input_config.get("plant_inputs") or []
    plant_names: dict[int, str] = {
        idx: str(p.get("name", f"Plant {idx}"))
        for idx, p in enumerate(plant_inputs)
    }

    graph, node_types = build_graph_from_merge_definitions(
        merge_definitions,
        plant_names,
        storage_name=storage_name,
    )

    save_tocomo_results(
        results,
        pipeline_map_name=str(pipeline_map_name) if pipeline_map_name is not None else None,
        graph=graph,
        node_types=node_types,
        plant_names=plant_names,
    )

    if progress_callback and total_sources > 0:
        progress_callback(total_sources, total_sources, "Completed")

    return results


if __name__ == "__main__":
    run_reaction()
