from backend.pipemapping.models import Stage, WizardState


def test_wizard_state_defaults_are_initialized():
    state = WizardState()

    assert state.stage is Stage.PLANT_SELECTION
    assert state.graph.number_of_nodes() == 0
    assert state.node_types == {}
    assert state.available_nodes == set()
    assert state.plant_names == []
    assert state.merge_history == []
    assert state.plant_inputs == []
    assert state.merge_pipe_inputs == {}
