"""Dynamic merge simulation engine with time-stepping and transport delays.

Provides a generic time-stepping framework for evaluating merge properties over time
with time-varying inlet conditions and transport delays (pipe hold-up times). Supports
any merge evaluation model (e.g., TOCOMO, custom chemistry) via callback function.

Key features:
- Time-stepping from t=0 to duration_days
- Step-hold profile system for time-varying plant inlet conditions
- Transport delay handling: tracks plant and merge histories and delays source arrival
- Topological merge resolution: ensures downstream merges use delayed upstream results
- Per-time-step source collection for reporting (optional)

Note: Flowrate changes are applied instantaneously (no acoustic/speed-of-sound delay).

Main entry point: run_dynamic_merges() accepts a callback function to evaluate each
merge and returns a list of results indexed by (time_step, merge_name).
"""

from copy import deepcopy
from typing import Any, Callable

from backend.merge_support import build_merge_inputs_from_definitions
from backend.merge_support.calculations import _build_merge_input_from_source_states, _build_plant_source_dict
from backend.pipemapping.workflow import build_pipe_graph_with_inputs_interactive
from backend.user_inputs import clear_runtime_input_config, get_input_config, set_runtime_input_config


# Type alias for merge evaluation callback: (merge_name, merge_values, time_days) -> extra_columns_dict
MergeEvaluator = Callable[[str, dict[str, Any], float], dict[str, Any]]
SECONDS_PER_DAY = 86400.0


def _step_hold_value(time_days: float, points: list[tuple[float, float]], default_value: float) -> float:
    """Return a step-held value for time_days from (time_days, value) points.
    
    Implements step-hold (zero-order hold) interpolation: returns the most recent
    point value whose timestamp is <= current time. Used for time-varying profiles.
    
    Args:
        time_days: Current simulation time in days.
        points: List of (time_days, value) tuples in any order.
        default_value: Value to use if no points exist or before first point.
    
    Returns:
        Held value at current time (float).
    """
    # No profile points means we keep the original value.
    if not points:
        return default_value

    # Pick the latest value whose timestamp is <= current time.
    sorted_points = sorted(points, key=lambda item: item[0])
    resolved_value = default_value
    for point_time, point_value in sorted_points:
        if time_days >= point_time:
            resolved_value = float(point_value)
        else:
            break
    return resolved_value


def _build_dynamic_input_config(
    base_input_config: dict[str, object],
    dynamic_profile: dict[str, object],
    time_days: float,
) -> dict[str, object]:
    """Create a per-time-step input config by applying profile overrides.
    
    Modifies plant_inputs in the config based on dynamic_profile specifications,
    using step-hold interpolation for each time-varying parameter (flowrate,
    temperature, stream_phase, inlet_conc). Returns a deep copy so the base
    config remains unchanged.
    
    Args:
        base_input_config: Base configuration dict with plant_inputs list.
        dynamic_profile: Dict with 'plant_profiles' key mapping plant names to
                        profile dicts (keys: flowrate, temperature_celsius,
                        stream_phase, inlet_conc), each with [(time_days, value)].
        time_days: Current simulation time in days.
    
    Returns:
        Modified copy of input_config with interpolated plant inlet conditions.
    """
    # Work on a copy so the base config stays unchanged.
    config = deepcopy(base_input_config)
    # We expect plant_inputs in the config to be a list of plant dictionaries.
    plant_inputs: list[dict[str, object]] = config["plant_inputs"]

    profile_by_plant: dict[str, dict[str, object]] = dynamic_profile.get("plant_profiles", {})
    if not profile_by_plant:
        return config

    # Update each plant with time-based profile values.
    for plant_input in plant_inputs:
        plant_name = str(plant_input["name"])
        plant_profile = profile_by_plant.get(plant_name)
        if not plant_profile:
            continue

        flowrate_profile: list[tuple[float, float]] = plant_profile.get("flowrate", [])
        if flowrate_profile:
            plant_input["flowrate"] = _step_hold_value(
                time_days,
                flowrate_profile,
                float(plant_input["flowrate"]),
            )

        temperature_profile: list[tuple[float, float]] = plant_profile.get("temperature_celsius", [])
        if temperature_profile:
            plant_input["temperature_celsius"] = _step_hold_value(
                time_days,
                temperature_profile,
                float(plant_input["temperature_celsius"]),
            )

        phase_profile: list[tuple[float, str]] = plant_profile.get("stream_phase", [])
        if phase_profile:
            sorted_phase_points = sorted(phase_profile, key=lambda item: item[0])
            current_phase = str(plant_input["stream_phase"])
            for point_time, point_phase in sorted_phase_points:
                if time_days >= point_time:
                    current_phase = str(point_phase)
                else:
                    break
            plant_input["stream_phase"] = current_phase

        inlet_profile_by_species: dict[str, list[tuple[float, float]]] = plant_profile.get("inlet_conc", {})
        if inlet_profile_by_species:
            for species, points in inlet_profile_by_species.items():
                species_key = str(species).strip().upper()
                current_value = float(plant_input["inlet_conc"].get(species_key, 0.0))
                plant_input["inlet_conc"][species_key] = _step_hold_value(
                    time_days,
                    points,
                    current_value,
                )

    return config


