"""Named pipeline map persistence and auto-loading.

Stores and retrieves named pipeline map configurations (merge definitions and
pipe inputs) to/from this module file between sessions. Provides a dev/sandbox
mode for reusing pre-defined pipeline topologies.
"""

from copy import deepcopy
from pathlib import Path
from pprint import pformat

from backend.user_inputs import get_input_config, set_runtime_input_config

# BEGIN AUTO-GENERATED PIPELINE MAPS
AUTO_GENERATED_PIPELINE_MAPS: dict[str, dict[str, object]] = {}
ACTIVE_AUTO_PIPELINE_MAP: str | None = 'realisticinput'
# END AUTO-GENERATED PIPELINE MAPS


def _all_dev_pipeline_maps() -> dict[str, dict[str, object]]:
    """Get a deep copy of all stored pipeline maps."""
    return deepcopy(AUTO_GENERATED_PIPELINE_MAPS)


def get_available_dev_pipeline_map_names() -> list[str]:
    """Return all available dev pipeline map names sorted alphabetically."""
    return sorted(_all_dev_pipeline_maps().keys())


def get_default_dev_pipeline_map_name() -> str | None:
    """Return the active auto pipeline map name, if one is configured."""
    return ACTIVE_AUTO_PIPELINE_MAP


def select_dev_pipeline_map_name(configured_name: str | None = None) -> str:
    """Resolve the pipeline map name from config or prompt user interactively.
    
    Args:
        configured_name: If provided, validate and return this name
        
    Returns:
        Selected pipeline map name
        
    Raises:
        ValueError: If no maps are available or configured name is invalid
    """
    available_names = get_available_dev_pipeline_map_names()
    default_name = get_default_dev_pipeline_map_name()

    if not available_names:
        raise ValueError(
            "USE_DEV_PIPELINE_MAP is enabled, but no saved pipeline maps were found. "
            "Build a named map first using RUN_MODE='pipemapping'."
        )

    if configured_name is not None:
        if configured_name not in available_names:
            available_text = ", ".join(available_names)
            raise ValueError(
                f"Unknown DEV_PIPELINE_MAP_NAME '{configured_name}'. "
                f"Available maps: {available_text}"
            )
        return configured_name

    print("Available dev pipeline maps:")
    for idx, map_name in enumerate(available_names, start=1):
        suffix = " (default)" if map_name == default_name else ""
        print(f"{idx}. {map_name}{suffix}")

    if default_name is None:
        selected = input("Select pipeline map name: ").strip()
    else:
        selected = input(f"Select pipeline map name (press Enter for '{default_name}'): ").strip()
        if selected == "":
            return default_name

    if selected not in available_names:
        available_text = ", ".join(available_names)
        raise ValueError(f"Unknown pipeline map '{selected}'. Available maps: {available_text}")
    return selected


def _persist_generated_pipeline_maps() -> None:
    """Persist AUTO_GENERATED_PIPELINE_MAPS and ACTIVE_AUTO_PIPELINE_MAP to file.
    
    Updates the module file between the marker comments to persist new maps.
    """
    start_marker = "# BEGIN AUTO-GENERATED PIPELINE MAPS"
    end_marker = "# END AUTO-GENERATED PIPELINE MAPS"
    module_path = Path(__file__)
    file_text = module_path.read_text(encoding="utf-8")

    start_idx = file_text.find(start_marker)
    end_idx = file_text.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise RuntimeError("Missing auto-generated pipeline map markers in dev_pipeline_map.py")

    end_idx += len(end_marker)
    replacement_block = (
        f"{start_marker}\n"
        f"AUTO_GENERATED_PIPELINE_MAPS: dict[str, dict[str, object]] = "
        f"{pformat(AUTO_GENERATED_PIPELINE_MAPS, width=100)}\n"
        f"ACTIVE_AUTO_PIPELINE_MAP: str | None = {ACTIVE_AUTO_PIPELINE_MAP!r}\n"
        f"{end_marker}"
    )
    updated = file_text[:start_idx] + replacement_block + file_text[end_idx:]
    module_path.write_text(updated, encoding="utf-8")


