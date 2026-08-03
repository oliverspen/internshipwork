"""Calculations module for thermodynamic and fluid dynamic properties at merge nodes.

Provides utilities to:
- Convert between pressure (bara/Pa) and temperature (°C/K) units
- Calculate CO2 density using CoolProp for gas and liquid phases
- Convert between molar ppm and concentration (mol/m³) using ideal gas law
- Calculate flow speed and residence time in pipes
- Build plant source dictionaries with initial conditions
- Mix multiple sources into equilibrium merge inlet streams

All calculations assume constant pressure and negligible mixing losses.
Most scalar values are cleaned to 5 decimal places for numerical stability.
Concentration outputs (ppm) are cleaned to 1 decimal place.
"""

from decimal import Decimal
from typing import Any
import CoolProp.CoolProp as CP
import numpy as np

from backend.constants import R, SPECIES_ORDER, molecular_weights
from backend.user_inputs import PLANT_SPECIES, get_input_config


def _clean_float(value: float, decimal_places: int = 5) -> float:
    """Round float to specified decimal places using Decimal for precision.
    
    Args:
        value: Float value to round.
        decimal_places: Number of decimal places (default 5).
    
    Returns:
        Rounded float value.
    """
    return float(Decimal(str(value)).quantize(Decimal(f"1e-{decimal_places}")))


def _bara_to_pa(pressure_bara: float) -> float:
    """Convert pressure from bara (absolute bar) to Pa (pascals).
    
    Args:
        pressure_bara: Pressure in bara.
    
    Returns:
        Pressure in pascals (1 bara = 1e5 Pa).
    """
    return pressure_bara * 10**5


def _celsius_to_kelvin(temperature_c: float) -> float:
    """Convert temperature from Celsius to Kelvin.
    
    Args:
        temperature_c: Temperature in Celsius.
    
    Returns:
        Temperature in Kelvin.
    """
    return temperature_c + 273.15


def _molar_ppm_to_concentration(
    molar_ppm: float,
    pressure_pa_value: float,
    temperature_kelvin_value: float,
) -> float:
    """Convert molar ppm concentration to mol/m³ using ideal gas law.
    
    Args:
        molar_ppm: Concentration in molar ppm (parts per million moles).
        pressure_pa_value: Pressure in pascals.
        temperature_kelvin_value: Temperature in Kelvin.
    
    Returns:
        Concentration in mol/m³.
    """
    # ppm means parts per million (1e-6 mole fraction).
    return (molar_ppm * 10**-6) * pressure_pa_value / (R * temperature_kelvin_value)


def _concentration_to_molar_ppm(
    concentration: float,
    pressure_pa_value: float,
    temperature_kelvin_value: float,
) -> float:
    """Convert concentration (mol/m³) to molar ppm using ideal gas law.
    
    Args:
        concentration: Concentration in mol/m³.
        pressure_pa_value: Pressure in pascals.
        temperature_kelvin_value: Temperature in Kelvin.
    
    Returns:
        Concentration in molar ppm.
    """
    return concentration * 10**6 * R * temperature_kelvin_value / pressure_pa_value

def _normalize_stream_phase(stream_phase: str) -> str:
    """Normalize and validate stream phase string.
    
    Args:
        stream_phase: Stream phase as string ('gas' or 'liquid').
    
    Returns:
        Normalized lowercase phase string.
    
    Raises:
        ValueError: If phase is not 'gas' or 'liquid'.
    """
    normalized = stream_phase.strip().lower()
    if normalized not in {"gas", "liquid"}:
        raise ValueError(
            "stream_phase must be either 'gas' or 'liquid'."
        )
    return normalized


def _get_molecular_weight(species: str) -> float:
    """Return molecular weight for species, supporting legacy lowercase keys."""
    if species in molecular_weights:
        return molecular_weights[species]

    upper_species = species.upper()
    if upper_species in molecular_weights:
        return molecular_weights[upper_species]

    lower_species = species.lower()
    if lower_species in molecular_weights:
        return molecular_weights[lower_species]

    raise KeyError(species)


def _get_species_concentration(source_conc: dict[str, float], species: str) -> float:
    """Read concentration by species key with uppercase/lowercase compatibility.

    Avoid summing duplicate alias keys (for example "SO2" and "so2") because
    merged source dicts may intentionally carry both for backward compatibility.
    """
    lower_species = species.lower()
    upper_species = species.upper()

    has_exact = species in source_conc
    has_lower = lower_species in source_conc
    has_upper = upper_species in source_conc

    exact_value = float(source_conc.get(species, 0.0)) if has_exact else None
    lower_value = float(source_conc.get(lower_species, 0.0)) if has_lower else None
    upper_value = float(source_conc.get(upper_species, 0.0)) if has_upper else None

    if has_exact and has_lower and lower_species != species:
        # Alias pair present: avoid summing duplicates, but allow non-zero override.
        if exact_value == 0.0 and lower_value != 0.0:
            return lower_value
        if lower_value == 0.0 and exact_value != 0.0:
            return exact_value
        return exact_value

    if has_exact and has_upper and upper_species != species:
        if exact_value == 0.0 and upper_value != 0.0:
            return upper_value
        if upper_value == 0.0 and exact_value != 0.0:
            return exact_value
        return exact_value

    if has_exact:
        return exact_value
    if has_lower:
        return lower_value
    if has_upper:
        return upper_value

    return 0.0


