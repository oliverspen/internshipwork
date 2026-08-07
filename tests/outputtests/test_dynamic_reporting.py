import importlib
from pathlib import Path

import pandas as pd
import pytest


dynamic_reporting = importlib.import_module("backend.output.dynamic_reporting")


def _sample_dynamic_results() -> list[dict]:
    return [
        {
            "time_days": 0.0,
            "merge_name": "Merge A",
            "sources": "0",
            "flow_kg_per_h": 100.0,
            "temperature_celsius": 25.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.8,
            "pipe_time_days": 2.0,
            "acoustic_pipe_time_days": 0.0,
            "final": {"SO2": 1.0, "NO2": 0.5},
        },
        {
            "time_days": 1.0,
            "merge_name": "Merge A",
            "sources": "0",
            "flow_kg_per_h": 150.0,
            "temperature_celsius": 28.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.9,
            "pipe_time_days": 2.0,
            "acoustic_pipe_time_days": 0.0,
            "final": {"SO2": 2.0, "NO2": 0.5},
        },
        {
            "time_days": 0.0,
            "merge_name": "Merge B",
            "sources": "Merge A, 1",
            "flow_kg_per_h": 200.0,
            "temperature_celsius": 26.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 2.0,
            "pipe_time_days": 3.0,
            "acoustic_pipe_time_days": 0.2,
            "final": {"SO2": 3.0, "NO2": 0.2},
        },
        {
            "time_days": 1.0,
            "merge_name": "Merge B",
            "sources": "Merge A, 1",
            "flow_kg_per_h": 200.0,
            "temperature_celsius": 26.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 2.0,
            "pipe_time_days": 3.0,
            "acoustic_pipe_time_days": 0.2,
            "final": {"SO2": 4.0, "NO2": 0.2},
        },
    ]


def _sample_plant_results() -> list[dict]:
    return [
        {
            "time_days": 0.0,
            "plant_name": "Plant 1",
            "flow_kg_per_h": 100.0,
            "temperature_celsius": 25.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.8,
            "pipe_time_days": 1.0,
            "pipe_length_m": 100.0,
            "pipe_diameter_m": 0.5,
            "inlet_SO2": 1.0,
            "inlet_NO2": 0.5,
        },
        {
            "time_days": 1.0,
            "plant_name": "Plant 1",
            "flow_kg_per_h": 150.0,
            "temperature_celsius": 28.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.9,
            "pipe_time_days": 1.0,
            "pipe_length_m": 100.0,
            "pipe_diameter_m": 0.5,
            "inlet_SO2": 2.0,
            "inlet_NO2": 0.5,
        },
    ]


def test_infer_dt_days_handles_edge_cases():
    assert dynamic_reporting._infer_dt_days([]) == 0.1
    assert dynamic_reporting._infer_dt_days([{"time_days": 3.0}]) == 0.1
    assert dynamic_reporting._infer_dt_days([{"time_days": 0.0}, {"time_days": 0.5}, {"time_days": 2.0}]) == 0.5


def test_requested_dynamic_metrics_extracts_flow_temp_and_species():
    profile = {
        "plant_profiles": {
            "Plant 1": {
                "flowrate": [(0, 1.0)],
                "temperature_celsius": [(0, 20.0)],
                "inlet_conc": {"SO2": [(0, 1.0)], "NO2": []},
            }
        }
    }

    metrics = dynamic_reporting._requested_dynamic_metrics(profile)
    names = [m["name"] for m in metrics]

    assert "Flow" in names
    assert "Temperature" in names
    assert "SO2" in names
    assert "NO2" not in names


def test_compact_change_table_keeps_first_and_changed_rows():
    table = pd.DataFrame(
        [
            {"time_days": 0.0, "merge_name": "M1", "flow": 1.0, "phase": "gas"},
            {"time_days": 1.0, "merge_name": "M1", "flow": 1.0, "phase": "gas"},
            {"time_days": 2.0, "merge_name": "M1", "flow": 2.0, "phase": "gas"},
            {"time_days": 0.0, "merge_name": "M2", "flow": 5.0, "phase": "gas"},
            {"time_days": 1.0, "merge_name": "M2", "flow": 5.0, "phase": "liquid"},
        ]
    )

    compact = dynamic_reporting._compact_change_table(
        table,
        group_col="merge_name",
        tracked_cols=["flow", "phase"],
        numeric_cols=["flow"],
    )

    assert len(compact) == 4


