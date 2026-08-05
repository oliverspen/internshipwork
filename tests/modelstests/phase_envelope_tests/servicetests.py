from backend.models.phase_envelope import service


def test_to_mole_fractions():
    raw_conc = {"initial_merge_conc": {
            "CO2": 90.0,
            "N2": 7.0,
            "O2": 3.0,
        }}

    result = service._to_mole_fractions(raw_conc)

    assert result["CO2"] == 0.9
    assert result["N2"] == 0.07
    assert result["O2"] == 0.03
    assert sum(result.values()) == 1.0

def test_build_fluid():
    temperature_kelvin = 298.15
    pressure_bara = 10.0
    mole_fractions = {
        "CO2": 0.9,
        "N2": 0.07,
        "O2": 0.03,
    }

    fluid = service._build_fluid(temperature_kelvin, pressure_bara, mole_fractions)

    assert fluid.getTemperature() == 298.15
    assert fluid.getPressure() == 10.0
    assert fluid.getNumberOfComponents() == len(mole_fractions)


def test_build_storage_state_weighted_mix_from_plants_arrange_act_assert():
    source_rows = [
        (
            "plant",
            0,
            {
                "initial_merge_conc": {"CO2": 0.8, "N2": 0.2},
                "temperature_kelvin": 200.0,
                "density_kg_per_m3": 900.0,
                "total_massflow": 30.0,
                "stream_phase": "liquid",
            },
        ),
        (
            "plant",
            1,
            {
                "initial_merge_conc": {"CO2": 0.5, "N2": 0.5},
                "temperature_kelvin": 300.0,
                "density_kg_per_m3": 1000.0,
                "total_massflow": 70.0,
                "stream_phase": "liquid",
            },
        ),
    ]
    result = service._build_storage_state(source_rows=source_rows, merge_definitions=[])
    assert result is not None
    assert result["total_massflow"] == 100.0
    assert result["initial_merge_conc"]["CO2"] == 0.59
    assert result["initial_merge_conc"]["N2"] == 0.41
    assert result["temperature_kelvin"] == 270.0
    assert result["density_kg_per_m3"] == 970.0
    assert result["stream_phase"] == "liquid"


def test_build_storage_state_uses_only_terminal_merges_arrange_act_assert():
    source_rows = [
        (
            "merge",
            "M1",
            {
                "initial_merge_conc": {"CO2": 0.75, "N2": 0.25},
                "temperature_kelvin": 310.0,
                "density_kg_per_m3": 5.0,
                "total_massflow": 40.0,
                "stream_phase": "gas",
            },
        ),
        (
            "merge",
            "M2",
            {
                "initial_merge_conc": {"CO2": 0.60, "N2": 0.40},
                "temperature_kelvin": 330.0,
                "density_kg_per_m3": 3.0,
                "total_massflow": 60.0,
                "stream_phase": "gas",
            },
        ),
    ]
    merge_definitions = [
        {"merge_name": "M1", "sources": [("plant", 0), ("plant", 1)]},
        {"merge_name": "M2", "sources": [("merge", "M1"), ("plant", 2)]},
    ]
    result = service._build_storage_state(
        source_rows=source_rows,
        merge_definitions=merge_definitions,
    )
    assert result is not None
    assert result["total_massflow"] == 60.0
    assert result["initial_merge_conc"]["CO2"] == 0.60
    assert result["initial_merge_conc"]["N2"] == 0.40
    assert result["temperature_kelvin"] == 330.0
    assert result["density_kg_per_m3"] == 3.0
    assert result["stream_phase"] == "gas"

