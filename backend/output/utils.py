
from typing import Any


def _celsius_from_kelvin(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value) - 273.15
    except (TypeError, ValueError):
        return None


def _round_conc(value: Any) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def infer_allowed_input_species(results: list[dict[str, Any]]) -> list[str]:
    totals: dict[str, float] = {}
    for row in results:
        if str(row.get("source_type", "")) == "storage":
            continue
        for species, value in row.get("tocomo_input", {}).items():
            totals[str(species)] = totals.get(str(species), 0.0) + abs(float(value or 0))
    return sorted(k for k, v in totals.items() if v > 0)


def filter_results_for_summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = set(infer_allowed_input_species(results))
    filtered_rows: list[dict[str, Any]] = []

    for row in results:
        row_copy = dict(row)
        input_values = row.get("tocomo_input", {})
        final_values = row.get("final", {})

        row_copy["tocomo_input"] = {
            k: input_values[k]
            for k in sorted(input_values)
            if str(k) in allowed
        }
        row_copy["final"] = {
            k: final_values[k]
            for k in sorted(final_values)
        }
        filtered_rows.append(row_copy)

    return filtered_rows


def infer_output_species(results: list[dict[str, Any]]) -> list[str]:
    totals: dict[str, float] = {}
    for row in results:
        if str(row.get("source_type", "")) == "storage":
            continue
        for species, value in row.get("final", {}).items():
            totals[str(species)] = totals.get(str(species), 0.0) + abs(float(value or 0))
    return sorted(k for k, v in totals.items() if v > 0)


def build_species_columns(results: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    input_species = infer_allowed_input_species(results)
    output_species = infer_output_species(results)
    return input_species, output_species


def _plant_name_from_source(source_name: Any, plant_inputs: list[dict[str, Any]] | None = None) -> Any:
    if isinstance(source_name, int):
        idx = source_name
    elif isinstance(source_name, str) and source_name.strip().isdigit():
        idx = int(source_name.strip())
    else:
        return source_name

    if idx < 0:
        return source_name

    plants = plant_inputs if isinstance(plant_inputs, list) else []
    if idx >= len(plants):
        return source_name

    configured_name = str((plants[idx] or {}).get("name") or "").strip()
    return configured_name or source_name


def build_excel_rows(
    results: list[dict[str, Any]],
    plant_inputs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    input_species, output_species = build_species_columns(results)
    rows: list[dict[str, Any]] = []
    for row in results:
        source_type = str(row.get("source_type", ""))
        source_name = row.get("source_name")
        if source_type == "plant":
            source_name = _plant_name_from_source(source_name, plant_inputs)

        record: dict[str, Any] = {
            "source_type": source_type,
            "source_name": source_name,
            "stream_phase": row.get("stream_phase"),
            "temperature (C)": _celsius_from_kelvin(row.get("temperature_kelvin")),
            "massflow (kg/hr)": row.get("total_massflow"),
            "density (kg/m3)": row.get("density_kg_per_m3"),
        }
        tocomo_input = row.get("tocomo_input", {})
        final_values = row.get("final", {})
        is_storage = str(row.get("source_type", "")) == "storage"
        output_source = tocomo_input if is_storage else final_values
        for species in input_species:
            record[f"inlet_{species} (molar ppm)"] = _round_conc(tocomo_input.get(species))
        for species in output_species:
            record[f"predicted_{species} (molar ppm)"] = _round_conc(output_source.get(species))
        rows.append(record)
    return rows


def build_storage_row(storage_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in storage_results:
        composition = row.get("tocomo_input", {})
        record: dict[str, Any] = {
            "name": row.get("source_name") or "Storage",
            "stream_phase": row.get("stream_phase"),
            "temperature (C)": _celsius_from_kelvin(row.get("temperature_kelvin")),
            "massflow (kg/hr)": row.get("total_massflow"),
            "density (kg/m3)": row.get("density_kg_per_m3"),
        }
        for species in sorted(composition):
            value = composition[species]
            if float(value or 0) != 0.0:
                record[f"inlet_{species} (molar ppm)"] = _round_conc(value)
        rows.append(record)
    return rows


def build_node_labels(
    results: list[dict[str, Any]],
    plant_names: dict[int, str],
) -> dict[str, str]:
    labels: dict[str, str] = {}
    for row in results:
        source_type = str(row.get("source_type", ""))
        source_name = row.get("source_name")
        final = row.get("final", {})
        inp = row.get("tocomo_input", {})
        temperature_kelvin = row.get("temperature_kelvin")
        total_massflow = row.get("total_massflow")

        if source_type == "plant":
            node_name = plant_names.get(int(source_name), f"plant {source_name}")
        elif source_type == "storage":
            node_name = str(source_name)
        else:
            node_name = str(source_name)

        lines: list[str] = []
        
        lines.append(node_name)
        lines.append("=" * 20)
        
        if source_type == "storage":
            if temperature_kelvin is not None:
                lines.append(f"T: {temperature_kelvin:.2f} K")
            if total_massflow is not None:
                lines.append(f"Flow: {total_massflow:.1f} kg/s")
            
            lines.append("Composition:")
            all_species = sorted(inp.keys())
            for species in all_species:
                in_v = float(inp.get(species, 0.0))
                if in_v == 0.0:
                    continue
                lines.append(f"  {species}: {in_v:.1f}")
        else:
            lines.append("Input:")
            if temperature_kelvin is not None:
                lines.append(f"  T: {temperature_kelvin:.2f} K")
            if total_massflow is not None:
                lines.append(f"  Flow: {total_massflow:.1f} kg/s")
            
            input_species = sorted(inp.keys())
            for species in input_species:
                in_v = float(inp.get(species, 0.0))
                if in_v == 0.0:
                    continue
                lines.append(f"  {species}: {in_v:.1f}")

            lines.append("Output:")
            output_species = sorted(final.keys())
            for species in output_species:
                out_v = float(final.get(species, 0.0))
                if out_v == 0.0:
                    continue
                lines.append(f"  {species}: {out_v:.1f}")

        if lines:
            labels[node_name] = "\n".join(lines)
    return labels


