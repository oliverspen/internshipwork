"""Dynamic TOCOMO simulation reporting with tables and plots.

Generates comprehensive reports for time-stepping TOCOMO simulations including:
- Compact change-point tables (plant and merge states)
- Multi-panel plots showing species concentrations over time
- Storage receipt analysis showing final merge conditions at storage node
- Automatic metric detection based on configured dynamic profiles

Main entry point: render_dynamic_reports() generates all tables and plots.
"""

import math
from pathlib import Path
from typing import Any

import matplotlib

# Use a non-interactive backend for API/background threads (avoids Tk main-loop errors).
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _infer_dt_days(dynamic_results: list[dict[str, Any]]) -> float:
    """Infer time step size from simulation results by finding smallest time difference.
    
    Args:
        dynamic_results: List of result dicts with 'time_days' key.
    
    Returns:
        Estimated dt in days, or 0.1 if unable to determine.
    """
    if not dynamic_results:
        return 0.1
    
    times = sorted(set(float(r.get("time_days", 0)) for r in dynamic_results if "time_days" in r))
    if len(times) < 2:
        return 0.1
    
    # Find smallest non-zero time difference
    diffs = [times[i+1] - times[i] for i in range(len(times)-1) if times[i+1] > times[i]]
    if diffs:
        return min(diffs)
    return 0.1


def _requested_dynamic_metrics(dynamic_profile: dict[str, object]) -> list[dict[str, str]]:
    """Extract sorted lists of input and output species from results.
    
    Scans plant_profiles in the dynamic_profile to detect which metrics were explicitly
    configured: flow rate, temperature, and inlet species concentrations.
    
    Args:
        dynamic_profile: Dynamic profile dict with 'plant_profiles' key.
    
    Returns:
        List of metric dicts, each with 'name', 'merge_col', 'plant_col', 'storage_col', 'y_label'.
    """
    plant_profiles = dynamic_profile.get("plant_profiles", {})
    if not isinstance(plant_profiles, dict):
        return []

    want_flow = False
    want_temperature = False
    inlet_species: set[str] = set()

    for plant_profile in plant_profiles.values():
        if not isinstance(plant_profile, dict):
            continue

        if plant_profile.get("flowrate"):
            want_flow = True

        if plant_profile.get("temperature_celsius"):
            want_temperature = True

        inlet_profile = plant_profile.get("inlet_conc", {})
        if isinstance(inlet_profile, dict):
            for species, points in inlet_profile.items():
                if points:
                    inlet_species.add(str(species).strip().upper())

    metrics: list[dict[str, str]] = []
    if want_flow:
        metrics.append(
            {
                "name": "Flow",
                "merge_col": "flow_kg_per_h",
                "plant_col": "flow_kg_per_h",
                "storage_col": "flow_kg_per_h",
                "y_label": "Flow (kg/h)",
            }
        )
    if want_temperature:
        metrics.append(
            {
                "name": "Temperature",
                "merge_col": "temperature_celsius",
                "plant_col": "temperature_celsius",
                "storage_col": "temperature_celsius",
                "y_label": "Temperature (C)",
            }
        )

    for species_name in sorted(inlet_species):
        metrics.append(
            {
                "name": species_name,
                "merge_col": f"final_{species_name}",
                "plant_col": f"inlet_{species_name}",
                "storage_col": f"final_{species_name}",
                "y_label": f"{species_name} concentration",
            }
        )

    return metrics


def _dashboard_figsize(metric_count: int) -> tuple[float, float]:
    """Scale the dashboard figure size to the number of metric columns.
    
    Args:
        metric_count: Number of metrics (species/properties) to plot.
    
    Returns:
        Tuple (width_inches, height_inches) for matplotlib figure.
    """
    safe_count = max(1, metric_count)
    panel_width = 15
    panel_height = 3.9
    return panel_width * safe_count, panel_height * 3


def _compact_change_table(
    table: pd.DataFrame,
    group_col: str,
    tracked_cols: list[str],
    numeric_cols: list[str],
) -> pd.DataFrame:
    """Keep first row per group and rows where values changed.
    
    Implements change-point detection: for each group, includes the first row and any
    row where a tracked column value differs from the previous row (within tolerance).
    
    Args:
        table: Input DataFrame to compact.
        group_col: Column name defining groups (e.g., 'merge_name', 'plant_name').
        tracked_cols: Column names to monitor for changes.
        numeric_cols: Which of tracked_cols are numeric (for tolerance comparison).
    
    Returns:
        Compacted DataFrame with only first and change-point rows per group.
    """
    compact_rows: list[pd.Series] = []
    for _group_name, group_table in table.groupby(group_col, sort=False):
        group_table = group_table.sort_values("time_days")
        previous_row: pd.Series | None = None
        for _, current_row in group_table.iterrows():
            if previous_row is None:
                compact_rows.append(current_row)
                previous_row = current_row
                continue

            changed = False
            for col in tracked_cols:
                if col not in group_table.columns:
                    continue
                current_value = current_row[col]
                previous_value = previous_row[col]
                if col in numeric_cols:
                    if current_value is None and previous_value is None:
                        continue
                    if current_value is None or previous_value is None:
                        changed = True
                        break
                    if abs(float(current_value) - float(previous_value)) > 1e-9:
                        changed = True
                        break
                elif str(current_value) != str(previous_value):
                    changed = True
                    break

            if changed:
                compact_rows.append(current_row)
                previous_row = current_row

    return pd.DataFrame(compact_rows)


