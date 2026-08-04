import importlib
import json
from pathlib import Path

import pytest


user_inputs = importlib.import_module("internshipwork.user_inputs")


def _valid_plant(name: str = "Plant A") -> dict[str, object]:
    return {
        "name": name,
        "flowrate": 100.0,
        "temperature_celsius": 20.0,
        "stream_phase": "gas",
        "pipediameter": 0.5,
        "pipelength": 100.0,
        "inlet_conc": {"SO2": 1.0},
    }


def _valid_merge_inputs() -> dict[str, dict[str, float]]:
    return {"Merge 1": {"pipelength": 10.0, "pipediameter": 0.2}}


def test_validate_inputs_rejects_invalid_stream_phase():
    bad_plant = _valid_plant()
    bad_plant["stream_phase"] = "solid"

    with pytest.raises(ValueError, match="stream_phase"):
        user_inputs._validate_inputs([bad_plant], _valid_merge_inputs(), 5.0, "Storage")


def test_validate_inputs_rejects_non_positive_merge_pipe_values():
    bad_merge = {"Merge 1": {"pipelength": 10.0, "pipediameter": 0.0}}

    with pytest.raises(ValueError, match="positive pipediameter"):
        user_inputs._validate_inputs([_valid_plant()], bad_merge, 5.0, "Storage")


def test_build_input_config_deep_copies_and_normalizes_storage_name():
    source_plant = _valid_plant()
    source_merge = _valid_merge_inputs()
    source_defs = [{"merge_name": "Merge 1", "sources": [("plant", 0)]}]

    config = user_inputs.build_input_config(
        config_plant_inputs=[source_plant],
        config_merge_pipe_inputs=source_merge,
        config_p_bara=6.5,
        config_merge_definitions=source_defs,
        config_storage_name="  Tank  ",
    )

    source_plant["flowrate"] = 999.0
    source_merge["Merge 1"]["pipediameter"] = 9.9

    assert config["plant_inputs"][0]["flowrate"] == 100.0
    assert config["merge_pipe_inputs"]["Merge 1"]["pipediameter"] == 0.2
    assert config["storage_name"] == "Tank"
    assert config["merge_definitions"] == source_defs


def test_set_runtime_input_config_preserves_extra_keys_and_clear_resets():
    payload = {
        "plant_inputs": [_valid_plant()],
        "merge_pipe_inputs": _valid_merge_inputs(),
        "p_bara": 9.0,
        "storage_name": "Storage X",
        "pipeline_map_name": "Map A",
        "pipeline_map_png_path": "map.png",
    }

    user_inputs.set_runtime_input_config(payload)
    try:
        active = user_inputs.get_input_config()
        assert active["pipeline_map_name"] == "Map A"
        assert active["pipeline_map_png_path"] == "map.png"
        assert active["p_bara"] == 9.0
    finally:
        user_inputs.clear_runtime_input_config()

    restored = user_inputs.get_input_config()
    assert "pipeline_map_name" not in restored


def test_reload_input_config_from_file_updates_globals(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "input_config.json"
    config_path.write_text(
        json.dumps(
            {
                "plant_inputs": [_valid_plant("Plant B")],
                "merge_pipe_inputs": _valid_merge_inputs(),
                "p_bara": 7.25,
                "storage_name": "  Depot  ",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(user_inputs, "INPUT_CONFIG_PATH", config_path)
    user_inputs.reload_input_config()

    assert user_inputs.p_bara == 7.25
    assert user_inputs.storage_name == "Depot"
    assert user_inputs.plant_inputs[0]["name"] == "Plant B"


def test_reload_input_config_raises_for_missing_file(monkeypatch, tmp_path: Path):
    missing = tmp_path / "missing_input_config.json"
    monkeypatch.setattr(user_inputs, "INPUT_CONFIG_PATH", missing)

    with pytest.raises(FileNotFoundError, match="Missing required input config file"):
        user_inputs.reload_input_config()


def test_reload_input_config_raises_for_missing_required_key(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "input_config.json"
    config_path.write_text(
        json.dumps(
            {
                "plant_inputs": [_valid_plant()],
                "merge_pipe_inputs": _valid_merge_inputs(),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(user_inputs, "INPUT_CONFIG_PATH", config_path)

    with pytest.raises(KeyError, match="p_bara"):
        user_inputs.reload_input_config()
