import datetime as dt
import importlib
from pathlib import Path


tocomo_dynamic_model = importlib.import_module("internshipwork.models.dynamic.tocomo_dynamic_model")


class _FixedDatetime:
    @staticmethod
    def now():
        return dt.datetime(2026, 7, 31, 12, 34, 56)


def _redirect_module_file(monkeypatch, module, tmp_path: Path) -> None:
    fake_file = tmp_path / "a" / "b" / "c" / "module.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("# test sentinel\n", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(fake_file))


def test_evaluate_tocomo_merge_maps_supported_species_and_normalizes_output(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_post_model(model_id, input_concentrations, *, temperature_kelvin, pressure_bara):
        captured["model_id"] = model_id
        captured["input_concentrations"] = dict(input_concentrations)
        captured["temperature_kelvin"] = temperature_kelvin
        captured["pressure_bara"] = pressure_bara
        return {"SO2": 1.5, "H2O": 2.0}

    monkeypatch.setattr(tocomo_dynamic_model, "post_model", _fake_post_model)
    monkeypatch.setattr(tocomo_dynamic_model, "get_input_config", lambda: {"p_bara": 12.5})

    result = tocomo_dynamic_model._evaluate_tocomo_merge(
        "Merge 1",
        {
            "ppm_molar": {"SO2": 10.0, "NO2": 5.0, "NO": 99.0},
            "temperature_kelvin": 333.15,
        },
        _time_days=0.0,
    )

    assert captured["model_id"] == "tocomo"
    assert captured["pressure_bara"] == 12.5
    assert captured["temperature_kelvin"] == 333.15
    assert "NO" not in captured["input_concentrations"]
    assert result["final"] == {"SO2": 1.5, "H2O": 2.0}


def test_run_reaction_dynamic_tocomo_orchestrates_progress_and_outputs(monkeypatch, tmp_path: Path):
    _redirect_module_file(monkeypatch, tocomo_dynamic_model, tmp_path)
    monkeypatch.setattr(tocomo_dynamic_model, "datetime", _FixedDatetime)

    progress_events: list[tuple[int, int, str | None]] = []
    report_calls: dict[str, object] = {}
    excel_calls: dict[str, object] = {}

    def _fake_run_dynamic_merges(**kwargs):
        kwargs["collect_plant_rows"].append({"plant_name": "Plant 1", "time_days": 0.0})
        kwargs["progress_callback"](1, 4, None)
        kwargs["progress_callback"](4, 4, "Merge 1")
        return [{"merge_name": "Merge 1", "time_days": 0.0}]

    monkeypatch.setattr(tocomo_dynamic_model, "run_dynamic_merges", _fake_run_dynamic_merges)
    monkeypatch.setattr(
        tocomo_dynamic_model,
        "_evaluate_tocomo_plant",
        lambda *args, **kwargs: {"final": {"SO2": 0.2}},
    )

    def _fake_render(dynamic_results, plant_results, dynamic_profile, graph_output_path):
        report_calls["dynamic_results"] = dynamic_results
        report_calls["plant_results"] = plant_results
        report_calls["dynamic_profile"] = dynamic_profile
        report_calls["graph_output_path"] = graph_output_path

    monkeypatch.setattr(tocomo_dynamic_model, "render_dynamic_reports", _fake_render)

    def _fake_save_excel(dynamic_results, plant_results, session_dir, **kwargs):
        excel_calls["dynamic_results"] = dynamic_results
        excel_calls["plant_results"] = plant_results
        excel_calls["session_dir"] = session_dir
        excel_calls["kwargs"] = kwargs
        return str(Path(session_dir) / "dynamic.xlsx")

    monkeypatch.setattr(tocomo_dynamic_model, "save_dynamic_excel", _fake_save_excel)

    result = tocomo_dynamic_model.run_reaction_dynamic(
        duration_days=1.0,
        dt_days=0.5,
        dynamic_profile={"plant_profiles": {}},
        progress_callback=lambda completed, total, label: progress_events.append((completed, total, label)),
    )

    assert result == [{"merge_name": "Merge 1", "time_days": 0.0}]
    assert any(event[0] == 22 for event in progress_events)
    assert any(event[0] == 90 for event in progress_events)
    assert [event[0] for event in progress_events[-4:]] == [92, 96, 98, 99]
    assert report_calls["graph_output_path"].endswith("_change_points.png")
    assert Path(excel_calls["session_dir"]).exists()
    assert excel_calls["plant_results"][0]["final"] == {"SO2": 0.2}