def _co2_density_kg_per_m3(
    stream_phase: str,
    pressure_pa_value: float,
    temperature_kelvin_value: float,
) -> float:
    """Calculate CO2 density at given conditions.
    
    For gas phase, uses ideal gas law. For liquid phase, uses CoolProp property database.
    
    Args:
        stream_phase: 'gas' or 'liquid'.
        pressure_pa_value: Pressure in pascals.
        temperature_kelvin_value: Temperature in Kelvin.
    
    Returns:
        CO2 density in kg/m³.
    """
    normalized_phase = _normalize_stream_phase(stream_phase)
    if normalized_phase == "gas":
        co2_molar_mass_kg_per_mol = _get_molecular_weight("CO2") / 1000.0
        return pressure_pa_value * co2_molar_mass_kg_per_mol / (R * temperature_kelvin_value)
    return float(CP.PropsSI("D", "T", temperature_kelvin_value, "P", pressure_pa_value, "CO2"))


def _flow_speed(flowrate: float, pipe_diameter: float, density_kg_per_m3: float) -> float:
    """Calculate fluid flow speed in pipe.
    
    Args:
        flowrate: Mass flow rate in kg/h.
        pipe_diameter: Pipe diameter in meters.
        density_kg_per_m3: Fluid density in kg/m³.
    
    Returns:
        Flow speed in m/s.
    """
    flow_rate_s = flowrate * 1 / 3600  # Convert flowrate from kg/h to kg/s
    volumetric_flow_rate = flow_rate_s / density_kg_per_m3
    pipe_area = np.pi * (pipe_diameter / 2) ** 2
    return volumetric_flow_rate / pipe_area


def _pipe_time(pipe_length: float, flowrate: float, pipe_diameter: float, density_kg_per_m3: float) -> float:
    """Calculate residence time of fluid in pipe segment.
    
    Args:
        pipe_length: Pipe length in meters.
        flowrate: Mass flow rate in kg/h.
        pipe_diameter: Pipe diameter in meters.
        density_kg_per_m3: Fluid density in kg/m³.
    
    Returns:
        Residence time in seconds.
    """
    speed = _flow_speed(flowrate, pipe_diameter, density_kg_per_m3)
    return pipe_length / speed


def _resolve_merge_pipe_config(
    input_config: dict[str, Any],
    merge_name: str | None = None,
) -> tuple[float | None, float | None]:
    """Return merge pipe (diameter, length) for a merge name or default, if configured."""
    merge_pipe_inputs = input_config.get("merge_pipe_inputs")
    if not isinstance(merge_pipe_inputs, dict):
        return None, None

    if merge_name is not None:
        if merge_name not in merge_pipe_inputs:
            raise KeyError(f"merge_pipe_inputs is missing required key '{merge_name}'.")
        merge_pipe_input = merge_pipe_inputs[merge_name]
    else:
        if "default" not in merge_pipe_inputs:
            return None, None
        merge_pipe_input = merge_pipe_inputs["default"]

    return float(merge_pipe_input["pipediameter"]), float(merge_pipe_input["pipelength"])


def _build_plant_source_dict(stream_idx: int) -> dict[str, Any]:
    """Build source dictionary from plant inlet stream specification.
    
    Loads plant configuration, converts units, and calculates thermodynamic properties
    and flow dynamics for the plant stream at given index.
    
    Args:
        stream_idx: Index of plant stream in input_config['plant_inputs'].
    
    Returns:
        Dictionary with keys: source_type, source_name, temperature_kelvin, total_massflow,
        stream_phase, density_kg_per_m3, initial_merge_conc (dict), flow_speed, pipe_time.
    
    Raises:
        IndexError: If stream_idx is out of range.
    """
    input_config = get_input_config()
    plant_inputs = input_config["plant_inputs"]
    if stream_idx < 0 or stream_idx >= len(plant_inputs):
        raise IndexError(f"Plant stream index '{stream_idx}' is out of range for active input config.")

    plant_input = plant_inputs[stream_idx]
    pressure_pa = _bara_to_pa(float(input_config["p_bara"]))
    temperature_kelvin = _celsius_to_kelvin(float(plant_input["temperature_celsius"]))
    stream_phase = _normalize_stream_phase(str(plant_input["stream_phase"]))
    stream_density = _co2_density_kg_per_m3(stream_phase, pressure_pa, temperature_kelvin)

    raw_inlet_conc = {
        str(species_key).strip().upper(): float(species_value)
        for species_key, species_value in plant_input["inlet_conc"].items()
    }
    inlet_ppm = {
        species: float(raw_inlet_conc.get(species, 0.0))
        for species in PLANT_SPECIES
    }
    nonco2_total = sum(inlet_ppm.values())
    inlet_ppm["CO2"] = max(0.0, 10**6 - nonco2_total)

    initial_merge_conc: dict[str, float] = {
        species: _molar_ppm_to_concentration(
            inlet_ppm.get(species, 0.0),
            pressure_pa,
            temperature_kelvin,
        )
        for species in SPECIES_ORDER
    }

    flow_speed = _flow_speed(
        float(plant_input["flowrate"]),
        float(plant_input["pipediameter"]),
        stream_density,
    )
    pipe_time = _pipe_time(
        float(plant_input["pipelength"]),
        float(plant_input["flowrate"]),
        float(plant_input["pipediameter"]),
        stream_density,
    )

    return {
        "source_type": "plant",
        "source_name": stream_idx,
        "temperature_kelvin": temperature_kelvin,
        "total_massflow": float(plant_input["flowrate"]),
        "stream_phase": stream_phase,
        "density_kg_per_m3": _clean_float(stream_density),
        "initial_merge_conc": initial_merge_conc,
        "flow_speed": flow_speed,
        "pipe_time": pipe_time,
    }