def _round_numeric_columns(
    table: pd.DataFrame,
    numeric_cols: list[str],
    digits: int = 4,
) -> pd.DataFrame:
    """Return a copy with selected numeric columns rounded.
    
    Args:
        table: Input DataFrame.
        numeric_cols: List of column names to round.
        digits: Number of decimal places to round to (default 4).
    
    Returns:
        Copy of table with specified columns rounded.
    """
    rounded = table.copy()
    for col in numeric_cols:
        if col in rounded.columns:
            rounded[col] = pd.to_numeric(rounded[col], errors="coerce").round(digits)
    return rounded


def _print_dynamic_merge_table(dynamic_results: list[dict[str, Any]]) -> None:
    """Print compact merge rows in per-merge blocks showing change points.
    
    Args:
        dynamic_results: List of merge result dicts from run_dynamic_merges().
    """
    flattened_rows: list[dict[str, Any]] = []
    for result in dynamic_results:
        row = {
            "time_days": result["time_days"],
            "merge_name": result["merge_name"],
            "sources": result.get("sources", ""),
            "temperature_celsius": result.get("temperature_celsius"),
            "flow_kg_per_h": result["flow_kg_per_h"],
            "stream_phase": result["stream_phase"],
            "density_kg_per_m3": result["density_kg_per_m3"],
            "pipe_time_days": result.get("pipe_time_days"),
            "pipe_length_m": result.get("pipe_length_m"),
            "pipe_diameter_m": result.get("pipe_diameter_m"),
        }
        for species, value in result.get("final", {}).items():
            row[f"final_{species}"] = value
        flattened_rows.append(row)

    merge_table = pd.DataFrame(flattened_rows)
    merge_compact_table = _compact_change_table(
        merge_table,
        group_col="merge_name",
        tracked_cols=[
            "temperature_celsius",
            "flow_kg_per_h",
            "stream_phase",
            "density_kg_per_m3",
            "pipe_time_days",
            "pipe_length_m",
            "pipe_diameter_m",
            "final_H2O",
            "final_SO2",
            "final_NO2",
            "final_H2S",
            "final_NO",
        ],
        numeric_cols=[
            "temperature_celsius",
            "flow_kg_per_h",
            "density_kg_per_m3",
            "pipe_time_days",
            "pipe_length_m",
            "pipe_diameter_m",
            "final_H2O",
            "final_SO2",
            "final_NO2",
            "final_H2S",
            "final_NO",
        ],
    )

    merge_compact_table = _round_numeric_columns(
        merge_compact_table,
        numeric_cols=[
            "time_days",
            "temperature_celsius",
            "flow_kg_per_h",
            "density_kg_per_m3",
            "pipe_time_days",
            "pipe_length_m",
            "pipe_diameter_m",
            "final_H2O",
            "final_SO2",
            "final_NO2",
            "final_H2S",
            "final_NO",
        ],
    )

    print("Merge change points (grouped):")
    for merge_name, merge_group in merge_compact_table.groupby("merge_name", sort=False):
        merge_group = merge_group.sort_values("time_days")
        first_row = merge_group.iloc[0]
        print()
        print(f"{merge_name}")

        table_cols = [
            "pipe_time_days",
        ]
        table_cols = [col for col in table_cols if col in merge_group.columns]
        print(merge_group[table_cols].to_string(index=False))


