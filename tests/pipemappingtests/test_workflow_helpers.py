import networkx as nx
import pytest

from backend.pipemapping import workflow
from backend.pipemapping.models import WizardState


def test_get_default_plant_input_returns_deep_copy(monkeypatch: pytest.MonkeyPatch):
    config = {
        "plant_inputs": [
            {
                "name": "Plant 1",
                "inlet_conc": {"o2": 2.0},
                "flowrate": 1000.0,
                "temperature_celsius": 25.0,
                "pipelength": 100.0,
                "pipediameter": 0.5,
            }
        ]
    }

    monkeypatch.setattr(workflow, "get_input_config", lambda: config)

    plant_input = workflow._get_default_plant_input("Plant 1")
    plant_input["inlet_conc"]["o2"] = 999.0

    assert config["plant_inputs"][0]["inlet_conc"]["o2"] == 2.0


def test_get_default_plant_input_raises_for_missing_name(monkeypatch: pytest.MonkeyPatch):
    config = {
        "plant_inputs": [
            {
                "name": "Plant 1",
                "inlet_conc": {"o2": 2.0},
                "flowrate": 1000.0,
                "temperature_celsius": 25.0,
                "pipelength": 100.0,
                "pipediameter": 0.5,
            }
        ]
    }

    monkeypatch.setattr(workflow, "get_input_config", lambda: config)

    with pytest.raises(ValueError, match="Plant 'Missing Plant' is missing"):
        workflow._get_default_plant_input("Missing Plant")


def test_get_default_merge_pipe_input_returns_deep_copy(monkeypatch: pytest.MonkeyPatch):
    config = {
        "merge_pipe_inputs": {
            "Merge 1": {"pipelength": 100.0, "pipediameter": 0.4}
        }
    }

    monkeypatch.setattr(workflow, "get_input_config", lambda: config)

    merge_input = workflow._get_default_merge_pipe_input("Merge 1")
    merge_input["pipelength"] = 999.0

    assert config["merge_pipe_inputs"]["Merge 1"]["pipelength"] == 100.0


def test_get_default_merge_pipe_input_raises_for_missing_name(monkeypatch: pytest.MonkeyPatch):
    config = {
        "merge_pipe_inputs": {
            "Merge 1": {"pipelength": 100.0, "pipediameter": 0.4}
        }
    }

    monkeypatch.setattr(workflow, "get_input_config", lambda: config)

    with pytest.raises(ValueError, match="Merge 'Merge X' is missing"):
        workflow._get_default_merge_pipe_input("Merge X")


def test_build_input_config_for_pipe_graph_normalizes_order(monkeypatch: pytest.MonkeyPatch):
    graph = nx.DiGraph()
    graph.add_node("Plant B", plant_index=1)
    graph.add_node("Plant A", plant_index=0)
    graph.add_node("Merge 1")
    graph.add_edge("Plant A", "Merge 1")
    graph.add_edge("Plant B", "Merge 1")

    node_types = {
        "Plant A": "plant",
        "Plant B": "plant",
        "Merge 1": "merge",
    }

    plant_inputs = [
        {"name": "placeholder-a", "flowrate": 1.0},
        {"name": "placeholder-b", "flowrate": 2.0},
    ]
    merge_pipe_inputs = {"Merge 1": {"pipelength": 750.0, "pipediameter": 0.4}}

    captured: dict[str, object] = {}

    def fake_build_input_config(
        config_plant_inputs: list[dict[str, object]],
        config_merge_pipe_inputs: dict[str, dict[str, float]],
        config_p_bara: float,
    ) -> dict[str, object]:
        captured["plants"] = config_plant_inputs
        captured["merges"] = config_merge_pipe_inputs
        captured["p_bara"] = config_p_bara
        return {
            "plant_inputs": config_plant_inputs,
            "merge_pipe_inputs": config_merge_pipe_inputs,
            "p_bara": config_p_bara,
        }

    monkeypatch.setattr(workflow, "build_input_config", fake_build_input_config)

    result = workflow.build_input_config_for_pipe_graph(
        graph,
        node_types,
        plant_inputs,
        merge_pipe_inputs,
        pressure_bara=10.0,
    )

    normalized_names = [item["name"] for item in captured["plants"]]  # type: ignore[index]
    assert normalized_names == ["Plant A", "Plant B"]
    assert list(captured["merges"].keys()) == ["Merge 1"]  # type: ignore[union-attr]
    assert captured["p_bara"] == 10.0
    assert result["p_bara"] == 10.0


def test_build_input_config_for_pipe_graph_raises_when_merge_input_missing():
    graph = nx.DiGraph()
    graph.add_node("Plant 1", plant_index=0)
    graph.add_node("Merge 1")
    graph.add_edge("Plant 1", "Merge 1")

    node_types = {
        "Plant 1": "plant",
        "Merge 1": "merge",
    }

    plant_inputs = [{"name": "Plant 1", "flowrate": 1.0}]

    with pytest.raises(ValueError, match="Merge 'Merge 1' is missing pipe inputs"):
        workflow.build_input_config_for_pipe_graph(
            graph,
            node_types,
            plant_inputs,
            merge_pipe_inputs={},
            pressure_bara=10.0,
        )


def test_commit_merge_updates_graph_state(monkeypatch: pytest.MonkeyPatch):
    state = WizardState()
    state.graph.add_node("Plant 1")
    state.graph.add_node("Plant 2")
    state.available_nodes.update({"Plant 1", "Plant 2"})

    refresh_calls = {"count": 0}

    def fake_refresh(_preview: tuple[object, object], _state: WizardState) -> None:
        refresh_calls["count"] += 1

    monkeypatch.setattr(workflow, "_refresh_preview", fake_refresh)

    workflow._commit_merge(state, (object(), object()), "Merge 1", ["Plant 1", "Plant 2"])

    assert "Merge 1" in state.graph
    assert state.node_types["Merge 1"] == "merge"
    assert ("Plant 1", "Merge 1") in state.graph.edges
    assert ("Plant 2", "Merge 1") in state.graph.edges
    assert state.merge_history == ["Merge 1"]
    assert "Merge 1" in state.available_nodes
    assert state.merge_index == 2
    assert refresh_calls["count"] == 1


def test_remove_last_merge_removes_state_and_node(monkeypatch: pytest.MonkeyPatch):
    state = WizardState()
    state.graph.add_node("Merge 1")
    state.node_types["Merge 1"] = "merge"
    state.available_nodes.add("Merge 1")
    state.merge_history.append("Merge 1")
    state.merge_pipe_inputs["Merge 1"] = {"pipelength": 1.0, "pipediameter": 0.2}
    state.merge_index = 3

    refresh_calls = {"count": 0}

    def fake_refresh(_preview: tuple[object, object], _state: WizardState) -> None:
        refresh_calls["count"] += 1

    monkeypatch.setattr(workflow, "_refresh_preview", fake_refresh)

    removed = workflow._remove_last_merge(state, (object(), object()))

    assert removed is True
    assert "Merge 1" not in state.graph
    assert "Merge 1" not in state.node_types
    assert "Merge 1" not in state.available_nodes
    assert "Merge 1" not in state.merge_pipe_inputs
    assert state.merge_history == []
    assert state.merge_index == 2
    assert refresh_calls["count"] == 1


def test_normalize_map_name_preserves_spaces_between_words():
    assert workflow._normalize_map_name("  North Sea Export  ") == "North Sea Export"


def test_normalize_map_name_removes_unsupported_characters():
    assert workflow._normalize_map_name("Map! #1") == "Map 1"
