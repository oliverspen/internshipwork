from contextvars import ContextVar
from copy import deepcopy
import json
from pathlib import Path


PLANT_SPECIES = ("O2", "H2O", "SO2", "NO2", "NO", "SO3", "H2S")
VALID_STREAM_PHASES = {"gas", "liquid"}

INPUT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "input_config.json"

# ContextVar gives each web request (async task or thread) its own isolated config.
_runtime_input_config: ContextVar[dict[str, object] | None] = ContextVar(
    "_runtime_input_config", default=None
)


def _validate_inputs(
    config_plant_inputs: list[dict[str, object]],
    config_merge_pipe_inputs: dict[str, dict[str, float]],
    config_p_bara: float,
    config_storage_name: str = "Storage",
) -> None:
    if not config_plant_inputs:
        raise ValueError("plant_inputs must contain at least one plant.")

    phases_seen: set[str] = set()

    for plant_input in config_plant_inputs:
        # Note: Plants may have missing species concentrations (they default to 0.0)
        # No validation needed for missing species

        stream_phase = str(plant_input.get("stream_phase", "")).strip().lower()
        if stream_phase not in VALID_STREAM_PHASES:
            raise ValueError(
                f"Plant '{plant_input['name']}' must set stream_phase to one of "
                f"{sorted(VALID_STREAM_PHASES)}."
            )
        phases_seen.add(stream_phase)

        if plant_input["flowrate"] <= 0:
            raise ValueError(f"Plant '{plant_input['name']}' must have a positive flowrate.")
        if plant_input["pipelength"] <= 0:
            raise ValueError(f"Plant '{plant_input['name']}' must have a positive pipelength.")
        if plant_input["pipediameter"] <= 0:
            raise ValueError(f"Plant '{plant_input['name']}' must have a positive pipediameter.")

    if len(phases_seen) > 1:
        raise ValueError(
            "Only single-phase systems are allowed. "
            f"Found mixed phases in plant inputs: {sorted(phases_seen)}"
        )

    for merge_name, merge_input in config_merge_pipe_inputs.items():
        if merge_input["pipelength"] <= 0:
            raise ValueError(f"Merge '{merge_name}' must have a positive pipelength.")
        if merge_input["pipediameter"] <= 0:
            raise ValueError(f"Merge '{merge_name}' must have a positive pipediameter.")

    if config_p_bara <= 0:
        raise ValueError("p_bara must be positive.")

    if not str(config_storage_name).strip():
        raise ValueError("storage_name must be a non-empty string.")


def build_input_config(
    config_plant_inputs: list[dict[str, object]] | None = None,
    config_merge_pipe_inputs: dict[str, dict[str, float]] | None = None,
    config_p_bara: float | None = None,
    config_merge_definitions: list[dict[str, object]] | None = None,
    config_storage_name: str | None = None,
) -> dict[str, object]:
    """Build one normalized input configuration dict."""
    resolved_plant_inputs = deepcopy(config_plant_inputs if config_plant_inputs is not None else plant_inputs)
    resolved_merge_pipe_inputs = deepcopy(
        config_merge_pipe_inputs if config_merge_pipe_inputs is not None else merge_pipe_inputs
    )
    resolved_p_bara = float(config_p_bara if config_p_bara is not None else p_bara)
    resolved_storage_name = str(
        config_storage_name if config_storage_name is not None else storage_name
    ).strip() or "Storage"

    _validate_inputs(
        resolved_plant_inputs,
        resolved_merge_pipe_inputs,
        resolved_p_bara,
        resolved_storage_name,
    )
    config: dict[str, object] = {
        "plant_inputs": resolved_plant_inputs,
        "merge_pipe_inputs": resolved_merge_pipe_inputs,
        "p_bara": resolved_p_bara,
        "storage_name": resolved_storage_name,
    }

    if config_merge_definitions is not None:
        config["merge_definitions"] = deepcopy(config_merge_definitions)

    return config


def get_input_config() -> dict[str, object]:
    """Return the active input configuration used by derived variables."""
    config = _runtime_input_config.get()
    if config is not None:
        return deepcopy(config)
    return build_input_config()


def set_runtime_input_config(input_config: dict[str, object]) -> None:
    """Override the default file-backed inputs for the current Python session."""
    validated = build_input_config(
        config_plant_inputs=input_config.get("plant_inputs"),
        config_merge_pipe_inputs=input_config.get("merge_pipe_inputs"),
        config_p_bara=input_config.get("p_bara"),
        config_merge_definitions=input_config.get("merge_definitions"),
        config_storage_name=str(input_config.get("storage_name") or "Storage"),
    )
    # Preserve keys that build_input_config does not handle.
    for key in ("pipeline_map_name", "pipeline_map_png_path"):
        if key in input_config:
            validated[key] = input_config[key]
    _runtime_input_config.set(validated)


def clear_runtime_input_config() -> None:
    """Remove any runtime override and fall back to the file-backed defaults."""
    _runtime_input_config.set(None)


def _load_file_backed_inputs() -> None:
    """Load default inputs from input_config.json."""
    global plant_inputs
    global merge_pipe_inputs
    global p_bara
    global storage_name

    if not INPUT_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing required input config file: {INPUT_CONFIG_PATH}")

    with INPUT_CONFIG_PATH.open("r", encoding="utf-8") as json_file:
        raw_config = json.load(json_file)

    if "plant_inputs" not in raw_config:
        raise KeyError("input_config.json is missing required key 'plant_inputs'.")
    if "merge_pipe_inputs" not in raw_config:
        raise KeyError("input_config.json is missing required key 'merge_pipe_inputs'.")
    if "p_bara" not in raw_config:
        raise KeyError("input_config.json is missing required key 'p_bara'.")

    loaded_plant_inputs = raw_config["plant_inputs"]
    loaded_merge_pipe_inputs = raw_config["merge_pipe_inputs"]
    loaded_p_bara = raw_config["p_bara"]
    loaded_storage_name = str(raw_config.get("storage_name", "Storage")).strip() or "Storage"

    _validate_inputs(
        loaded_plant_inputs,
        loaded_merge_pipe_inputs,
        loaded_p_bara,
        loaded_storage_name,
    )

    plant_inputs = loaded_plant_inputs
    merge_pipe_inputs = loaded_merge_pipe_inputs
    p_bara = loaded_p_bara
    storage_name = loaded_storage_name


def reload_input_config() -> None:
    """Reload file-backed defaults from input_config.json."""
    _load_file_backed_inputs()


_load_file_backed_inputs()
_validate_inputs(plant_inputs, merge_pipe_inputs, p_bara, storage_name)