def resolve_merge_input_config() -> dict[str, object]:
    """Get a runtime config with merge definitions, prompting once if needed.
    
    Returns existing input config if it has merge_definitions. Otherwise,
    invokes the interactive pipeline mapping wizard to build a config.
    
    Returns:
        Dict with merge_definitions, plant_inputs, and other config keys.
    """
    # Use existing merge definitions when already available.
    input_config = get_input_config()
    if input_config.get("merge_definitions"):
        return input_config

    # Otherwise, ask user once to build a pipeline map.
    _graph, _node_types, generated_config = build_pipe_graph_with_inputs_interactive()
    return generated_config


def _state_pipe_time_days(source_state: dict[str, Any]) -> float:
    """Return pipe time in days for a source state (None means no delay).
    
    Args:
        source_state: State dict with optional 'pipe_time' key (seconds).
    
    Returns:
        Pipe time converted to days, or 0.0 if None or negative.
    """
    pipe_time = source_state.get("pipe_time")
    if pipe_time is None:
        return 0.0
    return max(0.0, float(pipe_time)) / SECONDS_PER_DAY


def _latest_arrived_state(
    history: list[tuple[float, dict[str, Any]]],
    current_time_days: float,
    delay_key: str = "pipe_time",
) -> dict[str, Any]:
    """Pick the newest state that has had enough time to travel through its pipe.
    
    Implements transport delay: finds the most recent (emit_time, state) pair where
    arrival_time = emit_time + delay <= current_time. The delay is read from
    state[delay_key] in seconds (None means no delay). Before the first state
    arrives, returns the oldest state (startup behavior).
    
    Args:
        history: List of (time_days_emitted, state_dict) sorted by emission time.
        current_time_days: Current simulation time in days.
        delay_key: Key in the state dict holding the delay in seconds (default "pipe_time").
    
    Returns:
        The most recent state that has arrived by current_time_days.
    
    Raises:
        ValueError: If history is empty.
    """
    if not history:
        raise ValueError("History is empty. Cannot resolve delayed state.")

    arrived_state: dict[str, Any] | None = None
    for emit_time_days, state in history:
        raw_delay = state.get(delay_key)
        delay_days = 0.0 if raw_delay is None else max(0.0, float(raw_delay)) / SECONDS_PER_DAY
        arrival_time_days = emit_time_days + delay_days
        if arrival_time_days <= current_time_days:
            arrived_state = state
        else:
            break

    # If nothing has arrived yet, use the oldest known state as startup behavior.
    if arrived_state is None:
        return history[0][1]
    return arrived_state


