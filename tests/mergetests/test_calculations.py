import pytest

from internshipwork.constants import SPECIES_ORDER
from internshipwork.merge_support import calculations


def _zero_species_dict() -> dict[str, float]:
    return {species: 0.0 for species in SPECIES_ORDER}


def test_clean_float_quantizes_to_five_decimals_by_default():
    assert calculations._clean_float(1.23456789) == 1.23457
    assert calculations._clean_float(1.23456789, decimal_places=3) == 1.235


def test_get_species_concentration_does_not_double_count_upper_lower_aliases():
    source_conc = {"SO2": 1.0, "so2": 1.0}
    assert calculations._get_species_concentration(source_conc, "SO2") == 1.0


def test_build_merge_input_rounds_ppm_concentrations_to_one_decimal(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(calculations, "get_input_config", lambda: {"p_bara": 10.0})
    monkeypatch.setattr(
        calculations,
        "_concentration_to_molar_ppm",
        lambda concentration, pressure_pa_value, temperature_kelvin_value: 1.1234567890123,
    )
    monkeypatch.setattr(calculations, "_get_molecular_weight", lambda species: 2.0)

    source = {
        "source_name": 0,
        "stream_phase": "gas",
        "temperature_kelvin": 300.0,
        "total_massflow": 100.0,
        "initial_merge_conc": _zero_species_dict(),
    }

    result = calculations._build_merge_input_from_source_states([source])
    assert result["ppm_molar"]["CO2"] == calculations._clean_float(1.1234567890123, decimal_places=1)
    assert result["ppm_mass"]["CO2"] == calculations._clean_float(2.2469135780246, decimal_places=1)


def test_celsius_to_kelvin_uses_precise_offset():
    assert calculations._celsius_to_kelvin(25.0) == 298.15


def test_molar_ppm_conversion_round_trip():
    pressure_pa = 1_000_000.0
    temperature_kelvin = 300.0
    ppm_value = 2500.0

    concentration = calculations._molar_ppm_to_concentration(
        ppm_value,
        pressure_pa,
        temperature_kelvin,
    )
    restored_ppm = calculations._concentration_to_molar_ppm(
        concentration,
        pressure_pa,
        temperature_kelvin,
    )

    assert restored_ppm == pytest.approx(ppm_value)


def test_build_plant_source_dict_adds_co2_and_core_fields(monkeypatch: pytest.MonkeyPatch):
    config = {
        "p_bara": 10.0,
        "plant_inputs": [
            {
                "name": "Plant A",
                "inlet_conc": {
                    "o2": 2.0,
                    "h2o": 1.0,
                    "so2": 3.0,
                    "no2": 4.0,
                    "no": 6.0,
                    "so3": 10.0,
                    "h2s": 5.0,
                },
                "stream_phase": "gas",
                "flowrate": 1000.0,
                "temperature_celsius": 25.0,
                "pipelength": 1000.0,
                "pipediameter": 0.5,
            }
        ],
    }
    monkeypatch.setattr(calculations, "get_input_config", lambda: config)

    result = calculations._build_plant_source_dict(0)

    assert result["source_type"] == "plant"
    assert result["source_name"] == 0
    assert result["temperature_kelvin"] == 298.15
    assert result["total_massflow"] == 1000.0
    assert result["stream_phase"] == "gas"
    assert set(result["initial_merge_conc"].keys()) == set(SPECIES_ORDER)


def test_build_merge_input_from_source_states_mixes_weighted_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        calculations,
        "get_input_config",
        lambda: {
            "p_bara": 10.0,
            "merge_pipe_inputs": {
                "default": {"pipediameter": 0.4, "pipelength": 750.0}
            },
        },
    )

    conc_a = _zero_species_dict()
    conc_b = _zero_species_dict()
    conc_a["co2"] = 1.0
    conc_b["co2"] = 3.0

    sources = [
        {
            "source_name": 0,
            "temperature_kelvin": 300.0,
            "total_massflow": 100.0,
            "initial_merge_conc": conc_a,
        },
        {
            "source_name": 1,
            "temperature_kelvin": 330.0,
            "total_massflow": 300.0,
            "initial_merge_conc": conc_b,
        },
    ]

    result = calculations._build_merge_input_from_source_states(sources)

    assert result["sources"] == [0, 1]
    assert result["pipe_time"] is not None
    assert result["total_massflow"] == 400.0
    assert result["temperature_kelvin"] == 322.5
    assert result["initial_merge_conc"]["co2"] == 2.5


def test_build_merge_input_uses_plant_sources(monkeypatch: pytest.MonkeyPatch):
    def fake_build_plant_source_dict(stream_idx: int):
        base = _zero_species_dict()
        base["co2"] = float(stream_idx + 1)
        return {
            "source_name": stream_idx,
            "temperature_kelvin": 300.0,
            "total_massflow": 100.0,
            "initial_merge_conc": base,
        }

    monkeypatch.setattr(calculations, "_build_plant_source_dict", fake_build_plant_source_dict)
    monkeypatch.setattr(
        calculations,
        "get_input_config",
        lambda: {
            "p_bara": 10.0,
            "merge_pipe_inputs": {
                "default": {"pipediameter": 0.4, "pipelength": 750.0}
            },
        },
    )

    result = calculations.build_merge_input([0, 1])

    assert result["sources"] == [0, 1]
    assert result["pipe_time"] is not None


def test_build_merge_input_from_source_states_requires_sources(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(calculations, "get_input_config", lambda: {"p_bara": 10.0})

    with pytest.raises(ValueError, match="At least one source stream"):
        calculations._build_merge_input_from_source_states([])


def test_build_merge_input_from_source_states_rejects_non_positive_total_massflow(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(calculations, "get_input_config", lambda: {"p_bara": 10.0})

    source = {
        "source_name": 0,
        "temperature_kelvin": 300.0,
        "total_massflow": 0.0,
        "initial_merge_conc": _zero_species_dict(),
    }

    with pytest.raises(ValueError, match="Total massflow must be greater than zero"):
        calculations._build_merge_input_from_source_states([source])