def _print_dynamic_plant_table(plant_results: list[dict[str, Any]]) -> None:
    """Print compact plant rows in per-plant blocks showing change points.
    
    Args:
        plant_results: List of plant state dicts collected during simulation.
    """
    if not plant_results:
        return

    plant_table = pd.DataFrame(plant_results)
    plant_compact_table = _compact_change_table(
        plant_table,
        group_col="plant_name",
        tracked_cols=[
            "temperature_celsius",
            "flow_kg_per_h",
            "stream_phase",
            "density_kg_per_m3",
            "pipe_time_days",
            "pipe_length_m",
            "pipe_diameter_m",
            "inlet_O2",
            "inlet_H2O",
            "inlet_SO2",
            "inlet_NO2",
            "inlet_NO",
            "inlet_SO3",
            "inlet_H2S",
        ],
        numeric_cols=[
            "temperature_celsius",
            "flow_kg_per_h",
            "density_kg_per_m3",
            "pipe_time_days",
            "pipe_length_m",
            "pipe_diameter_m",
            "inlet_O2",
            "inlet_H2O",
            "inlet_SO2",
            "inlet_NO2",
            "inlet_NO",
            "inlet_SO3",
            "inlet_H2S",
        ],
    )

    plant_compact_table = _round_numeric_columns(
        plant_compact_table,
        numeric_cols=[
            "time_days",
            "temperature_celsius",
            "flow_kg_per_h",
            "density_kg_per_m3",
            "pipe_time_days",
            "pipe_length_m",
            "pipe_diameter_m",
            "inlet_O2",
            "inlet_H2O",
            "inlet_SO2",
            "inlet_NO2",
            "inlet_NO",
            "inlet_SO3",
            "inlet_H2S",
        ],
    )

    print()
    print("Plant change points (grouped):")
    for plant_name, plant_group in plant_compact_table.groupby("plant_name", sort=False):
        plant_group = plant_group.sort_values("time_days")
        first_row = plant_group.iloc[0]
        print()
        print(f"{plant_name}")

        table_cols = [
            "time_days",
            "temperature_celsius",
            "flow_kg_per_h",
            "pipe_time_days",
            "inlet_O2",
            "inlet_H2O",
            "inlet_SO2",
            "inlet_NO2",
            "inlet_NO",
            "inlet_SO3",
            "inlet_H2S",
        ]
        table_cols = [col for col in table_cols if col in plant_group.columns]
        print(plant_group[table_cols].to_string(index=False))


def _format_change_annotation(previous: float, new: float, time_days: float) -> str:
    """Format change-point text with timestamp only."""
    return f"t={time_days:.2f} d"


def _plot_group_step_series(
    ax: Any,
    table: pd.DataFrame,
    group_col: str,
    value_col: str,
    colors: list[str],
    legend_title: str,
    x_end: float,
) -> set[float]:
    """Plot grouped step series with markers and annotations on real change points only."""
    if value_col not in table.columns or table.empty:
        return set()

    all_change_times: set[float] = set()
    for idx, (group_name, group_table) in enumerate(table.groupby(group_col, sort=False)):
        group_table = group_table.sort_values("time_days")
        x = pd.to_numeric(group_table["time_days"], errors="coerce")
        y = pd.to_numeric(group_table[value_col], errors="coerce")
        if y.isna().all() or x.isna().all():
            continue

        color = colors[idx % len(colors)]

        x_plot = x
        y_plot = y

        # Extend the last plateau to the plot boundary so the line does not
        # visually stop at the final data point.
        if float(x.iloc[-1]) < x_end:
            x_plot = pd.concat([x_plot, pd.Series([x_end])], ignore_index=True)
            y_plot = pd.concat([y_plot, pd.Series([float(y.iloc[-1])])], ignore_index=True)

        # With a single timestamp, step() has no visible horizontal segment,
        # so the extension above creates that visible run-out.

        ax.step(
            x_plot,
            y_plot,
            where="post",
            linewidth=2.4,
            color=color,
            label=str(group_name),
            zorder=2,
        )

        change_indices: list[int] = []
        for i in range(1, len(y)):
            prev = y.iloc[i - 1]
            new = y.iloc[i]
            if pd.isna(prev) or pd.isna(new):
                continue
            if abs(float(new) - float(prev)) > 1e-9:
                change_indices.append(i)

        if not change_indices:
            continue

        x_changes = x.iloc[change_indices]
        y_changes = y.iloc[change_indices]
        ax.scatter(
            x_changes,
            y_changes,
            s=34,
            color=color,
            edgecolor="white",
            linewidth=0.7,
            zorder=4,
        )

        for ann_idx, i in enumerate(change_indices):
            prev_value = float(y.iloc[i - 1])
            new_value = float(y.iloc[i])
            change_time = float(x.iloc[i])
            all_change_times.add(change_time)
            y_offset = 10 if ann_idx % 2 == 0 else -14
            ax.annotate(
                _format_change_annotation(prev_value, new_value, change_time),
                xy=(change_time, new_value),
                xytext=(6, y_offset),
                textcoords="offset points",
                fontsize=9,
                color=color,
                bbox={
                    "boxstyle": "round,pad=0.2",
                    "facecolor": "white",
                    "edgecolor": color,
                    "linewidth": 0.6,
                    "alpha": 0.9,
                },
                zorder=5,
            )

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(
            handles,
            labels,
            title=legend_title,
            title_fontsize=12,
            fontsize=10,
            frameon=False,
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
        )

    return all_change_times


