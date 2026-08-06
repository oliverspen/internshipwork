"""High-level TOCOMO run orchestration."""

from pathlib import Path
from pprint import pprint
from typing import Callable

from backend.output import save_tocomo_results
from backend.user_inputs import get_input_config

from backend.models.acidwatch_run_file import run_model_with_fallback
from backend.output.graph import build_graph_from_merge_definitions
from .pipeline import source_results_for_tocomo, to_tocomo_input_from_source_state


def _build_storage_row(
    results: list[dict],
    merge_definitions: list[dict],
    storage_name: str = "Storage",
) -> dict | None:
    """Build a storage row by mixing terminal stream outputs (merge-like logic)."""
    if merge_definitions:
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
        terminal_rows = [r for r in results if str(r.get("source_type")) == "plant"]

    if not terminal_rows:
        return None

    total_flow = sum(float(r.get("total_massflow") or 0) for r in terminal_rows)

    if total_flow == 0:
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

    mixed_temperature = sum(
        float(r.get("temperature_kelvin") or 0) * float(r.get("total_massflow") or 0)
        for r in terminal_rows
    ) / total_flow
    mixed_density = sum(
        float(r.get("density_kg_per_m3") or 0) * float(r.get("total_massflow") or 0)
        for r in terminal_rows
    ) / total_flow
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
    save_results: bool = True,
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
        print(
            "Running TOCOMO for {label}: phase={phase}, density={density:.5f} kg/m^3".format(
                label=source_label,
                phase=source_state.get("stream_phase", "unknown"),
                density=float(source_state.get("density_kg_per_m3", 0.0)),
            )
        )

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
        storage_row = _build_storage_row(results, merge_definitions, storage_name=storage_name)
        if storage_row:
            results.append(storage_row)

    print("TOCOMO final values:")
    pprint(results)

    if save_results:
        # Gather naming/topology metadata for JSON/Excel/HTML export.
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

        # Persist session outputs and print generated artifact paths.
        session_dir = save_tocomo_results(
            results,
            pipeline_map_name=str(pipeline_map_name) if pipeline_map_name is not None else None,
            graph=graph,
            node_types=node_types,
            plant_names=plant_names,
        )
        session_path = Path(session_dir)
        summary_excel = session_path / "summary.xlsx"
        print(f"Saved TOCOMO summary Excel:  {summary_excel}")
        print(f"Per-source files saved in:   {session_path}")
        png_files = list(session_path.glob("*_map.png"))
        html_files = list(session_path.glob("*_map.html"))
        if png_files:
            print(f"Saved annotated pipeline map (PNG):  {png_files[0]}")
        if html_files:
            print(f"Saved interactive pipeline map (HTML): {html_files[0]}")
    else:
        print("TOCOMO result export disabled (save_results=False).")

    if progress_callback and total_sources > 0:
        progress_callback(total_sources, total_sources, "Completed")

    return results


if __name__ == "__main__":
    run_reaction()
