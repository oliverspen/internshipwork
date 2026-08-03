import importlib


utils = importlib.import_module("internshipwork.output.utils")


def test_infer_output_species_ignores_storage_and_zero_values():
    species = utils.infer_output_species(
        [
            {"source_type": "plant", "final": {"h2so4": 0.5, "hno3": 0.0}},
            {"source_type": "storage", "final": {"h2so4": 99.0}},
            {"source_type": "merge", "final": {"hno3": -0.2}},
        ]
    )

    assert species == ["h2so4", "hno3"]


def test_build_excel_rows_uses_storage_input_as_output_source():
    rows = utils.build_excel_rows(
        [
            {
                "source_type": "plant",
                "source_name": "Plant A",
                "stream_phase": "gas",
                "temperature_kelvin": 300.0,
                "total_massflow": 12.0,
                "density_kg_per_m3": 1.1,
                "tocomo_input": {"SO2": 2.0},
                "final": {"h2so4": 1.0},
            },
            {
                "source_type": "storage",
                "source_name": "Storage",
                "stream_phase": "gas",
                "temperature_kelvin": 300.0,
                "total_massflow": 12.0,
                "density_kg_per_m3": 1.1,
                "tocomo_input": {"SO2": 3.0},
                "final": {"h2so4": 999.0},
            },
        ]
    )

    plant_row = rows[0]
    storage_row = rows[1]

    assert plant_row["predicted_h2so4 (molar ppm)"] == 1.0
    assert storage_row["predicted_h2so4 (molar ppm)"] is None


def test_build_node_labels_formats_plant_and_storage_sections():
    labels = utils.build_node_labels(
        results=[
            {
                "source_type": "plant",
                "source_name": 0,
                "temperature_kelvin": 300.0,
                "total_massflow": 10.0,
                "tocomo_input": {"SO2": 2.0, "NO2": 0.0},
                "final": {"h2so4": 1.0, "hno3": 0.0},
            },
            {
                "source_type": "storage",
                "source_name": "Storage",
                "temperature_kelvin": 301.0,
                "total_massflow": 11.0,
                "tocomo_input": {"SO2": 2.5, "NO2": 0.0},
                "final": {},
            },
        ],
        plant_names={0: "Plant 1"},
    )

    assert "Plant 1" in labels
    assert "Input:" in labels["Plant 1"]
    assert "Output:" in labels["Plant 1"]
    assert "SO2: 2.0" in labels["Plant 1"]
    assert "h2so4: 1.0" in labels["Plant 1"]

    assert "Storage" in labels
    assert "Composition:" in labels["Storage"]
    assert "SO2: 2.5" in labels["Storage"]
    assert "NO2" not in labels["Storage"]
