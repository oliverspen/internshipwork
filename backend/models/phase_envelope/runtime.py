"""Runtime helpers to generate phase envelopes from active pipeline config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.merge_support.calculations import _build_plant_source_dict
from backend.merge_support.flow import build_merge_inputs_from_definitions

from .service import _NEQSIM_UNSUPPORTED, generate_phase_envelopes_for_network


def build_source_rows_from_config(
    config: dict[str, Any],
) -> list[tuple[str, str | int, dict[str, Any]]]:
    """Build plant/merge source rows from a runtime config dict."""
    merge_definitions = config.get("merge_definitions") or []
    plant_inputs = config["plant_inputs"]

    plant_indices: set[int] = set(range(len(plant_inputs)))
    if merge_definitions:
        for merge_def in merge_definitions:
            sources = merge_def["sources"]
            for source_type, source_value in sources:
                if source_type == "plant":
                    plant_indices.add(int(source_value))

    source_rows: list[tuple[str, str | int, dict[str, Any]]] = []
    for plant_idx in sorted(plant_indices):
        source_rows.append(("plant", plant_idx, _build_plant_source_dict(plant_idx)))

    if merge_definitions:
        merge_results = build_merge_inputs_from_definitions(merge_definitions)
        for merge_def in merge_definitions:
            merge_name = str(merge_def["merge_name"])
            source_rows.append(("merge", merge_name, merge_results[merge_name]))

    return source_rows


def generate_phase_envelopes_from_config(
    config: dict[str, Any],
    output_dir: Path,
) -> list[Path]:
    """Generate phase envelopes for plant, merge, and storage nodes."""
    found = {
        str(species).upper()
        for plant in config.get("plant_inputs", [])
        for species, val in (plant.get("inlet_conc") or {}).items()
        if str(species).upper() in _NEQSIM_UNSUPPORTED and float(val or 0) > 0
    }
    if found:
        raise ValueError("phase envelopes can not be produced due to neqsim specie limitations")

    pressure_bara = float(config["p_bara"])
    storage_name = str(config["storage_name"])
    merge_definitions = config.get("merge_definitions") or []

    plant_inputs = config["plant_inputs"]
    plant_names: dict[int, str] = {
        idx: str(plant["name"])
        for idx, plant in enumerate(plant_inputs)
    }

    source_rows = build_source_rows_from_config(config)
    return generate_phase_envelopes_for_network(
        source_rows=source_rows,
        merge_definitions=merge_definitions,
        storage_name=storage_name,
        pressure_bara=pressure_bara,
        output_dir=output_dir,
        plant_names=plant_names,
    )
