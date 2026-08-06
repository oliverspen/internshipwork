import pytest

from backend.merge_support import flow

def test_build_merge_inputs_from_plant_def(monkeypatch: pytest.MonkeyPatch):
    merge_definitions = [
        {"merge_name": "Merge 1", "sources": [("plant", 0), ("plant", 1)]}
    ]

    source = {"source_name": 0, "temperature_kelvin": 300.0, "stream_phase": "gas", "total_massflow": 200.0, "initial_merge_conc": {"NO2": 1.0}}
    result = {"temperature_kelvin": 300.0, "stream_phase": "gas", "total_massflow": 200.0, "initial_merge_conc": {"NO2": 1.0}}

    monkeypatch.setattr(flow, "_build_plant_source_dict", lambda _idx: source)
    monkeypatch.setattr(flow, "_build_merge_input_from_source_states", lambda _dicts, merge_name=None: result)

    assert flow.build_merge_inputs_from_definitions(merge_definitions) == {"Merge 1": result}


def test_build_merge_inputs_from_definitions_passes_resolved_merge_as_source(monkeypatch: pytest.MonkeyPatch):
    # Merge 2 depends on Merge 1; verifies the resolved merge is correctly passed as a source dict.
    merge_definitions = [
        {"merge_name": "Merge 1", "sources": [("plant", 0)]},
        {"merge_name": "Merge 2", "sources": [("merge", "Merge 1")]},
    ]

    merge1_result = {"temperature_kelvin": 310.0, "stream_phase": "gas", "total_massflow": 500.0, "initial_merge_conc": {"CO2": 2.0}}
    merge2_result = {"temperature_kelvin": 315.0, "stream_phase": "gas", "total_massflow": 500.0, "initial_merge_conc": {"CO2": 2.0}}
    captured_source_dicts = []

    def fake_build_merge_input(source_dicts, merge_name=None):
        captured_source_dicts.append((merge_name, source_dicts))
        return merge1_result if merge_name == "Merge 1" else merge2_result

    monkeypatch.setattr(flow, "_build_plant_source_dict", lambda _idx: {})
    monkeypatch.setattr(flow, "_build_merge_input_from_source_states", fake_build_merge_input)

    result = flow.build_merge_inputs_from_definitions(merge_definitions)

    assert result == {"Merge 1": merge1_result, "Merge 2": merge2_result}
    _merge1_name, merge2_sources = captured_source_dicts[1]
    assert merge2_sources[0] == {
        "source_type": "merge",
        "source_name": "Merge 1",
        "temperature_kelvin": merge1_result["temperature_kelvin"],
        "total_massflow": merge1_result["total_massflow"],
        "stream_phase": merge1_result["stream_phase"],
        "initial_merge_conc": merge1_result["initial_merge_conc"],
    }
