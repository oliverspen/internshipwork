from typing import Any
from typing import Callable

from backend.output import save_phpitz_reactive_results
from backend.user_inputs import get_input_config

from backend.output.graph import build_graph_from_merge_definitions
from backend.models.storage_builder import build_storage_row

from backend.models.acidwatch_run_file import run_model_with_fallback
from .pipeline import source_results_for_phpitz_reactive, to_phpitz_reactive_input_from_source_state


def run_reaction(
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> list[dict]:
    """Run PH_PITZ reactive simulation on plants, merges, and storage."""
    results: list[dict] = []
    source_rows = source_results_for_phpitz_reactive()
    total_sources = len(source_rows)
    if progress_callback and total_sources > 0:
        progress_callback(0, total_sources, "Starting")
    input_config = get_input_config()
    pipeline_map_name = input_config.get("pipeline_map_name")
    storage_name = str(input_config.get("storage_name") or "Storage")
    pressure_bara = float(input_config.get("p_bara", 10.0))
    plant_inputs = input_config.get("plant_inputs") or []
    plant_names: dict[int, str] = {
        idx: str(p.get("name", f"Plant {idx}"))
        for idx, p in enumerate(plant_inputs)
    }

    for idx, (source_type, source_name, source_state) in enumerate(source_rows, start=1):
        input_concentrations = to_phpitz_reactive_input_from_source_state(source_state)
        display_name = plant_names.get(source_name, source_name) if source_type == "plant" else source_name
        source_label = f"{source_type} {display_name}"

        temperature_kelvin = float(source_state.get("temperature_kelvin", 298.15))
        final_values = run_model_with_fallback(
            "phpitz_reactive",
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
        merge_definitions = input_config.get("merge_definitions") or []
        storage_row = build_storage_row(
            results,
            merge_definitions,
            storage_name=storage_name,
            pressure_bara=pressure_bara,
        )
        if storage_row:
            results.append(storage_row)

    merge_definitions = input_config.get("merge_definitions") or []

    graph, node_types = build_graph_from_merge_definitions(
        merge_definitions,
        plant_names,
        storage_name=storage_name,
    )

    save_phpitz_reactive_results(
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