def run_dynamic_merges(
    duration_days: float | None,
    dt_days: float,
    dynamic_profile: dict[str, object],
    evaluate_merge: MergeEvaluator,
    collect_plant_rows: list[dict[str, Any]] | None = None,
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> list[dict[str, Any]]:
    """Run a dynamic merge simulation and delegate each merge state to evaluate_merge.
    
    Main simulation loop that:
    1. Iterates from t=0 to duration_days with dt_days steps
    2. Applies time-varying inlet conditions from dynamic_profile at each step
    3. Tracks plant and merge history with pipe delays
    4. Resolves merges in topological order using delayed source states
    5. Calls evaluate_merge callback for each merge to generate custom output columns
    6. Optionally collects detailed plant state rows
    
    Args:
        duration_days: Simulation end time in days, or None to auto-derive from max pipe time.
        dt_days: Time step size in days (must be positive).
        dynamic_profile: Dict with 'plant_profiles' for time-varying inlet conditions.
        evaluate_merge: Callback(merge_name, merge_values, time_days) -> dict of extra columns.
        collect_plant_rows: If provided, appends detailed plant state rows to this list
                           at each time step.
    
    Returns:
        List of result dicts, one per (time_step, merge_name) pair, with keys:
        time_days, merge_name, sources, temperature_kelvin, temperature_celsius,
        flow_kg_per_h, stream_phase, density_kg_per_m3, pipe_time_s, pipe_time_days,
        pipe_length_m, pipe_diameter_m, plus any columns returned by evaluate_merge.
    
    Raises:
        ValueError: If dt_days <= 0, duration_days cannot be determined, or
                   merge_definitions not found.
    """
    # Time step must be positive.
    if dt_days <= 0:
        raise ValueError("dt_days must be positive.")

    base_input_config = resolve_merge_input_config()
    merge_definitions = base_input_config.get("merge_definitions")
    if not merge_definitions:
        raise ValueError("No merge_definitions found. Build a pipeline map first.")

    # If duration is not set, use the longest merge pipe time.
    baseline_merges = build_merge_inputs_from_definitions(merge_definitions)
    max_pipe_time = max(
        (
            float(merge_values["pipe_time"]) / SECONDS_PER_DAY
            for merge_values in baseline_merges.values()
            if merge_values.get("pipe_time") is not None
        ),
        default=0.0,
    )
    resolved_duration_days = duration_days if duration_days is not None else max_pipe_time
    if resolved_duration_days <= 0:
        raise ValueError(
            "duration_days must be positive or merge pipe times must be configured to derive it."
        )

    dynamic_results: list[dict[str, Any]] = []
    time_days = 0.0

    merge_definition_list: list[dict[str, Any]] = merge_definitions
    plant_count = len(base_input_config["plant_inputs"])

    # Keep per-source history so we can apply transport delay (hold-up time).
    plant_history: dict[int, list[tuple[float, dict[str, Any]]]] = {
        stream_idx: [] for stream_idx in range(plant_count)
    }
    merge_names = [str(item["merge_name"]) for item in merge_definition_list]
    merge_history: dict[str, list[tuple[float, dict[str, Any]]]] = {
        merge_name: [] for merge_name in merge_names
    }
    total_steps = int((resolved_duration_days / dt_days) + 1e-9) + 1
    completed_steps = 0

    if progress_callback is not None:
        progress_callback(0, total_steps, "Preparing dynamic simulation")

    try:
        # Main loop: update inputs -> recalculate merges -> evaluate selected model.
        while time_days <= resolved_duration_days:
            step_config = _build_dynamic_input_config(base_input_config, dynamic_profile, time_days)
            set_runtime_input_config(step_config)
            plant_inputs_step: list[dict[str, Any]] = step_config["plant_inputs"]

            # Build the current plant states and add them to plant history.
            for stream_idx in range(plant_count):
                current_plant_state = _build_plant_source_dict(stream_idx)
                # Flowrate changes propagate instantly (no acoustic delay model).
                current_plant_state["acoustic_pipe_time"] = 0.0
                plant_history[stream_idx].append((time_days, current_plant_state))

                if collect_plant_rows is not None:
                    plant_input = plant_inputs_step[stream_idx]
                    inlet_conc = plant_input.get("inlet_conc", {})
                    collect_plant_rows.append(
                        {
                            "time_days": round(time_days, 5),
                            "plant_name": str(plant_input.get("name", stream_idx)),
                            "temperature_kelvin": current_plant_state["temperature_kelvin"],
                            "temperature_celsius": current_plant_state["temperature_kelvin"] - 273.0,
                            "flow_kg_per_h": current_plant_state["total_massflow"],
                            "stream_phase": current_plant_state["stream_phase"],
                            "density_kg_per_m3": current_plant_state["density_kg_per_m3"],
                            "pipe_time_days": round(
                                float(current_plant_state["pipe_time"]) / SECONDS_PER_DAY,
                                5,
                            ),
                            "pipe_length_m": plant_input.get("pipelength"),
                            "pipe_diameter_m": plant_input.get("pipediameter"),
                            "inlet_O2": float(inlet_conc.get("O2", 0.0)),
                            "inlet_H2O": float(inlet_conc.get("H2O", 0.0)),
                            "inlet_SO2": float(inlet_conc.get("SO2", 0.0)),
                            "inlet_NO2": float(inlet_conc.get("NO2", 0.0)),
                            "inlet_NO": float(inlet_conc.get("NO", 0.0)),
                            "inlet_SO3": float(inlet_conc.get("SO3", 0.0)),
                            "inlet_H2S": float(inlet_conc.get("H2S", 0.0)),
                        }
                    )

            calculated_merges: dict[str, dict[str, Any]] = {}

            # Resolve merges in topological order using delayed source states.
            for merge_definition in merge_definition_list:
                merge_name = str(merge_definition["merge_name"])
                source_dicts: list[dict[str, Any]] = []

                for source_type, source_value in merge_definition["sources"]:
                    if source_type == "plant":
                        plant_idx = int(source_value)
                        current_plant_state = plant_history[plant_idx][-1][1]
                        arrived_plant_state = _latest_arrived_state(
                            plant_history[plant_idx],
                            time_days,
                            "pipe_time",
                        )
                        # Flow changes propagate immediately; other properties still follow pipe delay.
                        source_dicts.append(
                            {
                                **arrived_plant_state,
                                "total_massflow": current_plant_state["total_massflow"],
                            }
                        )
                        continue

                    if source_type == "merge":
                        source_merge_name = str(source_value)
                        current_merge_state = calculated_merges[source_merge_name]
                        arrived_merge_state = _latest_arrived_state(
                            merge_history[source_merge_name],
                            time_days,
                            "pipe_time",
                        )
                        source_dicts.append(
                            {
                                **arrived_merge_state,
                                "source_type": "merge",
                                "source_name": source_merge_name,
                                "total_massflow": current_merge_state["total_massflow"],
                            }
                        )
                        continue

                    raise ValueError(
                        f"Unsupported source type '{source_type}' in merge '{merge_name}'."
                    )

                current_merge_state = _build_merge_input_from_source_states(
                    source_dicts,
                    merge_name=merge_name,
                )
                # Keep this output field for compatibility, but flow delay is disabled.
                current_merge_state["acoustic_pipe_time"] = 0.0
                calculated_merges[merge_name] = current_merge_state
                merge_history[merge_name].append((time_days, current_merge_state))

            # Build one output row per merge for this time step.
            for merge_name, merge_values in calculated_merges.items():
                pipe_time_s = merge_values.get("pipe_time")
                acoustic_pipe_time_s = merge_values.get("acoustic_pipe_time")
                result_row = {
                    "time_days": round(time_days, 5),
                    "merge_name": merge_name,
                    "sources": ", ".join(str(item) for item in merge_values.get("sources", [])),
                    "temperature_kelvin": merge_values["temperature_kelvin"],
                    "temperature_celsius": float(merge_values["temperature_kelvin"]) - 273.0,
                    "flow_kg_per_h": merge_values["total_massflow"],
                    "stream_phase": merge_values["stream_phase"],
                    "density_kg_per_m3": merge_values["density_kg_per_m3"],
                    "pipe_time_s": pipe_time_s,
                    "pipe_time_days": (
                        round(float(pipe_time_s) / SECONDS_PER_DAY, 5)
                        if pipe_time_s is not None
                        else None
                    ),
                    "acoustic_pipe_time_s": acoustic_pipe_time_s,
                    "acoustic_pipe_time_days": (
                        round(float(acoustic_pipe_time_s) / SECONDS_PER_DAY, 5)
                        if acoustic_pipe_time_s is not None
                        else None
                    ),
                    "pipe_length_m": merge_values.get("pipe_length"),
                    "pipe_diameter_m": merge_values.get("pipe_diameter"),
                }
                # Extract inlet ppm_molar concentrations (before chemistry evaluation)
                ppm_molar = merge_values.get("ppm_molar", {})
                if isinstance(ppm_molar, dict):
                    for species, value in ppm_molar.items():
                        species_key = str(species).strip().upper()
                        result_row[f"inlet_{species_key}"] = value
                result_row.update(evaluate_merge(merge_name, merge_values, time_days))
                dynamic_results.append(result_row)

            completed_steps += 1
            if progress_callback is not None:
                progress_callback(
                    completed_steps,
                    total_steps,
                    f"Simulating t={round(time_days, 2)} d",
                )

            time_days += dt_days
    finally:
        # Always restore default runtime config after the simulation.
        clear_runtime_input_config()

    return dynamic_results
