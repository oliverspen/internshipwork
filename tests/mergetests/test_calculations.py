import pytest
import numpy as np
from backend.constants import SPECIES_ORDER, R
from backend.merge_support import calculations

def test_clean_float():
    value = 1.5555555
    rounded_value = calculations._clean_float(value)
    assert rounded_value == 1.55556

def test_bara_to_pa():
    bara = 3.0  
    pa = calculations._bara_to_pa(bara)
    assert pa == 300000

def test_celsius_to_kelvin():
    celsius = 25.0  
    kelvin = calculations._celsius_to_kelvin(celsius)
    assert kelvin == 298.15

def test_molar_ppm_to_concentration():
    molar_ppm = 20
    pressure_pa = 200000
    temperature_kelvin = 300
    concentration = calculations._molar_ppm_to_concentration(molar_ppm, pressure_pa, temperature_kelvin) 
    assert concentration == pytest.approx(0.001603720632)

def test_concentration_to_molar_ppm():
    concentration = 5
    pressure_pa = 50000
    temperature_kelvin = 273
    molar_ppm = calculations._concentration_to_molar_ppm(concentration, pressure_pa, temperature_kelvin)
    assert molar_ppm == 226972.2

def test_get_molecular_weight():
    species = "SO2"
    molecular_weight = calculations._get_molecular_weight(species)
    assert molecular_weight == 64

def test_get_species_concentration_uses_uppercase_contract_only():
    mixed_case_source_conc = {"SO2": 10.0, "NO": 5.0, "O2": 20.0, "so2": 15.0}
    lowercase_only_source_conc = {"so2": 10.0}
    uppercase_value = calculations._get_species_concentration(mixed_case_source_conc, "SO2")
    missing_value = calculations._get_species_concentration(mixed_case_source_conc, "NO2")
    lowercase_fallback_value = calculations._get_species_concentration(lowercase_only_source_conc, "SO2")
    assert uppercase_value == 10.0
    assert missing_value == 0.0
    assert lowercase_fallback_value == 0.0

def test_co2_density_kg_per_m3():
    pressure_pa = 200000
    temperature_kelvin_gas = 300
    temperature_kelvin_liquid = 220
    co2_density_gas = calculations._co2_density_kg_per_m3("gas", pressure_pa, temperature_kelvin_gas)
    co2_density_liquid = calculations._co2_density_kg_per_m3("liquid", pressure_pa, temperature_kelvin_liquid)
    assert co2_density_gas == pytest.approx(3.52818539)
    assert co2_density_liquid == pytest.approx(4.9495)
    with pytest.raises(ValueError):
        calculations._co2_density_kg_per_m3("solid", pressure_pa, temperature_kelvin_gas)

def test_flow_speed():
    flowrate = 100000 
    pipe_diameter = 0.5 
    density_kg_per_m3 = 0.3  
    flow_speed = calculations._flow_speed(flowrate, pipe_diameter, density_kg_per_m3)
    assert flow_speed == pytest.approx(471.5702019)

def test_pipe_time():
    pipe_length = 100000.0
    flowrate = 100000
    pipe_diameter = 0.5
    density_kg_per_m3 = 0.3
    pipe_time = calculations._pipe_time(pipe_length, flowrate, pipe_diameter, density_kg_per_m3)
    assert pipe_time == pytest.approx(212.0575041)

def test_get_merge_inputs():
    input_config = {
        "merge_pipe_inputs": {
            "Merge 1": {"pipelength": 100.0, "pipediameter": 0.5}
        }
    }
    resolved_config = calculations._get_merge_inputs(input_config, "Merge 1")
    assert resolved_config == (0.5, 100.0)
    with pytest.raises(KeyError):
        calculations._get_merge_inputs(input_config, "Missing Merge")

