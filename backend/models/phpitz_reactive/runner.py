"""High-level PH_PITZ reactive run orchestration."""

from pathlib import Path
from typing import Any
from typing import Callable

from backend.output import save_phpitz_reactive_results
from backend.user_inputs import get_input_config

from backend.output.graph import build_graph_from_merge_definitions

from backend.models.api_client import post_model
from .pipeline import source_results_for_phpitz_reactive, to_phpitz_reactive_input_from_source_state


def _build_storage_row(
    results: list[dict],
    merge_definitions: list[dict],
    storage_name: str = "Storage",
) -> dict[str, Any] | None:
    """Build a storage row by mixing all terminal node outputs.

    If merges exist, terminal merges (not used as sources in other merges) feed storage.
    If there are no merges, all plants feed storage directly.
    Outputs are mixed using a flowrate-weighted average when multiple sources exist.
    """
    if merge_definitions:
        # Find merge names that feed into another merge (non-terminal).
        upstream_merges: set[str] = set()
        for merge_def in merge_definitions:
            for source_type, source_value in merge_def.get("sources", []):
                if source_type == "merge":
                    upstream_merges.add(str(source_value))

        terminal_rows = [
            r for r in results
            if str(r.get("source_type")) == "merge"
            and str(r.get("source_name")) not in upstream_merges
        ]
    else:
        # No merges — all plants feed storage directly.
        terminal_rows = [r for r in results if str(r.get("source_type")) == "plant"]

    total_flow = sum(float(r.get("total_massflow") or 0) for r in terminal_rows)

    if total_flow == 0:
        # Fall back to last terminal row if flowrates are missing.
        terminal = terminal_rows[-1]
        return {
            "source_type": "storage",
            "source_name": storage_name,
            "stream_phase": terminal.get("stream_phase"),
            "density_kg_per_m3": terminal.get("density_kg_per_m3"),
            "temperature_kelvin": terminal.get("temperature_kelvin"),
            "total_massflow": None,
            "tocomo_input": terminal.get("final", {}),
            "final": {},
        }

    # Flowrate-weighted average of all terminal node outputs.
    all_species: set[str] = set()
    for r in terminal_rows:
        all_species.update(r.get("final", {}).keys())

    mixed_composition: dict[str, float] = {
        species: sum(
            float(r.get("final", {}).get(species, 0.0)) * float(r.get("total_massflow") or 0)
            for r in terminal_rows
        ) / total_flow
        for species in sorted(all_species)
    }

    # Weighted average temperature and density.
    mixed_temperature = sum(
        float(r.get("temperature_kelvin") or 0) * float(r.get("total_massflow") or 0)
        for r in terminal_rows
    ) / total_flow
    mixed_density = sum(
        float(r.get("density_kg_per_m3") or 0) * float(r.get("total_massflow") or 0)
        for r in terminal_rows
    ) / total_flow

    # Storage is liquid if any incoming stream is liquid.
    stream_phase = (
        "liquid" if any(r.get("stream_phase") == "liquid" for r in terminal_rows) else "gas"
    )

    return {
        "source_type": "storage",
        "source_name": storage_name,
        "stream_phase": stream_phase,
        "density_kg_per_m3": round(mixed_density, 5),
        "temperature_kelvin": round(mixed_temperature, 5),
        "total_massflow": round(total_flow, 5),
        "tocomo_input": mixed_composition,
        "final": {},
    }


def run_reaction(
    use_dev_pipeline_map: bool = False,
    save_results: bool = True,
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> list[dict]:
    """Run PH_PITZ reactive simulation on plants, merges, and storage."""
    results: list[dict] = []
    source_rows = source_results_for_phpitz_reactive(use_dev_pipeline_map=use_dev_pipeline_map)
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
        print(f"  [{source_label}] phase={source_state.get('stream_phase', 'unknown')}, density={float(source_state.get('density_kg_per_m3', 0.0)):.3f} kg/m³")

        temperature_kelvin = float(source_state.get("temperature_kelvin", 298.15))
        final_values = post_model(
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
        storage_row = _build_storage_row(results, merge_definitions, storage_name=storage_name)
        if storage_row:
            results.append(storage_row)

    if save_results:
        merge_definitions = input_config.get("merge_definitions") or []

        graph, node_types = build_graph_from_merge_definitions(
            merge_definitions,
            plant_names,
            storage_name=storage_name,
        )

        session_dir = save_phpitz_reactive_results(
            results,
            pipeline_map_name=str(pipeline_map_name) if pipeline_map_name is not None else None,
            graph=graph,
            node_types=node_types,
            plant_names=plant_names,
        )
        session_path = Path(session_dir)
        html_files = list(session_path.glob("*_map.html"))
        print(f"Results saved to: {session_path}")
        if html_files:
            print(f"Pipeline map:     {html_files[0].name}")
    else:
        print("PH_PITZ reactive result export disabled (save_results=False).")

    if progress_callback and total_sources > 0:
        progress_callback(total_sources, total_sources, "Completed")

    return results


if __name__ == "__main__":
    run_reaction()