def test_round_numeric_columns_rounds_selected_columns_only():
    table = pd.DataFrame([{"time_days": 1.23456, "label": "x"}])
    rounded = dynamic_reporting._round_numeric_columns(table, ["time_days"], digits=2)
    assert rounded.iloc[0]["time_days"] == 1.23
    assert rounded.iloc[0]["label"] == "x"


def test_print_dynamic_tables_execute(capsys):
    dynamic_reporting._print_dynamic_merge_table(_sample_dynamic_results())
    dynamic_reporting._print_dynamic_plant_table(_sample_plant_results())
    out = capsys.readouterr().out
    assert "Merge change points" in out
    assert "Plant change points" in out


def test_format_change_annotation_includes_time_only():
    assert dynamic_reporting._format_change_annotation(1.0, 2.0, 3.5) == "t=3.50 d"


def test_ensure_merge_metric_column_derives_from_final_payload():
    table = pd.DataFrame([{"final": {"SO2": 4.2}}])
    resolved = dynamic_reporting._ensure_merge_metric_column(table, "final_SO2")
    assert float(resolved.iloc[0]["final_SO2"]) == pytest.approx(4.2)


def test_build_storage_receipt_table_finds_terminal_merges_and_snaps_time():
    table = dynamic_reporting._build_storage_receipt_table(_sample_dynamic_results(), dt_days=0.5)
    assert not table.empty
    assert list(table["storage_stream"].unique()) == ["Merge B -> Storage"]
    assert table["time_days"].min() >= 0.0



def test_storage_receipt_flow_uses_instantaneous_delay():
    dynamic_results = [
        {
            "time_days": 2.0,
            "merge_name": "Terminal",
            "sources": "0",
            "flow_kg_per_h": 123.0,
            "pipe_time_days": 50.0,
            "acoustic_pipe_time_days": 0.0,
        }
    ]

    table = dynamic_reporting._build_storage_receipt_table_for_column(
        dynamic_results,
        value_col="flow_kg_per_h",
        dt_days=1.0,
    )

    assert list(table["time_days"]) == [2.0]
    assert list(table["metric_value"]) == [123.0]


def test_storage_receipt_concentration_uses_fluid_delay():
    dynamic_results = [
        {
            "time_days": 2.0,
            "merge_name": "Terminal",
            "sources": "0",
            "final_NO2": 7.0,
            "pipe_time_days": 5.0,
            "acoustic_pipe_time_days": 0.0,
        }
    ]

    table = dynamic_reporting._build_storage_receipt_table_for_column(
        dynamic_results,
        value_col="final_NO2",
        dt_days=1.0,
    )

    assert list(table["time_days"]) == [0.0, 7.0]
    assert list(table["metric_value"]) == [7.0, 7.0]


def test_storage_receipt_concentration_can_use_instantaneous_delay_for_flow_driven_case():
    dynamic_results = [
        {
            "time_days": 2.0,
            "merge_name": "Terminal",
            "sources": "0",
            "final_NO2": 7.0,
            "pipe_time_days": 5.0,
            "acoustic_pipe_time_days": 0.0,
        }
    ]

    table = dynamic_reporting._build_storage_receipt_table_for_column(
        dynamic_results,
        value_col="final_NO2",
        dt_days=1.0,
        composition_instantaneous=True,
    )

    assert list(table["time_days"]) == [0.0, 2.0]
    assert list(table["metric_value"]) == [7.0, 7.0]


def test_use_instantaneous_storage_composition_only_for_flow_without_inlet_steps():
    flow_only_profile = {
        "plant_profiles": {
            "Plant 1": {
                "flowrate": [(1.0, 1250.0)],
            }
        }
    }
    with_inlet_step_profile = {
        "plant_profiles": {
            "Plant 1": {
                "flowrate": [(1.0, 1250.0)],
                "inlet_conc": {"SO2": [(2.0, 5.0)]},
            }
        }
    }

    assert dynamic_reporting._use_instantaneous_storage_composition(flow_only_profile)
    assert not dynamic_reporting._use_instantaneous_storage_composition(with_inlet_step_profile)