def test_build_plant_source_dict(monkeypatch: pytest.MonkeyPatch):
    # Arrange
    input_config = {
        "p_bara": 2.0,
        "plant_inputs": [
            {
                "temperature_celsius": 26.85,
                "stream_phase": "gas",
                "flowrate": 100000.0,
                "pipediameter": 0.5,
                "pipelength": 100000.0,
                "inlet_conc": {"SO2": 20.0, "NO2": 5.0},
            }
        ],
    }
    monkeypatch.setattr(calculations, "get_input_config", lambda: input_config)

    expected_initial_merge_conc = {
        "H2O": 0.0,
        "O2": 0.0,
        "SO2": 0.0016037206318659288,
        "NO2": 0.0004009301579664822,
        "H2S": 0.0,
        "NO": 0.0,
        "CO2": 80.18402694250662,
        "H2SO4": 0.0,
        "HNO3": 0.0,
        "HNO2": 0.0,
        "SO3": 0.0,
    }

    source_dict = calculations._build_plant_source_dict(0)

    assert source_dict["source_type"] == "plant"
    assert source_dict["source_name"] == 0
    assert source_dict["stream_phase"] == "gas"

    assert source_dict["temperature_kelvin"] == pytest.approx(300.0)
    assert source_dict["total_massflow"] == pytest.approx(100000.0)
    assert source_dict["density_kg_per_m3"] == pytest.approx(3.52819)
    assert source_dict["flow_speed"] == pytest.approx(40.09739990503085)
    assert source_dict["pipe_time"] == pytest.approx(2493.9272929627896)

    assert set(source_dict["initial_merge_conc"].keys()) == set(expected_initial_merge_conc.keys())
    for species, expected_value in expected_initial_merge_conc.items():
        assert source_dict["initial_merge_conc"][species] == pytest.approx(expected_value)


def test_build_merge_input_from_source_states(monkeypatch: pytest.MonkeyPatch):
    input_config = {
        "p_bara": 2.0,
        "merge_pipe_inputs": {
            "Merge 1": {"pipelength": 100000.0, "pipediameter": 0.5}
        },
    }
    monkeypatch.setattr(calculations, "get_input_config", lambda: input_config)

    source_dicts = [
        {
            "source_name": 0,
            "temperature_kelvin": 300.0,
            "total_massflow": 100000.0,
            "stream_phase": "gas",
            "initial_merge_conc": {
                "H2O": 0.0,
                "O2": 0.0,
                "SO2": 0.0016037206318659288,
                "NO2": 0.0004009301579664822,
                "H2S": 0.0,
                "NO": 0.0,
                "CO2": 80.18402694250662,
                "H2SO4": 0.0,
                "HNO3": 0.0,
                "HNO2": 0.0,
                "SO3": 0.0,
            },
        }
    ]

    expected_initial_merge_conc = {
        "H2O": 0.0,
        "O2": 0.0,
        "SO2": 0.0016037206318659288,
        "NO2": 0.0004009301579664822,
        "H2S": 0.0,
        "NO": 0.0,
        "CO2": 80.18402694250662,
        "H2SO4": 0.0,
        "HNO3": 0.0,
        "HNO2": 0.0,
        "SO3": 0.0,
    }
    expected_ppm_molar = {
        "H2O": 0.0,
        "O2": 0.0,
        "SO2": 20.0,
        "NO2": 5.0,
        "H2S": 0.0,
        "NO": 0.0,
        "CO2": 999975.0,
        "H2SO4": 0.0,
        "HNO3": 0.0,
        "HNO2": 0.0,
        "SO3": 0.0,
    }
    expected_ppm_mass = {
        "H2O": 0.0,
        "O2": 0.0,
        "SO2": 1280.0,
        "NO2": 230.0,
        "H2S": 0.0,
        "NO": 0.0,
        "CO2": 43998900.0,
        "H2SO4": 0.0,
        "HNO3": 0.0,
        "HNO2": 0.0,
        "SO3": 0.0,
    }

    merge_dict = calculations._build_merge_input_from_source_states(source_dicts, "Merge 1")

    assert merge_dict["sources"] == [0]
    assert merge_dict["stream_phase"] == "gas"

    assert merge_dict["temperature_kelvin"] == pytest.approx(300.0)
    assert merge_dict["total_massflow"] == pytest.approx(100000.0)
    assert merge_dict["density_kg_per_m3"] == pytest.approx(3.52819)
    assert merge_dict["flow_speed"] == pytest.approx(40.09739990503085)
    assert merge_dict["pipe_time"] == pytest.approx(2493.9272929627896)
    assert merge_dict["pipe_length"] == pytest.approx(100000.0)
    assert merge_dict["pipe_diameter"] == pytest.approx(0.5)

    assert set(merge_dict["initial_merge_conc"].keys()) == set(expected_initial_merge_conc.keys())
    for species, expected_value in expected_initial_merge_conc.items():
        assert merge_dict["initial_merge_conc"][species] == pytest.approx(expected_value)

    assert set(merge_dict["ppm_molar"].keys()) == set(expected_ppm_molar.keys())
    for species, expected_value in expected_ppm_molar.items():
        assert merge_dict["ppm_molar"][species] == pytest.approx(expected_value)

    assert set(merge_dict["ppm_mass"].keys()) == set(expected_ppm_mass.keys())
    for species, expected_value in expected_ppm_mass.items():
        assert merge_dict["ppm_mass"][species] == pytest.approx(expected_value)