def test_plot_single_node_phase_envelope_output(tmp_path, monkeypatch):
    class FakeOperations:
        def __init__(self, _fluid):
            self._data = {
                "dewT": [280.0, 290.0, 300.0],
                "dewP": [8.0, 10.0, 12.0],
                "bubT": [282.0, 292.0, 302.0],
                "bubP": [9.0, 11.0, 13.0],
            }

        def calcPTphaseEnvelope(self):
            return None

        def get(self, key):
            return self._data[key]

    monkeypatch.setattr(service, "_to_mole_fractions", lambda _state: {"CO2": 1.0})
    monkeypatch.setattr(service, "_build_fluid", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(service, "operations_cls", FakeOperations)

    source_state = {
        "initial_merge_conc": {"CO2": 1.0},
        "temperature_kelvin": 298.15,
    }

    output_path = service._plot_single_node_phase_envelope(
        source_type="plant",
        source_name="Plant A/1",
        source_state=source_state,
        pressure_bara=10.0,
        output_dir=tmp_path,
    )

    assert output_path == tmp_path / "Plant_A1_phase_envelope.png"
    assert output_path.exists()
    assert output_path.suffix == ".png"


    def fake_build_fluid(temp_k, p_bara, mole_fractions):
        seen["temp_k"] = temp_k
        seen["p_bara"] = p_bara
        seen["mole_fractions"] = mole_fractions
        return object()

    monkeypatch.setattr(service, "_to_mole_fractions", lambda _state: {"CO2": 1.0})
    monkeypatch.setattr(service, "_build_fluid", fake_build_fluid)
    monkeypatch.setattr(service, "operations_cls", FakeOperations)

    source_state = {
        "initial_merge_conc": {"CO2": 1.0},
    }

    output_path = service._plot_single_node_phase_envelope(
        source_type="merge",
        source_name="M1",
        source_state=source_state,
        pressure_bara=15.0,
        output_dir=tmp_path,
    )

    assert seen["temp_k"] == 298.15
    assert seen["p_bara"] == 15.0
    assert seen["mole_fractions"] == {"CO2": 1.0}
    assert output_path == tmp_path / "M1_phase_envelope.png"
    assert output_path.exists()


def test_plot_single_node_phase_envelope_handles_non_finite_arrays(tmp_path, monkeypatch):
    class FakeOperations:
        def __init__(self, _fluid):
            self._data = {
                "dewT": [float("nan"), float("nan")],
                "dewP": [float("nan"), float("nan")],
                "bubT": [float("nan"), float("nan")],
                "bubP": [float("nan"), float("nan")],
            }

        def calcPTphaseEnvelope(self):
            return None

        def get(self, key):
            return self._data[key]

    monkeypatch.setattr(service, "_to_mole_fractions", lambda _state: {"CO2": 1.0})
    monkeypatch.setattr(service, "_build_fluid", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(service, "operations_cls", FakeOperations)

    source_state = {
        "initial_merge_conc": {"CO2": 1.0},
        "temperature_kelvin": 298.15,
    }

    output_path = service._plot_single_node_phase_envelope(
        source_type="storage",
        source_name="Storage Node",
        source_state=source_state,
        pressure_bara=10.0,
        output_dir=tmp_path,
    )

    assert output_path == tmp_path / "Storage_Node_phase_envelope.png"
    assert output_path.exists()
    assert output_path.suffix == ".png"

def test_skips_plot_failures(capsys, tmp_path, monkeypatch):
    source_rows = [
        ("plant", 0, {"initial_merge_conc": {"CO2": 1.0}, "temperature_kelvin": 300.0}),
        ("merge", "M1", {"initial_merge_conc": {"CO2": 1.0}, "temperature_kelvin": 300.0}),
    ]

    def fake_plot_single_node_phase_envelope(*, source_type, source_name, source_state, pressure_bara, output_dir):
        if source_type == "plant":
            raise RuntimeError("plot failed")
        return output_dir / f"{source_type}_{source_name}.png"

    monkeypatch.setattr(service, "_plot_single_node_phase_envelope", fake_plot_single_node_phase_envelope)
    monkeypatch.setattr(
        service,
        "_build_storage_state",
        lambda source_rows, merge_definitions: {
            "initial_merge_conc": {"CO2": 1.0},
            "temperature_kelvin": 300.0,
            "density_kg_per_m3": 1.0,
            "total_massflow": 10.0,
            "stream_phase": "gas",
        },
    )

    result = service.generate_phase_envelopes_for_network(
        source_rows=source_rows,
        merge_definitions=[{"merge_name": "M1", "sources": [("plant", 0)]}],
        storage_name="Storage",
        pressure_bara=10.0,
        output_dir=tmp_path,
        plant_names={0: "Plant A"},
    )

    assert result == [
        tmp_path / "merge_M1.png",
        tmp_path / "storage_Storage.png",
    ]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""