def _build_storage_receipt_table(dynamic_results: list[dict[str, Any]], dt_days: float = 0.1) -> pd.DataFrame:
    """Build storage receipt rows from terminal merges with arrival-time snapped to next dt step."""
    merge_table = pd.DataFrame(dynamic_results)
    if merge_table.empty:
        return pd.DataFrame()

    merge_names = set(merge_table["merge_name"].astype(str).unique())
    downstream_merge_sources: set[str] = set()

    for sources_text in merge_table.get("sources", pd.Series([], dtype=object)).dropna().astype(str):
        for token in (part.strip() for part in sources_text.split(",")):
            if token in merge_names:
                downstream_merge_sources.add(token)

    terminal_merges = sorted(merge_names - downstream_merge_sources)
    if not terminal_merges:
        return pd.DataFrame()

    terminal_rows = merge_table[merge_table["merge_name"].astype(str).isin(terminal_merges)].copy()
    terminal_rows["pipe_time_days"] = pd.to_numeric(
        terminal_rows.get("pipe_time_days"),
        errors="coerce",
    ).fillna(0.0)
    terminal_rows["acoustic_pipe_time_days"] = pd.to_numeric(
        terminal_rows.get("acoustic_pipe_time_days"),
        errors="coerce",
    ).fillna(0.0)

    # Flowrate is assumed to propagate instantaneously.
    raw_arrival_time = (
        pd.to_numeric(terminal_rows["time_days"], errors="coerce")
        + terminal_rows["acoustic_pipe_time_days"]
    )
    terminal_rows["time_days"] = raw_arrival_time.apply(
        lambda t: math.ceil(t / dt_days) * dt_days if dt_days > 0 else t
    )
    terminal_rows["storage_stream"] = terminal_rows["merge_name"].astype(str) + " -> Storage"

    return terminal_rows[["time_days", "storage_stream", "flow_kg_per_h"]]