def test_build_merge_input_two_sources_weighted_mix(monkeypatch: pytest.MonkeyPatch):
    input_config = {
        "p_bara": 2.0,
        "merge_pipe_inputs": {
            "Merge 1": {"pipelength": 100000.0, "pipediameter": 0.5}
        },
    }
    monkeypatch.setattr(calculations, "get_input_config", lambda: input_config)

    source_dicts = [
        {
            "source_name": 0,
            "temperature_kelvin": 300.0,
            "total_massflow": 100000.0,
            "stream_phase": "gas",
            "initial_merge_conc": {
                "H2O": 0.0,
                "O2": 0.0,
                "SO2": 0.0016037206318659288,
                "NO2": 0.0004009301579664822,
                "H2S": 0.0,
                "NO": 0.0,
                "CO2": 80.18402694250662,
                "H2SO4": 0.0,
                "HNO3": 0.0,
                "HNO2": 0.0,
                "SO3": 0.0,
            },
        },
        {
            "source_name": 1,
            "temperature_kelvin": 320.0,
            "total_massflow": 50000.0,
            "stream_phase": "liquid",
            "initial_merge_conc": {
                "H2O": 0.0,
                "O2": 0.0,
                "SO2": 0.003,
                "NO2": 0.001,
                "H2S": 0.0,
                "NO": 0.0,
                "CO2": 70.0,
                "H2SO4": 0.0,
                "HNO3": 0.0,
                "HNO2": 0.0,
                "SO3": 0.0,
            },
        },
    ]

    # Route wrapper source IDs to pre-built source states.
    source_dict_by_id = {
        source_dict["source_name"]: source_dict
        for source_dict in source_dicts
    }
    monkeypatch.setattr(
        calculations,
        "_build_plant_source_dict",
        lambda stream_idx: source_dict_by_id[stream_idx],
    )

    expected_initial_merge_conc = {
        "H2O": 0.0,
        "O2": 0.0,
        "SO2": 0.0020691470879106192,
        "NO2": 0.0006006201053109881,
        "H2S": 0.0,
        "NO": 0.0,
        "CO2": 76.78935129500441,
        "H2SO4": 0.0,
        "HNO3": 0.0,
        "HNO2": 0.0,
        "SO3": 0.0,
    }

    merge_dict = calculations.build_merge_input([0, 1], "Merge 1")

    assert merge_dict["sources"] == [0, 1]
    assert merge_dict["stream_phase"] == "liquid"
    assert merge_dict["total_massflow"] == 150000.0
    assert merge_dict["temperature_kelvin"] == pytest.approx(306.66667)
    assert merge_dict["density_kg_per_m3"] == pytest.approx(3.48373)
    assert merge_dict["flow_speed"] == pytest.approx(60.91357354857239)
    assert merge_dict["pipe_time"] == pytest.approx(1641.6702251142785)
    assert merge_dict["pipe_length"] == 100000.0
    assert merge_dict["pipe_diameter"] == 0.5

    assert set(merge_dict["initial_merge_conc"].keys()) == set(expected_initial_merge_conc.keys())
    for species, expected_value in expected_initial_merge_conc.items():
        assert merge_dict["initial_merge_conc"][species] == pytest.approx(expected_value)

