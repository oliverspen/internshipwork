"""Generate per-node phase envelope plots for pipeline networks."""

from __future__ import annotations

from pathlib import Path
import os
import re
from typing import Any

import matplotlib

if not os.environ.get("DISPLAY"):
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from neqsim import jneqsim
system_cls = jneqsim.thermo.system.SystemSrkEos
operations_cls = jneqsim.thermodynamicoperations.ThermodynamicOperations


def _finite_curve_pairs(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pair_mask = np.isfinite(x) & np.isfinite(y)
    x_pair = x[pair_mask]
    y_pair = y[pair_mask]
    if x_pair.size > 1 and y_pair.size > 1:
        return x_pair, y_pair

    # Some NeqSim outputs contain finite X and Y values at different indices.
    # If pairwise filtering collapses to <=1 point, salvage by pairing finite
    # sequences positionally up to their common length.
    x_finite = x[np.isfinite(x)]
    y_finite = y[np.isfinite(y)]
    n = min(x_finite.size, y_finite.size)
    if n <= 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    return x_finite[:n], y_finite[:n]


def _to_mole_fractions(source_state: dict[str, Any]) -> dict[str, float]:
    raw_conc = source_state["initial_merge_conc"]

    total = sum(max(float(value), 0.0) for value in raw_conc.values())
    return {
        str(species): max(float(value), 0.0) / total
        for species, value in raw_conc.items()
    }


def _build_fluid(temperature_kelvin: float, pressure_bara: float, mole_fractions: dict[str, float]):
    fluid = system_cls(temperature_kelvin, pressure_bara)
    for species, fraction in mole_fractions.items():
        if fraction <= 0:
            continue
        try:
            fluid.addComponent(species, float(fraction))
        except Exception:
            # Skip species unknown to neqsim (e.g. complex trace contaminants).
            pass

    fluid.setMixingRule("classic")
    return fluid


def _build_storage_state(
    source_rows: list[tuple[str, str | int, dict[str, Any]]],
    merge_definitions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if merge_definitions:
        upstream_merges: set[str] = set()
        for merge_def in merge_definitions:
            for source_type, source_value in merge_def.get("sources", []):
                if source_type == "merge":
                    upstream_merges.add(str(source_value))

        terminal_states = [
            state for source_type, source_name, state in source_rows
            if source_type == "merge" and str(source_name) not in upstream_merges
        ]
    else:
        terminal_states = [
            state for source_type, _source_name, state in source_rows if source_type == "plant"
        ]

    total_flow = sum(float(state.get("total_massflow") or 0.0) for state in terminal_states)

    all_species: set[str] = set()
    for state in terminal_states:
        all_species.update((state.get("initial_merge_conc") or {}).keys())

    mixed_conc: dict[str, float] = {
        str(species): sum(
            float((state.get("initial_merge_conc") or {}).get(species, 0.0))
            * float(state.get("total_massflow") or 0.0)
            for state in terminal_states
        ) / total_flow
        for species in sorted(all_species)
    }
    mixed_temperature = sum(
        float(state.get("temperature_kelvin") or 0.0) * float(state.get("total_massflow") or 0.0)
        for state in terminal_states
    ) / total_flow
    mixed_density = sum(
        float(state.get("density_kg_per_m3") or 0.0) * float(state.get("total_massflow") or 0.0)
        for state in terminal_states
    ) / total_flow

    return {
        "initial_merge_conc": mixed_conc,
        "temperature_kelvin": mixed_temperature,
        "density_kg_per_m3": mixed_density,
        "total_massflow": total_flow,
        "stream_phase": (
            "liquid"
            if any(state["stream_phase"] == "liquid" for state in terminal_states)
            else "gas"
        ),
    }


def _plot_single_node_phase_envelope(
    source_type: str,
    source_name: str,
    source_state: dict[str, Any],
    pressure_bara: float,
    output_dir: Path,
) -> Path:
    temperature_kelvin = float(source_state.get("temperature_kelvin"))
    operating_temp_c = temperature_kelvin - 273.15

    mole_fractions = _to_mole_fractions(source_state)
    fluid = _build_fluid(temperature_kelvin, pressure_bara, mole_fractions)

    ops = operations_cls(fluid)
    ops.calcPTphaseEnvelope()

    dew_t = np.array(list(ops.get("dewT")), dtype=float) - 273.15
    dew_p = np.array(list(ops.get("dewP")), dtype=float)
    bub_t = np.array(list(ops.get("bubT")), dtype=float) - 273.15
    bub_p = np.array(list(ops.get("bubP")), dtype=float)
    dew_t_plot, dew_p_plot = _finite_curve_pairs(dew_t, dew_p)
    bub_t_plot, bub_p_plot = _finite_curve_pairs(bub_t, bub_p)

    fig, ax = plt.subplots(figsize=(10.8, 7.2), dpi=130)
    fig.patch.set_facecolor("#f7f9fc")
    ax.set_facecolor("#ffffff")

    dew_line, = ax.plot(
        dew_t_plot,
        dew_p_plot,
        color="#136fdb",
        label="Dew Point",
        linewidth=2.6,
        alpha=0.98,
        zorder=3,
        solid_capstyle="round",
        marker="o",
        markeredgewidth=0,
        markersize=2.6,
        markevery=2,
    )
    bubble_line, = ax.plot(
        bub_t_plot,
        bub_p_plot,
        color="#f97316",
        label="Bubble Point",
        linewidth=2.6,
        linestyle="--",
        marker="o",
        markeredgewidth=0,
        markersize=2.8,
        markevery=2,
        zorder=4,
        solid_capstyle="round",
    )
    ax.plot(
        operating_temp_c,
        pressure_bara,
        marker="D",
        color="#b4238a",
        markeredgecolor="white",
        markeredgewidth=0.9,
        markersize=8,
        label="Operating Point",
        zorder=6,
    )

    ax.set_xlabel("Temperature (C)", fontsize=12, color="#1f2937")
    ax.set_ylabel("Pressure (bara)", fontsize=12, color="#1f2937")
    ax.set_title(f"Phase Envelope - {source_type.capitalize()} {source_name}", fontsize=15, weight="bold", color="#111827")
    ax.tick_params(axis="both", colors="#374151", labelsize=10)
    visible_t = np.concatenate([
        dew_t_plot,
        bub_t_plot,
        np.array([operating_temp_c], dtype=float),
    ])
    visible_p = np.concatenate([
        dew_p_plot,
        bub_p_plot,
        np.array([pressure_bara], dtype=float),
    ])

    if visible_t.size > 0:
        x_min = float(np.nanmin(visible_t))
        x_max = float(np.nanmax(visible_t))
        x_span = max(x_max - x_min, 10.0)
        x_pad = 0.08 * x_span
        ax.set_xlim(x_min - x_pad, x_max + x_pad)

    if visible_p.size > 0:
        y_min = float(np.nanmin(visible_p))
        y_max = float(np.nanmax(visible_p))
        y_span = max(y_max - y_min, 2.0)
        y_pad = 0.08 * y_span
        ax.set_ylim(y_min - y_pad, y_max + y_pad)

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#9ca3af")
    ax.spines["bottom"].set_color("#9ca3af")
    ax.grid(True, linestyle=(0, (3, 4)), linewidth=0.8, color="#cbd5e1", alpha=0.95)
    ax.set_axisbelow(True)

    ax.legend(loc="best", frameon=True, facecolor="white", edgecolor="#e5e7eb")

    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_name = re.sub(r"[^0-9A-Za-z_\-æøåÆØÅ]", "", re.sub(r"\s+", "_", str(source_name).strip()))
    output_path = output_dir / f"{normalized_name}_phase_envelope.png"
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


# Species neqsim cannot handle — tested empirically.
_NEQSIM_UNSUPPORTED = frozenset({"NH3", "HCHO", "CH3CHO", "CH3COCH3", "HCOOH", "CH3COOH"})


def generate_phase_envelopes_for_network(
    source_rows: list[tuple[str, str | int, dict[str, Any]]],
    merge_definitions: list[dict[str, Any]],
    storage_name: str,
    pressure_bara: float,
    output_dir: Path,
    plant_names: dict[int, str] | None = None,
) -> list[Path]:
    """Generate per-node phase envelope PNG files for plants, merges, and storage."""
    generated_paths: list[Path] = []

    for source_type, source_name, source_state in source_rows:
        display_name = str(source_name)
        if source_type == "plant" and plant_names is not None:
            try:
                display_name = str(plant_names.get(int(source_name), source_name))
            except (TypeError, ValueError):
                display_name = str(source_name)

        try:
            path = _plot_single_node_phase_envelope(
                source_type=source_type,
                source_name=display_name,
                source_state=source_state,
                pressure_bara=pressure_bara,
                output_dir=output_dir,
            )
            generated_paths.append(path)
        except Exception:
            continue

    storage_state = _build_storage_state(source_rows, merge_definitions)
    if storage_state is not None:
        try:
            storage_path = _plot_single_node_phase_envelope(
                source_type="storage",
                source_name=storage_name,
                source_state=storage_state,
                pressure_bara=pressure_bara,
                output_dir=output_dir,
            )
            generated_paths.append(storage_path)
        except Exception:
            pass

    return generated_paths
