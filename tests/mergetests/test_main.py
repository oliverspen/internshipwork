import importlib


merge_main = importlib.import_module("internshipwork.merge_support.__main__")


def test_build_config_with_merge_metrics_enriches_known_merges(monkeypatch):
    input_config = {
        "merge_definitions": [{"merge_name": "Merge 1", "sources": [("plant", 0), ("plant", 1)]}],
        "merge_pipe_inputs": {
            "Merge 1": {"pipediameter": 0.5, "pipelength": 1000.0},
            "Unchanged": {"pipediameter": 0.3, "pipelength": 500.0},
        },
    }

    monkeypatch.setattr(
        merge_main,
        "build_merge_inputs_from_definitions",
        lambda _definitions: {
            "Merge 1": {
                "flow_speed": 4.2,
                "pipe_time": 238.1,
                "total_massflow": 1234.5,
                "stream_phase": "gas",
                "density_kg_per_m3": 1.98,
            },
            "Merge not in inputs": {
                "flow_speed": 9.9,
                "pipe_time": 1.0,
                "total_massflow": 10.0,
                "stream_phase": "liquid",
                "density_kg_per_m3": 999.0,
            },
        },
    )

    result = merge_main._build_config_with_merge_metrics(input_config)

    assert result is not input_config
    assert result["merge_pipe_inputs"]["Merge 1"]["merge_flow_speed"] == 4.2
    assert result["merge_pipe_inputs"]["Merge 1"]["merge_pipe_time"] == 238.1
    assert result["merge_pipe_inputs"]["Merge 1"]["merge_total_massflow"] == 1234.5
    assert result["merge_pipe_inputs"]["Merge 1"]["merge_stream_phase"] == "gas"
    assert result["merge_pipe_inputs"]["Merge 1"]["merge_density_kg_per_m3"] == 1.98
    assert "merge_flow_speed" not in result["merge_pipe_inputs"]["Unchanged"]


def test_build_config_with_merge_metrics_does_not_mutate_original(monkeypatch):
    input_config = {
        "merge_definitions": [{"merge_name": "Merge 1", "sources": [("plant", 0), ("plant", 1)]}],
        "merge_pipe_inputs": {
            "Merge 1": {"pipediameter": 0.5, "pipelength": 1000.0},
        },
    }

    monkeypatch.setattr(
        merge_main,
        "build_merge_inputs_from_definitions",
        lambda _definitions: {
            "Merge 1": {
                "flow_speed": 4.2,
                "pipe_time": 238.1,
                "total_massflow": 1234.5,
                "stream_phase": "gas",
                "density_kg_per_m3": 1.98,
            }
        },
    )

    merge_main._build_config_with_merge_metrics(input_config)

    assert "merge_flow_speed" not in input_config["merge_pipe_inputs"]["Merge 1"]
    assert "merge_pipe_time" not in input_config["merge_pipe_inputs"]["Merge 1"]


def test_run_merge_support_prints_expected_output(monkeypatch, capsys):
    config = {
        "merge_definitions": [],
        "merge_pipe_inputs": {},
    }
    enriched = {"ok": True}
    captured = {}

    monkeypatch.setattr(merge_main, "get_input_config", lambda: config)
    monkeypatch.setattr(merge_main, "_build_config_with_merge_metrics", lambda _cfg: enriched)
    monkeypatch.setattr(merge_main, "pprint", lambda value: captured.setdefault("value", value))

    merge_main.run_merge_support()
    output = capsys.readouterr().out

    assert "merge_support loaded." in output
    assert "Active input config (from input_config.json unless overridden):" in output
    assert "Available functions:" in output
    assert "- build_merge_definitions" in output
    assert "- build_merge_input" in output
    assert "- build_merge_inputs_from_definitions" in output
    assert "- build_merge_inputs_from_pipe_graph" in output
    assert captured["value"] == enriched
