import networkx as nx
import pytest

from internshipwork.merge_support import flow

def test_build_merge_inputs_from_definitions(monkeypatch: pytest.MonkeyPatch):
    merge_definitions = [
        {"merge_name": "Merge 1", "sources": [("plant", 0), ("plant", 1)]}
    ]

    def fake_plant_source1(stream1_idx: int):
        return {
            "source_type": "plant",
            "source_name": stream1_idx,
            "temperature_kelvin": 300.0,
            "stream_phase": "gas",
            "total_massflow": 200.0,
            "initial_merge_conc": {"NO2": 1.0},
        }

    def fake_plant_source2(stream2_idx: int):
        return {
            "source_type": "plant",
            "source_name": stream2_idx,
            "temperature_kelvin": 350.0,
            "stream_phase": "gas",
            "total_massflow": 300.0,
            "initial_merge_conc": {"NO2": 5.0},
        }

    def expected_merge_result(source_dicts, merge_name=None):
        return {
            "sources": [item["source_name"] for item in source_dicts],
            "pipe_time": 42.0,
            "temperature_kelvin": 300.0,
            "stream_phase": "gas",
            "total_massflow": float(len(source_dicts) * 100),
            "initial_merge_conc": {"NO2": 1.0},
        }

    def fake_build_plant_source_dict(stream_idx: int):
        if stream_idx == 0:
            return fake_plant_source1(stream_idx)
        if stream_idx == 1:
            return fake_plant_source2(stream_idx)
        raise AssertionError(f"Unexpected stream index: {stream_idx}")

    monkeypatch.setattr(flow, "_build_plant_source_dict", fake_build_plant_source_dict)
    monkeypatch.setattr(flow, "_build_merge_input_from_source_states", expected_merge_result)

    merge_inputs = flow.build_merge_inputs_from_definitions(merge_definitions)
    expected_merge_inputs = {
        "Merge 1": {
            "sources": [0, 1],
            "pipe_time": 42.0,
            "temperature_kelvin": 300.0,
            "stream_phase": "gas",
            "total_massflow": 200.0,
            "initial_merge_conc": {"NO2": 1.0},
        }
    }

    assert merge_inputs == expected_merge_inputs


def test_build_merge_inputs_from_definitions_raises_for_unknown_merge_dependency(
    monkeypatch: pytest.MonkeyPatch,
):
    merge_definitions = [
        {"merge_name": "Merge 2", "sources": [("merge", "Merge 1"), ("plant", 0)]}
    ]

    monkeypatch.setattr(flow, "_build_plant_source_dict", lambda _idx: {})
    monkeypatch.setattr(
        flow,
        "_build_merge_input_from_source_states",
        lambda _source_dicts, merge_name=None: {},
    )

    with pytest.raises(ValueError, match="depends on unknown merge"):
        flow.build_merge_inputs_from_definitions(merge_definitions)


def test_build_merge_inputs_from_definitions_raises_for_unsupported_source_type(
    monkeypatch: pytest.MonkeyPatch,
):
    merge_definitions = [
        {"merge_name": "Merge X", "sources": [("storage", "Storage")]}]

    monkeypatch.setattr(flow, "_build_plant_source_dict", lambda _idx: {})
    monkeypatch.setattr(
        flow,
        "_build_merge_input_from_source_states",
        lambda _source_dicts, merge_name=None: {},
    )

    with pytest.raises(ValueError, match="Unsupported source type"):
        flow.build_merge_inputs_from_definitions(merge_definitions)


def test_build_merge_inputs_from_pipe_graph_delegates(monkeypatch: pytest.MonkeyPatch):
    graph = nx.DiGraph()
    node_types = {}

    expected_definitions = [{"merge_name": "Merge 1", "sources": [("plant", 0), ("plant", 1)]}]
    expected_result = {"Merge 1": {"total_massflow": 200.0}}

    monkeypatch.setattr(flow, "build_merge_definitions", lambda g, n: expected_definitions)
    monkeypatch.setattr(
        flow,
        "build_merge_inputs_from_definitions",
        lambda merge_definitions: expected_result,
    )

    result = flow.build_merge_inputs_from_pipe_graph(graph, node_types)

    assert result == expected_result