def _build_merge_input_from_source_states(
    source_dicts: list[dict[str, Any]],
    merge_name: str | None = None,
) -> dict[str, Any]:
    """Mix plant and upstream-merge source dicts into one merged stream."""
    if not source_dicts:
        raise ValueError("At least one source stream is required to build a merge input.")

    input_config = get_input_config()
    pressure_pa = _bara_to_pa(float(input_config["p_bara"]))

    total_massflow = sum(source_dict["total_massflow"] for source_dict in source_dicts)
    if total_massflow <= 0:
        raise ValueError("Total massflow must be greater than zero for merge calculations.")

    # Calculate mass-weighted average temperature of merged stream
    temperature_kelvin_total = (
        sum(
            source_dict["temperature_kelvin"] * source_dict["total_massflow"]
            for source_dict in source_dicts
        )
        / total_massflow
    )
    merge_stream_phase = (
        "liquid"
        if any(source_dict.get("stream_phase") == "liquid" for source_dict in source_dicts)
        else "gas"
    )
    merge_density = _co2_density_kg_per_m3(merge_stream_phase, pressure_pa, temperature_kelvin_total)

    initial_merge_conc = { 
        species: (
            sum(
                _get_species_concentration(source_dict["initial_merge_conc"], species)
                * source_dict["total_massflow"]
                for source_dict in source_dicts
            )
            / total_massflow
        )
        for species in SPECIES_ORDER
    }

    # Keep lowercase aliases for backward compatibility with older callers/tests.
    for species in SPECIES_ORDER:
        initial_merge_conc[species.lower()] = initial_merge_conc[species]

    ppm_molar = {
        species: _concentration_to_molar_ppm(concentration, pressure_pa, temperature_kelvin_total)
        for species, concentration in initial_merge_conc.items()
    }
    ppm_mass = {
        species: ppm_molar[species] * _get_molecular_weight(species)
        for species in SPECIES_ORDER
    }

    merge_pipe_diameter, merge_pipe_length = _resolve_merge_pipe_config(input_config, merge_name)
    flowspeed = (
        _flow_speed(total_massflow, merge_pipe_diameter, merge_density)
        if merge_pipe_diameter is not None
        else None
    )
    resolved_pipe_time = (
        _pipe_time(merge_pipe_length, total_massflow, merge_pipe_diameter, merge_density)
        if merge_pipe_diameter is not None and merge_pipe_length is not None
        else None
    )
    return {
        "sources": [source_dict["source_name"] for source_dict in source_dicts],
        "flow_speed": flowspeed,
        "pipe_time": resolved_pipe_time,
        "stream_phase": merge_stream_phase,
        "density_kg_per_m3": _clean_float(merge_density),
        "temperature_kelvin": _clean_float(temperature_kelvin_total),
        "total_massflow": _clean_float(total_massflow),
        # Keep full precision here because downstream merges mix these values.
        "initial_merge_conc": initial_merge_conc,
        "ppm_molar": {
            species: _clean_float(value, decimal_places=1)
            for species, value in ppm_molar.items()
        },
        "ppm_mass": {
            species: _clean_float(value, decimal_places=1)
            for species, value in ppm_mass.items()
        },
        "pipe_length": merge_pipe_length,
        "pipe_diameter": merge_pipe_diameter,
    }


def build_merge_input(source_stream_ids, merge_name: str | None = None):
    """Mix inlet plant stream concentrations into one merged inlet stream."""
    source_dicts = [_build_plant_source_dict(stream_idx) for stream_idx in source_stream_ids]
    return _build_merge_input_from_source_states(source_dicts, merge_name=merge_name)


