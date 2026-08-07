from __future__ import annotations

from backend.models.storage_builder import build_storage_row


def test_build_storage_row_no_merges_weighted_mix():
    gas_results = [
        {
            "source_type": "plant",
            "source_name": 0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.2,
            "temperature_kelvin": 300.0,
            "total_massflow": 100.0,
            "final": {"SO2": 10.0, "NO2": 2.0},
        },
        {
            "source_type": "plant",
            "source_name": 1,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.1,
            "temperature_kelvin": 330.0,
            "total_massflow": 300.0,
            "final": {"SO2": 30.0, "NO2": 6.0},
        },
    ]

    gas_row = build_storage_row(
        results=gas_results,
        merge_definitions=[],
        storage_name="Tank A",
        pressure_bara=10.0,
    )

    assert gas_row is not None
    assert gas_row["source_type"] == "storage"
    assert gas_row["source_name"] == "Tank A"
    assert gas_row["stream_phase"] == "gas"
    assert gas_row["total_massflow"] == 400.0
    assert gas_row["temperature_kelvin"] == 322.5
    assert gas_row["tocomo_input"] == {"NO2": 5.0, "SO2": 25.0}
    assert gas_row["density_kg_per_m3"] == 16.41016

    liquid_results = [
        {
            **row,
            "stream_phase": "liquid",
            "temperature_kelvin": liquid_temp,
        }
        for row, liquid_temp in zip(gas_results, (220.0, 230.0), strict=True)
    ]

    liquid_row = build_storage_row(
        results=liquid_results,
        merge_definitions=[],
        storage_name="Liquid Tank",
        pressure_bara=10.0,
    )

    assert liquid_row is not None
    assert liquid_row["source_type"] == "storage"
    assert liquid_row["source_name"] == "Liquid Tank"
    assert liquid_row["stream_phase"] == "liquid"
    assert liquid_row["total_massflow"] == 400.0
    assert liquid_row["temperature_kelvin"] == 227.5
    assert liquid_row["tocomo_input"] == {"NO2": 5.0, "SO2": 25.0}
    assert liquid_row["density_kg_per_m3"] == 1138.7303


def test_build_storage_row_uses_terminal_merges_only():
    merge_definitions = [
        {"merge_name": "M1", "sources": [("plant", 0), ("plant", 1)]},
        {"merge_name": "M2", "sources": [("merge", "M1"), ("plant", 2)]},
    ]

    results = [
        {
            "source_type": "merge",
            "source_name": "M1",
            "stream_phase": "gas",
            "temperature_kelvin": 290.0,
            "total_massflow": 200.0,
            "final": {"SO2": 10.0},
        },
        {
            "source_type": "merge",
            "source_name": "M2",
            "stream_phase": "gas",
            "temperature_kelvin": 310.0,
            "total_massflow": 400.0,
            "final": {"SO2": 40.0},
        },
        {
            "source_type": "plant",
            "source_name": 0,
            "stream_phase": "gas",
            "temperature_kelvin": 280.0,
            "total_massflow": 50.0,
            "final": {"SO2": 99.0},
        },
    ]

    row = build_storage_row(
        results=results,
        merge_definitions=merge_definitions,
        storage_name="Storage",
        pressure_bara=8.0,
    )

    assert row is not None
    assert row["source_name"] == "Storage"
    assert row["stream_phase"] == "gas"
    assert row["total_massflow"] == 400.0
    assert row["temperature_kelvin"] == 310.0
    assert row["tocomo_input"] == {"SO2": 40.0}

    assert row["density_kg_per_m3"] == 13.65749


def test_build_storage_row_normalizes_species_key_case():
    results = [
        {
            "source_type": "plant",
            "source_name": 0,
            "stream_phase": "gas",
            "temperature_kelvin": 300.0,
            "total_massflow": 100.0,
            "final": {"h2s": 10.0},
        },
        {
            "source_type": "plant",
            "source_name": 1,
            "stream_phase": "gas",
            "temperature_kelvin": 300.0,
            "total_massflow": 300.0,
            "final": {"H2S": 30.0},
        },
    ]

    row = build_storage_row(
        results=results,
        merge_definitions=[],
        storage_name="Storage",
        pressure_bara=10.0,
    )

    assert row is not None
    assert row["tocomo_input"] == {"H2S": 25.0}