def _ensure_merge_metric_column(merge_table: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Ensure a metric column exists, deriving final_* values from nested TOCOMO output."""
    resolved = merge_table.copy()
    if value_col in resolved.columns:
        return resolved

    if value_col.startswith("final_") and "final" in resolved.columns:
        species = value_col[len("final_"):]
        resolved[value_col] = resolved["final"].apply(
            lambda payload: (
                payload.get(species)
                if isinstance(payload, dict) and species in payload
                else payload.get(str(species).upper())
                if isinstance(payload, dict)
                else None
            )
        )

    return resolved


def _build_storage_receipt_table_for_column(
    dynamic_results: list[dict[str, Any]],
    value_col: str,
    dt_days: float = 0.1,
) -> pd.DataFrame:
    """Build storage receipt rows for a selected merge output column, snapped to next dt step."""
    merge_table = _ensure_merge_metric_column(pd.DataFrame(dynamic_results), value_col)
    if merge_table.empty or value_col not in merge_table.columns:
        return pd.DataFrame()

    merge_names = set(merge_table["merge_name"].astype(str).unique())
    downstream_merge_sources: set[str] = set()

    for sources_text in merge_table.get("sources", pd.Series([], dtype=object)).dropna().astype(str):
        for token in (part.strip() for part in sources_text.split(",")):
            if token in merge_names:
                downstream_merge_sources.add(token)

    terminal_merges = sorted(merge_names - downstream_merge_sources)
    if not terminal_merges:
        return pd.DataFrame()

    terminal_rows = merge_table[merge_table["merge_name"].astype(str).isin(terminal_merges)].copy()
    terminal_rows["pipe_time_days"] = pd.to_numeric(
        terminal_rows.get("pipe_time_days"),
        errors="coerce",
    ).fillna(0.0)
    terminal_rows["acoustic_pipe_time_days"] = pd.to_numeric(
        terminal_rows.get("acoustic_pipe_time_days"),
        errors="coerce",
    ).fillna(0.0)

    # Flowrate changes are instantaneous; species concentrations follow fluid residence time.
    delay_days_col = "acoustic_pipe_time_days" if value_col == "flow_kg_per_h" else "pipe_time_days"
    raw_arrival_time = (
        pd.to_numeric(terminal_rows["time_days"], errors="coerce")
        + terminal_rows[delay_days_col]
    )
    terminal_rows["time_days"] = raw_arrival_time.apply(
        lambda t: math.ceil(t / dt_days) * dt_days if dt_days > 0 else t
    )
    terminal_rows["storage_stream"] = terminal_rows["merge_name"].astype(str) + " -> Storage"
    terminal_rows["metric_value"] = pd.to_numeric(terminal_rows[value_col], errors="coerce")

    return terminal_rows[["time_days", "storage_stream", "metric_value"]]


def _plot_metric_dashboard(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    merge_value_col: str,
    plant_value_col: str,
    storage_value_col: str,
    output_path: str,
    title: str,
    subtitle: str,
    y_label: str,
) -> None:
    """Plot merge, plant, and storage dashboards for a selected metric."""
    if not dynamic_results:
        return

    merge_table = _ensure_merge_metric_column(pd.DataFrame(dynamic_results), merge_value_col)
    if merge_value_col not in merge_table.columns:
        print(f"Skipping dashboard '{title}': missing column {merge_value_col}")
        return

    merge_metric = merge_table[["time_days", "merge_name", merge_value_col]].rename(
        columns={merge_value_col: "metric_value"}
    )
    merge_compact = _compact_change_table(
        merge_metric,
        group_col="merge_name",
        tracked_cols=["metric_value"],
        numeric_cols=["metric_value"],
    )

    plant_compact = pd.DataFrame()
    if plant_results:
        plant_table = pd.DataFrame(plant_results)
        if plant_value_col in plant_table.columns:
            plant_metric = plant_table[["time_days", "plant_name", plant_value_col]].rename(
                columns={plant_value_col: "metric_value"}
            )
            plant_compact = _compact_change_table(
                plant_metric,
                group_col="plant_name",
                tracked_cols=["metric_value"],
                numeric_cols=["metric_value"],
            )

    storage_table = _build_storage_receipt_table_for_column(
        dynamic_results, storage_value_col, dt_days=_infer_dt_days(dynamic_results)
    )
    storage_compact = pd.DataFrame()
    if not storage_table.empty:
        storage_compact = _compact_change_table(
            storage_table,
            group_col="storage_stream",
            tracked_cols=["metric_value"],
            numeric_cols=["metric_value"],
        )

    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )
    fig, axes = plt.subplots(3, 1, figsize=(40, 13), sharex=True)
    fig.patch.set_facecolor("white")

    max_time = float(pd.to_numeric(merge_metric["time_days"], errors="coerce").max())
    if not plant_compact.empty:
        max_plant_time = float(pd.to_numeric(plant_compact["time_days"], errors="coerce").max())
        max_time = max(max_time, max_plant_time)
    if not storage_table.empty:
        max_storage_time = float(pd.to_numeric(storage_table["time_days"], errors="coerce").max())
        max_time = max(max_time, max_storage_time)
    x_end = max(1.0, max_time)

    merge_ax = axes[0]
    plant_ax = axes[1]
    storage_ax = axes[2]
    for axis in axes:
        axis.set_facecolor("white")
        axis.grid(True, linestyle="-", linewidth=0.8, color="#d9d9d9", alpha=0.8)
        axis.set_axisbelow(True)
        for spine in axis.spines.values():
            spine.set_color("#4d4d4d")
            spine.set_linewidth(0.8)

    merge_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#17becf"]
    plant_colors = ["#6a3d9a", "#d62728", "#8c564b", "#7f7f7f"]
    storage_colors = ["#0b7285", "#1098ad", "#0ca678"]

    merge_change_times = _plot_group_step_series(
        merge_ax,
        merge_compact,
        "merge_name",
        "metric_value",
        colors=merge_colors,
        legend_title="MERGES",
        x_end=x_end,
    )

    plant_change_times: set[float] = set()
    if not plant_compact.empty:
        plant_change_times = _plot_group_step_series(
            plant_ax,
            plant_compact,
            "plant_name",
            "metric_value",
            colors=plant_colors,
            legend_title="PLANTS",
            x_end=x_end,
        )
    else:
        plant_ax.text(
            0.5,
            0.5,
            "No plant concentration rows to plot",
            ha="center",
            va="center",
            fontsize=11,
        )

    storage_change_times: set[float] = set()
    if not storage_compact.empty:
        storage_change_times = _plot_group_step_series(
            storage_ax,
            storage_compact,
            "storage_stream",
            "metric_value",
            colors=storage_colors,
            legend_title="STORAGE",
            x_end=x_end,
        )
    else:
        storage_ax.text(
            0.5,
            0.5,
            "No storage concentration rows to plot",
            ha="center",
            va="center",
            fontsize=11,
        )

    all_change_times = sorted(merge_change_times.union(plant_change_times).union(storage_change_times))
    for change_time in all_change_times:
        merge_ax.axvline(change_time, color="#9b9b9b", linestyle=":", linewidth=1.0, alpha=0.45)
        plant_ax.axvline(change_time, color="#9b9b9b", linestyle=":", linewidth=1.0, alpha=0.45)
        storage_ax.axvline(change_time, color="#9b9b9b", linestyle=":", linewidth=1.0, alpha=0.45)

    merge_ax.set_title("Merge Concentrations", fontweight="bold")
    merge_ax.set_ylabel(y_label)

    plant_ax.set_title("Plant Concentrations", fontweight="bold")
    plant_ax.set_ylabel(y_label)

    storage_ax.set_title("Storage Receipt Concentrations", fontweight="bold")
    storage_ax.set_ylabel(y_label)
    storage_ax.set_xlabel("Time (days)")
    storage_ax.set_xlim(0.0, x_end)

    fig.suptitle(title, fontsize=18, fontweight="bold", y=0.985)
    fig.text(
        0.5,
        0.955,
        subtitle,
        ha="center",
        va="center",
        fontsize=12,
        color="#4d4d4d",
    )
    fig.tight_layout(rect=(0.04, 0.05, 0.80, 0.92))

    output = Path(output_path)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print()
    print(f"Saved dynamic graph: {output.resolve()}")


def _build_metric_compact_tables(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    merge_value_col: str,
    plant_value_col: str,
    storage_value_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    """Prepare compact merge/plant/storage tables for one metric."""
    merge_table = _ensure_merge_metric_column(pd.DataFrame(dynamic_results), merge_value_col)
    if merge_table.empty or merge_value_col not in merge_table.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 1.0

    merge_metric = merge_table[["time_days", "merge_name", merge_value_col]].rename(
        columns={merge_value_col: "metric_value"}
    )
    merge_compact = _compact_change_table(
        merge_metric,
        group_col="merge_name",
        tracked_cols=["metric_value"],
        numeric_cols=["metric_value"],
    )

    plant_compact = pd.DataFrame()
    if plant_results:
        plant_table = pd.DataFrame(plant_results)
        if plant_value_col in plant_table.columns:
            plant_metric = plant_table[["time_days", "plant_name", plant_value_col]].rename(
                columns={plant_value_col: "metric_value"}
            )
            plant_compact = _compact_change_table(
                plant_metric,
                group_col="plant_name",
                tracked_cols=["metric_value"],
                numeric_cols=["metric_value"],
            )

    storage_table = _build_storage_receipt_table_for_column(
        dynamic_results, storage_value_col, dt_days=_infer_dt_days(dynamic_results)
    )
    storage_compact = pd.DataFrame()
    if not storage_table.empty:
        storage_compact = _compact_change_table(
            storage_table.rename(columns={"flow_kg_per_h": "metric_value"}),
            group_col="storage_stream",
            tracked_cols=["metric_value"],
            numeric_cols=["metric_value"],
        )

    max_time = float(pd.to_numeric(merge_metric["time_days"], errors="coerce").max())
    if not plant_compact.empty:
        max_plant_time = float(pd.to_numeric(plant_compact["time_days"], errors="coerce").max())
        max_time = max(max_time, max_plant_time)
    if not storage_table.empty:
        max_storage_time = float(pd.to_numeric(storage_table["time_days"], errors="coerce").max())
        max_time = max(max_time, max_storage_time)

    return merge_compact, plant_compact, storage_compact, max(1.0, max_time)


def _infer_all_metrics(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Infer all plottable metrics from actual simulation data.
    
    Produces metrics for flowrate plus every contaminant species found in the results,
    regardless of what was explicitly configured in the dynamic profile.
    
    Returns:
        List of metric dicts with 'name', 'merge_col', 'plant_col', 'storage_col', 'y_label'.
    """
    metrics: list[dict[str, str]] = []

    # Always include flow rate
    metrics.append(
        {
            "name": "Flow",
            "merge_col": "flow_kg_per_h",
            "plant_col": "flow_kg_per_h",
            "storage_col": "flow_kg_per_h",
            "y_label": "Flow (kg/h)",
        }
    )

    # Collect all output species from "final" dicts in merge results
    output_species: set[str] = set()
    for result in dynamic_results:
        final_dict = result.get("final", {})
        if isinstance(final_dict, dict):
            output_species.update(final_dict.keys())

    # Collect all inlet species from plant results
    inlet_species: set[str] = set()
    for result in plant_results:
        for key in result.keys():
            if key.startswith("inlet_"):
                inlet_species.add(key[len("inlet_"):])

    # Build one metric per species (union of output and inlet species)
    all_species = sorted({str(species).upper() for species in output_species | inlet_species})
    for species in all_species:
        metrics.append(
            {
                "name": species,
                "merge_col": f"final_{species}",
                "plant_col": f"inlet_{species}",
                "storage_col": f"final_{species}",
                "y_label": f"{species} (ppm)",
            }
        )

    return metrics


def _metric_has_changes(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    metric: dict[str, str],
) -> bool:
    """Return True if a metric has at least one value change across all results."""
    merge_col = metric["merge_col"]
    plant_col = metric["plant_col"]

    # Check merge results
    merge_values = []
    for r in dynamic_results:
        if merge_col == "flow_kg_per_h":
            v = r.get("flow_kg_per_h")
        elif merge_col.startswith("final_"):
            final = r.get("final", {})
            species = merge_col[len("final_"):]
            v = final.get(species) if isinstance(final, dict) else None
        else:
            v = r.get(merge_col)
        if v is not None:
            merge_values.append(float(v))

    if len(set(merge_values)) > 1:
        return True

    # Check plant results
    plant_values = []
    for r in plant_results:
        v = r.get(plant_col)
        if v is not None:
            plant_values.append(float(v))

    return len(set(plant_values)) > 1


def plot_all_dynamic_dashboards(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    dynamic_profile: dict[str, object],
    output_path: str = "dynamic_change_points.png",
) -> None:
    """Save one dashboard PNG per metric (flowrate + every contaminant species)."""
    if not dynamic_results:
        return

    metrics = _infer_all_metrics(dynamic_results, plant_results)
    # Only plot metrics where values actually change during the simulation
    metrics = [m for m in metrics if _metric_has_changes(dynamic_results, plant_results, m)]
    if not metrics:
        print("No metrics found in simulation results; skipping graphs.")
        return

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )

    merge_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#17becf"]
    plant_colors = ["#6a3d9a", "#d62728", "#8c564b", "#7f7f7f"]
    storage_colors = ["#0b7285", "#1098ad", "#0ca678"]

    output_base = Path(output_path)
    graph_dir = output_base.parent / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for metric in metrics:
        merge_compact, plant_compact, storage_compact, x_end = _build_metric_compact_tables(
            dynamic_results,
            plant_results,
            merge_value_col=metric["merge_col"],
            plant_value_col=metric["plant_col"],
            storage_value_col=metric["storage_col"],
        )

        fig, axes = plt.subplots(3, 1, figsize=(15, 11.7), sharex=True)
        fig.patch.set_facecolor("white")

        plant_ax, merge_ax, storage_ax = axes

        for axis in (merge_ax, plant_ax, storage_ax):
            axis.set_facecolor("white")
            axis.grid(True, linestyle="-", linewidth=0.8, color="#d9d9d9", alpha=0.8)
            axis.set_axisbelow(True)
            for spine in axis.spines.values():
                spine.set_color("#4d4d4d")
                spine.set_linewidth(0.8)

        plant_change_times: set[float] = set()
        if not plant_compact.empty:
            plant_change_times = _plot_group_step_series(
                plant_ax, plant_compact, "plant_name", "metric_value",
                colors=plant_colors, legend_title="PLANTS", x_end=x_end,
            )
        else:
            plant_ax.text(0.5, 0.5, "No plant rows", ha="center", va="center", fontsize=10)

        merge_change_times: set[float] = set()
        if not merge_compact.empty:
            merge_change_times = _plot_group_step_series(
                merge_ax, merge_compact, "merge_name", "metric_value",
                colors=merge_colors, legend_title="MERGES", x_end=x_end,
            )
        else:
            merge_ax.text(0.5, 0.5, "No merge rows", ha="center", va="center", fontsize=10)

        storage_change_times: set[float] = set()
        if not storage_compact.empty:
            storage_change_times = _plot_group_step_series(
                storage_ax, storage_compact, "storage_stream", "metric_value",
                colors=storage_colors, legend_title="STORAGE", x_end=x_end,
            )
        else:
            storage_ax.text(0.5, 0.5, "No storage rows", ha="center", va="center", fontsize=10)

        all_change_times = sorted(merge_change_times | plant_change_times | storage_change_times)
        for change_time in all_change_times:
            for ax in (plant_ax, merge_ax, storage_ax):
                ax.axvline(change_time, color="#9b9b9b", linestyle=":", linewidth=1.0, alpha=0.45)

        plant_ax.set_title(f"Plant {metric['name']}", fontweight="bold")
        plant_ax.set_ylabel(metric["y_label"])
        merge_ax.set_title(f"Merge {metric['name']}", fontweight="bold")
        merge_ax.set_ylabel(metric["y_label"])
        storage_ax.set_title(f"Storage {metric['name']}", fontweight="bold")
        storage_ax.set_ylabel(metric["y_label"])
        storage_ax.set_xlabel("Time (days)")
        storage_ax.set_xlim(0.0, x_end)

        fig.suptitle(f"Dynamic Changes — {metric['name']}", fontsize=16, fontweight="bold", y=0.99)
        fig.tight_layout(rect=(0.03, 0.02, 0.85, 0.97))

        # Save as separate file per metric in graphs/ subfolder
        metric_suffix = metric["name"].lower().replace(" ", "_")
        metric_path = graph_dir / f"{metric_suffix}graph.png"
        fig.savefig(metric_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        saved_paths.append(metric_path)

    print(f"Saved {len(saved_paths)} graph(s) to: {graph_dir}")


def plot_dynamic_change_graphs(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    output_path: str = "dynamic_change_points.png",
) -> None:
    """Create a publication-style engineering dashboard for flow change points."""
    if not dynamic_results:
        return

    merge_table = pd.DataFrame(dynamic_results)
    merge_compact = _compact_change_table(
        merge_table,
        group_col="merge_name",
        tracked_cols=["flow_kg_per_h"],
        numeric_cols=["flow_kg_per_h"],
    )

    plant_compact = pd.DataFrame()
    if plant_results:
        plant_table = pd.DataFrame(plant_results)
        plant_compact = _compact_change_table(
            plant_table,
            group_col="plant_name",
            tracked_cols=["flow_kg_per_h"],
            numeric_cols=["flow_kg_per_h"],
        )

    storage_table = _build_storage_receipt_table(
        dynamic_results, dt_days=_infer_dt_days(dynamic_results)
    )
    storage_compact = pd.DataFrame()
    if not storage_table.empty:
        storage_compact = _compact_change_table(
            storage_table,
            group_col="storage_stream",
            tracked_cols=["flow_kg_per_h"],
            numeric_cols=["flow_kg_per_h"],
        )

    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )
    fig, axes = plt.subplots(3, 1, figsize=(40, 13), sharex=True)
    fig.patch.set_facecolor("white")

    max_time = float(pd.to_numeric(merge_table["time_days"], errors="coerce").max())
    if plant_results:
        max_plant_time = float(pd.to_numeric(pd.DataFrame(plant_results)["time_days"], errors="coerce").max())
        max_time = max(max_time, max_plant_time)
    if not storage_table.empty:
        max_storage_time = float(pd.to_numeric(storage_table["time_days"], errors="coerce").max())
        max_time = max(max_time, max_storage_time)
    x_end = max(1.0, max_time)

    plant_ax = axes[0]
    merge_ax = axes[1]
    storage_ax = axes[2]
    for axis in axes:
        axis.set_facecolor("white")
        axis.grid(True, linestyle="-", linewidth=0.8, color="#d9d9d9", alpha=0.8)
        axis.set_axisbelow(True)
        for spine in axis.spines.values():
            spine.set_color("#4d4d4d")
            spine.set_linewidth(0.8)

    merge_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#17becf"]
    plant_colors = ["#6a3d9a", "#d62728", "#8c564b", "#7f7f7f"]
    storage_colors = ["#0b7285", "#1098ad", "#0ca678"]

    plant_change_times: set[float] = set()
    if not plant_compact.empty:
        plant_change_times = _plot_group_step_series(
            plant_ax,
            plant_compact,
            "plant_name",
            "flow_kg_per_h",
            colors=plant_colors,
            legend_title="PLANTS",
            x_end=x_end,
        )
    else:
        plant_ax.text(
            0.5,
            0.5,
            "No plant flow rows to plot",
            ha="center",
            va="center",
            fontsize=11,
        )

    merge_change_times = _plot_group_step_series(
        merge_ax,
        merge_compact,
        "merge_name",
        "flow_kg_per_h",
        colors=merge_colors,
        legend_title="MERGES",
        x_end=x_end,
    )

    storage_change_times: set[float] = set()
    if not storage_compact.empty:
        storage_change_times = _plot_group_step_series(
            storage_ax,
            storage_compact,
            "storage_stream",
            "flow_kg_per_h",
            colors=storage_colors,
            legend_title="STORAGE",
            x_end=x_end,
        )
    else:
        storage_ax.text(
            0.5,
            0.5,
            "No storage receipt rows to plot",
            ha="center",
            va="center",
            fontsize=11,
        )

    all_change_times = sorted(merge_change_times.union(plant_change_times).union(storage_change_times))
    for change_time in all_change_times:
        merge_ax.axvline(
            change_time,
            color="#9b9b9b",
            linestyle=":",
            linewidth=1.0,
            alpha=0.45,
        )
        plant_ax.axvline(
            change_time,
            color="#9b9b9b",
            linestyle=":",
            linewidth=1.0,
            alpha=0.45,
        )
        storage_ax.axvline(
            change_time,
            color="#9b9b9b",
            linestyle=":",
            linewidth=1.0,
            alpha=0.45,
        )

    plant_ax.set_title("Plant Flows", fontweight="bold")
    plant_ax.set_ylabel("Flow (kg/h)")

    merge_ax.set_title("Merge Flows", fontweight="bold")
    merge_ax.set_ylabel("Flow (kg/h)")

    storage_ax.set_title("Storage Receipt Flows", fontweight="bold")
    storage_ax.set_ylabel("Flow (kg/h)")
    storage_ax.set_xlabel("Time (days)")
    storage_ax.set_xlim(0.0, x_end)

    fig.suptitle("Flow Capacity Changes Over Time", fontsize=18, fontweight="bold", y=0.985)
    fig.text(
        0.5,
        0.955,
        "Plant and Merge Network Change Points",
        ha="center",
        va="center",
        fontsize=12,
        color="#4d4d4d",
    )
    fig.tight_layout(rect=(0.04, 0.05, 0.80, 0.92))

    output = Path(output_path)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print()
    print(f"Saved dynamic change graph: {output.resolve()}")


def render_dynamic_reports(
    dynamic_results: list[dict[str, Any]],
    plant_results: list[dict[str, Any]],
    dynamic_profile: dict[str, object],
    graph_output_path: str = "dynamic_change_points.png",
) -> None:
    """Save dashboard graph."""
    plot_all_dynamic_dashboards(
        dynamic_results,
        plant_results,
        dynamic_profile=dynamic_profile,
        output_path=graph_output_path,
    )