def register_dev_pipeline_map(
    map_name: str,
    merge_definitions: list[dict[str, object]],
    merge_pipe_inputs: dict[str, dict[str, float]],
    selected_plant_indexes: list[int] | None = None,
    storage_name: str = "Storage",
    node_positions: dict[str, dict[str, float]] | None = None,
) -> None:
    """Store a new named pipeline map and set it as the active default.
    
    Persists to this module file for reuse across sessions.
    
    Args:
        map_name: Name to save the map under
        merge_definitions: List of merge definition dicts
        merge_pipe_inputs: Dict of merge pipe input configs
    """
    global ACTIVE_AUTO_PIPELINE_MAP
    AUTO_GENERATED_PIPELINE_MAPS[map_name] = {
        "merge_definitions": deepcopy(merge_definitions),
        "merge_pipe_inputs": deepcopy(merge_pipe_inputs),
        "selected_plant_indexes": [int(idx) for idx in (selected_plant_indexes or [])],
        "storage_name": (storage_name or "Storage").strip() or "Storage",
        "node_positions": deepcopy(node_positions) if node_positions else {},
    }
    ACTIVE_AUTO_PIPELINE_MAP = map_name
    _persist_generated_pipeline_maps()


def update_dev_pipeline_map_node_positions(
    map_name: str,
    node_positions: dict[str, dict[str, float]],
) -> None:
    """Update only saved node positions for an existing map and persist it."""
    if map_name not in AUTO_GENERATED_PIPELINE_MAPS:
        raise KeyError(f"Unknown dev pipeline map '{map_name}'.")
    AUTO_GENERATED_PIPELINE_MAPS[map_name]["node_positions"] = deepcopy(node_positions)
    _persist_generated_pipeline_maps()


def delete_dev_pipeline_map(map_name: str) -> None:
    """Delete a saved pipeline map and persist the updated map set.

    If the deleted map was the active default, pick the next available map
    alphabetically; if none remain, clear the active default.
    """
    global ACTIVE_AUTO_PIPELINE_MAP

    if map_name not in AUTO_GENERATED_PIPELINE_MAPS:
        raise KeyError(f"Unknown dev pipeline map '{map_name}'.")

    del AUTO_GENERATED_PIPELINE_MAPS[map_name]

    if ACTIVE_AUTO_PIPELINE_MAP == map_name:
        remaining_names = sorted(AUTO_GENERATED_PIPELINE_MAPS.keys())
        ACTIVE_AUTO_PIPELINE_MAP = remaining_names[0] if remaining_names else None

    _persist_generated_pipeline_maps()


def apply_dev_pipeline_map(map_name: str | None = None) -> None:
    """Inject dev merge definitions into runtime config for this session.
    
    Loads a named pipeline map and updates the global input config with its
    merge definitions and pipe inputs, allowing TOCOMO to use the pre-defined topology.
    
    Args:
        map_name: If provided, use this specific map (defaults to ACTIVE_AUTO_PIPELINE_MAP)
        
    Raises:
        ValueError: If no active map is configured
        KeyError: If map_name is not found
    """
    selected_name = map_name if map_name is not None else ACTIVE_AUTO_PIPELINE_MAP
    available_maps = _all_dev_pipeline_maps()
    if selected_name is None:
        raise ValueError(
            "No active dev pipeline map is configured. "
            "Build and save a named pipeline map first."
        )
    if selected_name not in available_maps:
        available_names = ", ".join(sorted(available_maps))
        raise KeyError(
            f"Unknown dev pipeline map '{selected_name}'. Available map names: {available_names}."
        )

    selected_map = available_maps[selected_name]
    input_config = deepcopy(get_input_config())
    input_config["merge_definitions"] = deepcopy(selected_map["merge_definitions"])
    selected_plant_indexes = [
        int(idx)
        for idx in (selected_map.get("selected_plant_indexes") or [])
        if isinstance(idx, int) or (isinstance(idx, str) and idx.isdigit())
    ]

    # Start with the stored dev map pipe inputs, then let input_config.json override
    # any matching merge keys so that edits to the JSON file are always picked up.
    merged_pipe_inputs = deepcopy(selected_map["merge_pipe_inputs"])
    for merge_name, json_pipe_input in input_config.get("merge_pipe_inputs", {}).items():
        if merge_name in merged_pipe_inputs:
            merged_pipe_inputs[merge_name] = deepcopy(json_pipe_input)
    input_config["merge_pipe_inputs"] = merged_pipe_inputs

    if not input_config["merge_definitions"] and selected_plant_indexes:
        input_config["plant_inputs"] = [
            deepcopy(plant_input)
            for idx, plant_input in enumerate(input_config.get("plant_inputs", []))
            if idx in set(selected_plant_indexes)
        ]

    input_config["pipeline_map_name"] = selected_name
    input_config["storage_name"] = str(selected_map.get("storage_name") or "Storage")
    set_runtime_input_config(input_config)
