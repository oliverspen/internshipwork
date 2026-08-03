from pathlib import Path

from backend.output.graph import build_graph_from_merge_definitions
from backend.output.utils import build_storage_row, filter_results_for_summary


def test_build_graph_from_merge_definitions_connects_terminal_merge_to_storage():
    merge_definitions = [
        {"merge_name": "Merge A", "sources": [("plant", 0), ("plant", 1)]},
        {"merge_name": "Merge B", "sources": [("merge", "Merge A"), ("plant", 2)]},
    ]
    plant_names = {0: "Plant 1", 1: "Plant 2", 2: "Plant 3"}

    graph, node_types = build_graph_from_merge_definitions(
        merge_definitions,
        plant_names,
        storage_name="Storage",
    )

    assert node_types["Storage"] == "storage"
    assert ("Merge B", "Storage") in graph.edges
    assert ("Merge A", "Storage") not in graph.edges


def test_build_storage_row_keeps_only_non_zero_species():
    rows = build_storage_row(
        [
            {
                "stream_phase": "gas",
                "temperature_kelvin": 300.0,
                "total_massflow": 1200.0,
                "density_kg_per_m3": 1.9,
                "tocomo_input": {"SO2": 2.0, "NO2": 0.0, "O2": 4.5},
            }
        ]
    )

    assert len(rows) == 1
    assert "inlet_SO2 (molar ppm)" in rows[0]
    assert "inlet_O2 (molar ppm)" in rows[0]
    assert "inlet_NO2 (molar ppm)" not in rows[0]


def test_filter_results_for_summary_preserves_final_ordered_keys():
    filtered = filter_results_for_summary(
        [
            {
                "source_type": "plant",
                "tocomo_input": {"SO2": 1.0, "NO2": 0.0},
                "final": {"hno3": 0.1, "h2so4": 0.2},
            }
        ]
    )

    assert len(filtered) == 1
    assert filtered[0]["tocomo_input"] == {"SO2": 1.0}
    assert set(filtered[0]["final"].keys()) == {"hno3", "h2so4"}
