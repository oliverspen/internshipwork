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
    return float(Decimal(str(value)).quantize(Decimal(f"1e-{decimal_places}")))


def _bara_to_pa(pressure_bara: float) -> float:
    return pressure_bara * 10**5


def _celsius_to_kelvin(temperature_c: float) -> float:
    return temperature_c + 273.15

def _molar_ppm_to_concentration(
    molar_ppm: float,
    pressure_pa_value: float,
    temperature_kelvin_value: float,
) -> float:
#convert molar ppm to concentration (mol/m³) using ideal gas law.
    return (molar_ppm * 10**-6) * pressure_pa_value / (R * temperature_kelvin_value)


def _concentration_to_molar_ppm(
    concentration: float,
    pressure_pa_value: float,
    temperature_kelvin_value: float,
) -> float:
    return concentration * 10**6 * R * temperature_kelvin_value / pressure_pa_value


def _get_molecular_weight(species: str) -> float:
#Return molecular weight for standard format.
    return float(molecular_weights[species])


def _get_species_concentration(source_conc: dict[str, float], species: str) -> float:
#Read concentration by standard format.
    return float(source_conc.get(species, 0.0))


def _co2_density_kg_per_m3(
    stream_phase: str,
    pressure_pa_value: float,
    temperature_kelvin_value: float,
) -> float:
    normalized_phase = stream_phase.strip().lower()
    if normalized_phase not in {"gas", "liquid"}:
        raise ValueError("stream_phase must be either 'gas' or 'liquid'.")
    if normalized_phase == "gas":
        co2_molar_mass_kg_per_mol = _get_molecular_weight("CO2") / 1000.0
        return pressure_pa_value * co2_molar_mass_kg_per_mol / (R * temperature_kelvin_value)
    return float(CP.PropsSI("D", "T", temperature_kelvin_value, "P", pressure_pa_value, "CO2"))


def _flow_speed(flowrate: float, pipe_diameter: float, density_kg_per_m3: float) -> float:
    flow_rate_s = flowrate * 1 / 3600  # Convert flowrate from kg/h to kg/s
    volumetric_flow_rate = flow_rate_s / density_kg_per_m3
    pipe_area = np.pi * (pipe_diameter / 2) ** 2
    return volumetric_flow_rate / pipe_area


def _pipe_time(pipe_length: float, flowrate: float, pipe_diameter: float, density_kg_per_m3: float) -> float:
    speed = _flow_speed(flowrate, pipe_diameter, density_kg_per_m3)
    return pipe_length / speed


def _get_merge_inputs(
    input_config: dict[str, Any],
    merge_name: str,
) -> tuple[float, float]:
    # Return merge pipe (diameter, length) for a required merge name
    merge_pipe_inputs = input_config.get("merge_pipe_inputs")
    if not isinstance(merge_pipe_inputs, dict):
        raise KeyError("merge_pipe_inputs is missing or invalid in input config.")

    if merge_name not in merge_pipe_inputs:
        raise KeyError(f"merge_pipe_inputs is missing required key '{merge_name}'.")
    merge_pipe_input = merge_pipe_inputs[merge_name]

    return float(merge_pipe_input["pipediameter"]), float(merge_pipe_input["pipelength"])


def _build_plant_source_dict(stream_idx: int) -> dict[str, Any]:
# builds a source dict for plants from inputs
    input_config = get_input_config()
    plant_inputs = input_config["plant_inputs"]
    if stream_idx < 0 or stream_idx >= len(plant_inputs):
        raise IndexError(f"Plant stream index '{stream_idx}' is out of range for active input config.")

    plant_input = plant_inputs[stream_idx]
    pressure_pa = _bara_to_pa(float(input_config["p_bara"]))
    temperature_kelvin = _celsius_to_kelvin(float(plant_input["temperature_celsius"]))
    stream_phase = str(plant_input["stream_phase"]).strip().lower()
    if stream_phase not in {"gas", "liquid"}:
        raise ValueError("stream_phase must be either 'gas' or 'liquid'.")
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
    merge_name: str,
) -> dict[str, Any]:
    """Mix plant and upstream-merge source dicts into one merged stream."""
    if not source_dicts:
        raise ValueError("At least one source stream is required to build a merge input.")

    input_config = get_input_config()
    pressure_pa = _bara_to_pa(float(input_config["p_bara"]))

    total_massflow = sum(source_dict["total_massflow"] for source_dict in source_dicts)

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

    ppm_molar = {
        species: _concentration_to_molar_ppm(concentration, pressure_pa, temperature_kelvin_total)
        for species, concentration in initial_merge_conc.items()
    }
    ppm_mass = {
        species: ppm_molar[species] * _get_molecular_weight(species)
        for species in SPECIES_ORDER
    }

    merge_pipe_diameter, merge_pipe_length = _get_merge_inputs(input_config, merge_name)
    flow_speed = _flow_speed(total_massflow, merge_pipe_diameter, merge_density)
    resolved_pipe_time = _pipe_time(merge_pipe_length, total_massflow, merge_pipe_diameter, merge_density)
    return {
        "sources": [source_dict["source_name"] for source_dict in source_dicts],
        "flow_speed": flow_speed,
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


def build_merge_input(source_stream_ids, merge_name: str):
    """Mix inlet plant stream concentrations into one merged inlet stream."""
    source_dicts = [_build_plant_source_dict(stream_idx) for stream_idx in source_stream_ids]
    return _build_merge_input_from_source_states(source_dicts, merge_name=merge_name)


