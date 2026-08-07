"""Shared helper for building the post-model storage row."""

from typing import Any

from backend.merge_support.calculations import _bara_to_pa, _co2_density_kg_per_m3


def _normalized_species_values(values: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for species, raw_value in values.items():
        key = str(species).strip().upper()
        normalized[key] = normalized.get(key, 0.0) + float(raw_value or 0.0)
    return normalized


def build_storage_row(
    results: list[dict[str, Any]],
    merge_definitions: list[dict[str, Any]],
    storage_name: str = "Storage",
    pressure_bara: float = 10.0,
) -> dict[str, Any] | None:
    """Build a storage row by mixing final outputs from terminal upstream nodes."""
    if merge_definitions:
        upstream_merges: set[str] = set()
        for merge_def in merge_definitions:
            for source_type, source_value in merge_def.get("sources", []):
                if source_type == "merge":
                    upstream_merges.add(str(source_value))

        terminal_rows = [
            row
            for row in results
            if str(row.get("source_type")) == "merge"
            and str(row.get("source_name")) not in upstream_merges
        ]
    else:
        terminal_rows = [row for row in results if str(row.get("source_type")) == "plant"]

    total_flow = sum(float(row.get("total_massflow") or 0.0) for row in terminal_rows)

    normalized_finals = [
        _normalized_species_values(row.get("final", {}))
        for row in terminal_rows
    ]

    all_species: set[str] = set()
    for final_values in normalized_finals:
        all_species.update(final_values.keys())

    mixed_composition: dict[str, float] = {
        species: sum(
            normalized_final.get(species, 0.0) * float(row.get("total_massflow") or 0.0)
            for row, normalized_final in zip(terminal_rows, normalized_finals, strict=True)
        )
        / total_flow
        for species in sorted(all_species)
    }

    mixed_temperature = sum(
        float(row.get("temperature_kelvin") or 0.0) * float(row.get("total_massflow") or 0.0)
        for row in terminal_rows
    ) / total_flow

    stream_phase = str(terminal_rows[0].get("stream_phase") or "gas").strip().lower()

    pressure_pa = _bara_to_pa(float(pressure_bara))
    mixed_density = _co2_density_kg_per_m3(stream_phase, pressure_pa, mixed_temperature)

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