def test_build_metric_compact_tables_returns_non_empty_merge_and_storage():
    merge_compact, plant_compact, storage_compact, x_end = dynamic_reporting._build_metric_compact_tables(
        _sample_dynamic_results(),
        _sample_plant_results(),
        merge_value_col="flow_kg_per_h",
        plant_value_col="flow_kg_per_h",
        storage_value_col="flow_kg_per_h",
    )

    assert not merge_compact.empty
    assert not plant_compact.empty
    assert not storage_compact.empty
    assert x_end >= 1.0


def test_infer_all_metrics_collects_union_of_inlet_and_output_species():
    metrics = dynamic_reporting._infer_all_metrics(_sample_dynamic_results(), _sample_plant_results())
    names = [m["name"] for m in metrics]

    assert "Flow" in names
    assert "Temperature" in names
    assert "SO2" in names
    assert "NO2" in names


def test_metric_has_changes_detects_change_and_no_change():
    metric = {
        "name": "SO2",
        "merge_col": "final_SO2",
        "plant_col": "inlet_SO2",
        "storage_col": "final_SO2",
        "y_label": "SO2",
    }
    assert dynamic_reporting._metric_has_changes(_sample_dynamic_results(), _sample_plant_results(), metric)

    static_dynamic = [{**r, "final": {"SO2": 1.0}} for r in _sample_dynamic_results()]
    static_plants = [{**r, "inlet_SO2": 1.0} for r in _sample_plant_results()]
    assert not dynamic_reporting._metric_has_changes(static_dynamic, static_plants, metric)


def test_plot_metric_dashboard_writes_output_file(tmp_path: Path):
    output_path = tmp_path / "metric_dashboard.png"
    dynamic_reporting._plot_metric_dashboard(
        _sample_dynamic_results(),
        _sample_plant_results(),
        merge_value_col="flow_kg_per_h",
        plant_value_col="flow_kg_per_h",
        storage_value_col="flow_kg_per_h",
        output_path=str(output_path),
        title="Flow Dashboard",
        subtitle="demo",
        y_label="Flow",
    )
    assert output_path.exists()


def test_plot_all_dynamic_dashboards_writes_graph_files(tmp_path: Path):
    output_path = tmp_path / "dynamic_change_points.png"
    dynamic_reporting.plot_all_dynamic_dashboards(
        _sample_dynamic_results(),
        _sample_plant_results(),
        dynamic_profile={"plant_profiles": {}},
        output_path=str(output_path),
    )

    graph_dir = tmp_path / "graphs"
    assert graph_dir.exists()
    written = {path.name for path in graph_dir.glob("*.png")}
    assert "flow_graph.png" in written
    assert "temperature_graph.png" in written
    assert "predicted_so2.png" in written
    assert "inlet_so2.png" in written
    assert "predicted_no2.png" in written
    assert "inlet_no2.png" in written


def test_plot_dynamic_change_graphs_writes_output_file(tmp_path: Path):
    output_path = tmp_path / "flow_dashboard.png"
    dynamic_reporting.plot_dynamic_change_graphs(
        _sample_dynamic_results(),
        _sample_plant_results(),
        output_path=str(output_path),
    )
    assert output_path.exists()


def test_render_dynamic_reports_delegates_to_plot_all(monkeypatch):
    captured = {}

    def _fake_plot_all(dynamic_results, plant_results, dynamic_profile, output_path):
        captured["dynamic_results"] = dynamic_results
        captured["plant_results"] = plant_results
        captured["dynamic_profile"] = dynamic_profile
        captured["output_path"] = output_path

    monkeypatch.setattr(dynamic_reporting, "plot_all_dynamic_dashboards", _fake_plot_all)

    dynamic_reporting.render_dynamic_reports(
        _sample_dynamic_results(),
        _sample_plant_results(),
        dynamic_profile={"plant_profiles": {"Plant 1": {}}},
        graph_output_path="x.png",
    )

    assert captured["output_path"] == "x.png"
