"""Excel export for TOCOMO results."""

from pathlib import Path
from typing import Any

import pandas as pd

from .utils import build_excel_rows, build_storage_row
from backend.user_inputs import get_input_config


def _with_model_column(df: pd.DataFrame, model_used: str | None) -> pd.DataFrame:
    """Ensure exported tables include a model column for traceability."""
    model_value = (model_used or "unknown").strip() or "unknown"
    if "model" in df.columns:
        df = df.drop(columns=["model"])
    df.insert(0, "model", model_value)
    return df


def save_summary_excel(
    results: list[dict[str, Any]],
    output_dir: Path,
    model_used: str | None = None,
) -> Path:
    """Save combined results as Excel with a separate Storage Results table."""
    summary_excel_path = (output_dir / "summary.xlsx").resolve()

    # Split storage row out of the main results.
    main_results = [r for r in results if str(r.get("source_type", "")) != "storage"]
    storage_results = [r for r in results if str(r.get("source_type", "")) == "storage"]

    try:
        input_config = get_input_config()
        plant_inputs = input_config.get("plant_inputs", []) if isinstance(input_config, dict) else []
    except Exception:
        plant_inputs = []

    main_df = _with_model_column(
        pd.DataFrame(build_excel_rows(main_results, plant_inputs=plant_inputs)),
        model_used,
    )
    storage_df = (
        _with_model_column(pd.DataFrame(build_storage_row(storage_results)), model_used)
        if storage_results
        else pd.DataFrame()
    )

    with pd.ExcelWriter(summary_excel_path, engine="openpyxl") as writer:
        main_df.to_excel(writer, sheet_name="Results", index=False, startrow=0)

        if not storage_df.empty:
            # Leave a blank row gap then write the storage table.
            start_row = len(main_df) + 3
            header_ws = writer.sheets["Results"]
            header_ws.cell(row=start_row, column=1, value="Storage Results")
            storage_df.to_excel(
                writer,
                sheet_name="Results",
                index=False,
                startrow=start_row,
            )

    return summary_excel_path


def save_dynamic_excel(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    output_dir: Path,
    model_used: str | None = None,
) -> Path:
    """Save dynamic simulation results as Excel with separate tables for each entity.
    
    Sheet order: Plants first, then Merges, then Storage at the end.
    
    Args:
        dynamic_results: List of merge result dicts from simulation
        plant_results: List of plant result dicts from simulation
        output_dir: Directory to save Excel file
    
    Returns:
        Path to saved Excel file
    """
    excel_path = (output_dir / "dynamic_results.xlsx").resolve()

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # 1. Write storage sheet first with simulation time_days aligned to plant/merge sheets.
        if dynamic_results:
            merge_table = pd.DataFrame(dynamic_results)
            merge_names_set = set(merge_table["merge_name"].astype(str).unique())
            downstream_sources: set[str] = set()
            for sources_text in merge_table.get("sources", pd.Series([], dtype=object)).dropna().astype(str):
                for token in (p.strip() for p in sources_text.split(",")):
                    if token in merge_names_set:
                        downstream_sources.add(token)
            terminal_merges = sorted(merge_names_set - downstream_sources)

            if terminal_merges:
                storage_data = []
                for result in dynamic_results:
                    if str(result.get("merge_name")) not in terminal_merges:
                        continue
                    row = {
                        "model": (model_used or "unknown").strip() or "unknown",
                        "time_days": result.get("time_days"),
                        "source": "Storage",
                        "temperature_celsius": result.get("temperature_celsius"),
                        "flow_kg_per_h": result.get("flow_kg_per_h"),
                        "stream_phase": result.get("stream_phase"),
                        "density_kg_per_m3": result.get("density_kg_per_m3"),
                    }
                    # Add final contaminant concentrations from the merge
                    final_dict = result.get("final", {})
                    if isinstance(final_dict, dict):
                        for species, value in sorted(final_dict.items()):
                            row[f"final_{species}"] = value
                    storage_data.append(row)

                if storage_data:
                    storage_df = pd.DataFrame(storage_data).sort_values("time_days")
                    storage_df.to_excel(writer, sheet_name="Storage", index=False)

        # 2. Write separate table for each plant
        if plant_results:
            plant_names = sorted(set(r.get("plant_name") for r in plant_results if r.get("plant_name")))

            for plant_name in plant_names:
                plant_rows_for_name = [r for r in plant_results if r.get("plant_name") == plant_name]

                plant_data = []
                for result in plant_rows_for_name:
                    row = {
                        "model": (model_used or "unknown").strip() or "unknown",
                        "time_days": result.get("time_days"),
                        "temperature_celsius": result.get("temperature_celsius"),
                        "flow_kg_per_h": result.get("flow_kg_per_h"),
                        "stream_phase": result.get("stream_phase"),
                        "density_kg_per_m3": result.get("density_kg_per_m3"),
                    }
                    for key, value in sorted(result.items()):
                        if key.startswith("inlet_"):
                            row[key] = value
                    # Include final contaminant concentrations if available
                    final_dict = result.get("final", {})
                    if isinstance(final_dict, dict):
                        for species, value in sorted(final_dict.items()):
                            row[f"final_{species}"] = value
                    plant_data.append(row)

                plant_df = pd.DataFrame(plant_data)
                sheet_name = f"Plant_{plant_name}"[:31]
                plant_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 3. Write separate table for each merge
        if dynamic_results:
            merge_names = sorted(set(r.get("merge_name") for r in dynamic_results if r.get("merge_name")))

            for merge_name in merge_names:
                merge_rows_for_name = [r for r in dynamic_results if r.get("merge_name") == merge_name]

                merge_data = []
                for result in merge_rows_for_name:
                    row = {
                        "model": (model_used or "unknown").strip() or "unknown",
                        "time_days": result.get("time_days"),
                        "temperature_celsius": result.get("temperature_celsius"),
                        "flow_kg_per_h": result.get("flow_kg_per_h"),
                        "stream_phase": result.get("stream_phase"),
                        "density_kg_per_m3": result.get("density_kg_per_m3"),
                    }
                    # Add inlet contaminant concentrations
                    for key, value in sorted(result.items()):
                        if key.startswith("inlet_"):
                            row[key] = value
                    # Add final contaminant concentrations
                    final_dict = result.get("final", {})
                    if isinstance(final_dict, dict):
                        for species, value in sorted(final_dict.items()):
                            row[f"final_{species}"] = value
                    merge_data.append(row)

                merge_df = pd.DataFrame(merge_data)
                sheet_name = f"Merge_{merge_name}"[:31]
                merge_df.to_excel(writer, sheet_name=sheet_name, index=False)

    return excel_path

