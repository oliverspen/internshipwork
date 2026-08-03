from pathlib import Path

import pandas as pd

from backend.output.excel_export import save_dynamic_excel


def test_save_dynamic_excel_storage_uses_time_days(tmp_path: Path):
    dynamic_results = [
        {
            "time_days": 0.0,
            "merge_name": "Merge 1",
            "sources": "0",
            "temperature_celsius": 20.0,
            "flow_kg_per_h": 100.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "pipe_time_days": 40.0,
            "final": {"no2": 1.5},
        },
        {
            "time_days": 2.0,
            "merge_name": "Merge 1",
            "sources": "0",
            "temperature_celsius": 21.0,
            "flow_kg_per_h": 200.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.1,
            "pipe_time_days": 40.0,
            "final": {"no2": 2.5},
        },
    ]

    plant_results = [
        {
            "time_days": 0.0,
            "plant_name": "Plant 1",
            "temperature_celsius": 20.0,
            "flow_kg_per_h": 100.0,
            "stream_phase": "gas",
            "density_kg_per_m3": 1.0,
            "inlet_no2": 1.5,
            "final": {"no2": 1.0},
        }
    ]

    excel_path = save_dynamic_excel(
        dynamic_results,
        plant_results,
        tmp_path,
        model_used="TOCOMO dynamic",
    )

    storage_df = pd.read_excel(excel_path, sheet_name="Storage")

    assert "model" in storage_df.columns
    assert storage_df["model"].tolist() == ["TOCOMO dynamic", "TOCOMO dynamic"]
    assert "time_days" in storage_df.columns
    assert "arrival_time_days" not in storage_df.columns
    assert storage_df["time_days"].tolist() == [0.0, 2.0]
