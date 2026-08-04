"""Interactive pipeline mapping workflow with wizard-style progression.

Orchestrates the step-by-step wizard that guides users through:
1. Selecting active plants
2. Defining merge operations
3. Connecting to storage

Builds a directed graph, collects associated input data, and persists
named pipeline map configurations.
"""

from copy import deepcopy
from pathlib import Path
import re
from typing import Any
from tkinter import messagebox

import networkx as nx

from backend.pipemapping.dialogs import (
    ask_non_empty_with_back,
    ask_select_nodes,
    ask_yes_no_with_back,
    init_dialog_root,
)
from backend.pipemapping.models import BackRequested, Stage, UserCancelled, WizardState
from backend.pipemapping.visuals import draw_pipe_graph, init_live_preview, save_pipe_graph_png, update_live_preview
from backend.pipemapping.dev_pipeline_map import register_dev_pipeline_map
from backend.user_inputs import INPUT_CONFIG_PATH, build_input_config, get_input_config, set_runtime_input_config
from backend.merge_support.topology import build_merge_definitions


_NORWEGIAN = str.maketrans({'æ': 'ae', 'Æ': 'ae', 'ø': 'oe', 'Ø': 'oe', 'å': 'aa', 'Å': 'aa'})


def _normalize_map_name(raw_name: str) -> str:
    """Normalize user-provided map name to valid identifier format.
    
    Preserves spaces between words while removing unsupported characters.
    
    Args:
        raw_name: User-provided pipeline map name
        
    Returns:
        Normalized name suitable for use as a config identifier
    """
    transliterated = raw_name.translate(_NORWEGIAN)
    normalized = re.sub(r"[^A-Za-z0-9 _-]+", "", transliterated.strip())
    normalized = re.sub(r"\s+", " ", normalized).strip(" _-")
    return normalized or "pipeline map"


def _refresh_preview(preview: tuple[object, object], state: WizardState) -> None:
    """Update the live preview with the current graph state."""
    update_live_preview(preview, state.graph, state.node_types)


def _remove_last_merge(state: WizardState, preview: tuple[object, object]) -> bool:
    """Remove the most recently added merge from graph and state (back-navigation).
    
    Args:
        state: Current wizard state
        preview: Live preview figure/axes tuple
        
    Returns:
        True if a merge was removed, False if merge history is empty
    """
    if not state.merge_history:
        return False

    # Remove from all tracking structures
    last_merge = state.merge_history.pop()
    state.merge_pipe_inputs.pop(last_merge, None)
    if last_merge in state.graph:
        state.graph.remove_node(last_merge)
    state.node_types.pop(last_merge, None)
    state.available_nodes.discard(last_merge)
    state.merge_index = max(1, state.merge_index - 1)
    _refresh_preview(preview, state)
    return True


def _remove_last_plant(state: WizardState, preview: tuple[object, object]) -> bool:
    """Remove the most recently added plant from graph and state (back-navigation).
    
    Args:
        state: Current wizard state
        preview: Live preview figure/axes tuple
        
    Returns:
        True if a plant was removed, False if plant history is empty
    """
    if not state.plant_names:
        return False

    # Remove from all tracking structures
    last_plant = state.plant_names.pop()
    if state.plant_inputs:
        state.plant_inputs.pop()
    if last_plant in state.graph:
        state.graph.remove_node(last_plant)
    state.node_types.pop(last_plant, None)
    state.available_nodes.discard(last_plant)
    state.plant_index = max(0, state.plant_index - 1)
    _refresh_preview(preview, state)
    return True


def _reset_plants(state: WizardState, preview: tuple[object, object]) -> None:
    """Remove all currently selected plants before applying a new active selection.
    
    Args:
        state: Current wizard state
        preview: Live preview figure/axes tuple
    """
    while _remove_last_plant(state, preview):
        pass


def _prompt_merge_definition(
    state: WizardState,
    available_merge_names: set[str],
) -> tuple[str, list[str]] | None:
    """Prompt user to select a merge name and its source streams.
    
    A merge combines two or more existing nodes (plants or other merges) into
    a single output stream.
    
    Args:
        state: Current wizard state
        available_merge_names: Set of unused merge names from config
        
    Returns:
        Tuple of (merge_name, source_list) or None if cancelled/back pressed
    """
    if len(state.available_nodes) < 2:
        messagebox.showerror(
            "Pipe Mapping",
            "A merge needs at least 2 existing nodes. Add more plants first.",
        )
        return None

    if not available_merge_names:
        messagebox.showinfo(
            "Pipe Mapping",
            f"No unused merge names remain in {INPUT_CONFIG_PATH}.",
        )
        return None

    while True:
        try:
            selected_merge_names = ask_select_nodes(
                "What is the name of this merge node?",
                available_merge_names,
                min_sources=1,
                allow_back=True,
            )
        except BackRequested:
            return None

        if len(selected_merge_names) != 1:
            messagebox.showerror(
                "Pipe Mapping",
                "Please select exactly one merge from the configured list.",
            )
            continue

        merge_name = selected_merge_names[0]

        try:
            # A merge can only use nodes that already exist in the graph
            sources = ask_select_nodes(
                f"Which streams merge into '{merge_name}'?",
                state.available_nodes,
                min_sources=2,
                allow_back=True,
            )
        except BackRequested:
            continue

        return merge_name, sources


def _get_default_plant_input(plant_name: str) -> dict[str, Any]:
    """Get plant input config from default settings by plant name.
    
    Args:
        plant_name: Name of the plant to look up
        
    Returns:
        Plant input dict (temperature, flow, concentrations, etc.)
        
    Raises:
        ValueError: If plant not found in input config
    """
    default_config = get_input_config()
    default_plants = default_config["plant_inputs"]
    plant_by_name = {
        str(plant_input["name"]): plant_input
        for plant_input in default_plants
        if "name" in plant_input
    }

    if plant_name not in plant_by_name:
        available_names = ", ".join(sorted(plant_by_name)) or "(none)"
        raise ValueError(
            f"Plant '{plant_name}' is missing from {INPUT_CONFIG_PATH}. "
            f"Available plant names: {available_names}."
        )

    plant_input = deepcopy(plant_by_name[plant_name])
    plant_input["name"] = plant_name
    return plant_input


def _get_default_merge_pipe_input(merge_name: str) -> dict[str, float]:
    """Get merge pipe input config (diameter, length) from default settings by merge name.
    
    Args:
        merge_name: Name of the merge to look up
        
    Returns:
        Merge pipe input dict with diameter and length
        
    Raises:
        ValueError: If merge not found in input config
    """
    default_config = get_input_config()
    default_merge_inputs = default_config["merge_pipe_inputs"]
    if merge_name not in default_merge_inputs:
        available_names = ", ".join(sorted(default_merge_inputs)) or "(none)"
        raise ValueError(
            f"Merge '{merge_name}' is missing from {INPUT_CONFIG_PATH}. "
            f"Available merge names: {available_names}."
        )

    return deepcopy(default_merge_inputs[merge_name])


def build_input_config_for_pipe_graph(
    graph: nx.DiGraph,
    node_types: dict[str, str],
    plant_inputs: list[dict[str, Any]],
    merge_pipe_inputs: dict[str, dict[str, float]],
    pressure_bara: float,
    storage_name: str | None = None,
) -> dict[str, object]:
    """Build final input config from completed graph and collected input data.
    
    Normalizes plant and merge ordering to match graph structure, validates
    consistency, and builds merge definitions.
    
    Args:
        graph: Completed pipeline topology graph
        node_types: Node type mapping
        plant_inputs: List of plant input configs
        merge_pipe_inputs: Dict of merge pipe input configs
        pressure_bara: System pressure in bar(a)
        
    Returns:
        Complete input configuration ready for TOCOMO simulation
        
    Raises:
        ValueError: If graph and input data are inconsistent
    """
    # Sort plants by their original index to ensure consistent ordering
    plant_nodes = sorted(
        (
            (graph.nodes[node_name].get("plant_index"), node_name)
            for node_name in graph.nodes
            if node_types.get(node_name) == "plant"
        ),
        key=lambda item: item[0],
    )

    if len(plant_nodes) != len(plant_inputs):
        raise ValueError("Plant input count does not match the number of plant nodes in the graph.")

    # Update plant names to match graph while preserving input data
    normalized_plant_inputs: list[dict[str, Any]] = []
    for expected_index, (plant_index, plant_name) in enumerate(plant_nodes):
        if plant_index != expected_index:
            raise ValueError(f"Plant '{plant_name}' has unexpected plant_index '{plant_index}'.")

        plant_input = deepcopy(plant_inputs[expected_index])
        plant_input["name"] = plant_name
        normalized_plant_inputs.append(plant_input)

    # Keep merges in topological order (upstream before downstream)
    merge_names = [
        node_name for node_name in nx.topological_sort(graph) if node_types.get(node_name) == "merge"
    ]
    normalized_merge_pipe_inputs: dict[str, dict[str, float]] = {}
    for merge_name in merge_names:
        if merge_name not in merge_pipe_inputs:
            raise ValueError(f"Merge '{merge_name}' is missing pipe inputs.")
        normalized_merge_pipe_inputs[merge_name] = deepcopy(merge_pipe_inputs[merge_name])

    # Build the final configuration
    build_kwargs: dict[str, Any] = {
        "config_plant_inputs": normalized_plant_inputs,
        "config_merge_pipe_inputs": normalized_merge_pipe_inputs,
        "config_p_bara": pressure_bara,
    }
    if storage_name is not None:
        build_kwargs["config_storage_name"] = storage_name

    config = build_input_config(**build_kwargs)

    # Add topology information (which nodes connect to which)
    config["merge_definitions"] = build_merge_definitions(graph, node_types)
    return config


def _commit_merge(
    state: WizardState,
    preview: tuple[object, object],
    merge_name: str,
    sources: list[str],
) -> None:
    """Add a validated merge to the graph and update preview.
    
    Args:
        state: Current wizard state
        preview: Live preview figure/axes tuple
        merge_name: Name of the merge node
        sources: List of source node names feeding this merge
    """
    # Add merge node with metadata for ordering
    state.graph.add_node(merge_name, merge_order=state.merge_index)
    state.node_types[merge_name] = "merge"
    
    # Add edges from all sources to this merge
    for source in sources:
        state.graph.add_edge(source, merge_name)
    
    # Update tracking
    state.available_nodes.add(merge_name)
    state.merge_history.append(merge_name)
    state.merge_index += 1
    _refresh_preview(preview, state)


def build_pipe_graph_with_inputs_interactive() -> tuple[nx.DiGraph, dict[str, str], dict[str, object]]:
    #build a pipe graph with the wizard and return the matching config. 
    init_dialog_root()
    state = WizardState()
    # Keep the preview open while the user builds the graph.
    preview = init_live_preview()
    _refresh_preview(preview, state)

    # Read the plant, merge, and pressure values from the JSON-backed config.
    default_config = get_input_config()

    messagebox.showinfo(
        "Pipe Mapping",
        "Create your pipeline map:\n"
        f"1) Select active plants from {INPUT_CONFIG_PATH}\n"
        "2) Define merges\n"
        f"3) Process inputs are loaded from {INPUT_CONFIG_PATH}",
    )
    requested_map_name = ask_non_empty_with_back("Enter a name for this pipeline map:")
    map_name = _normalize_map_name(requested_map_name)

    configured_plant_inputs = default_config["plant_inputs"]
    available_plant_names = [
        str(plant_input["name"])
        for plant_input in configured_plant_inputs
        if "name" in plant_input
    ]
    if not available_plant_names:
        raise ValueError(f"No plants are configured in {INPUT_CONFIG_PATH}.")

    configured_merge_inputs = default_config["merge_pipe_inputs"]
    available_merge_names = {
        str(merge_name)
        for merge_name in configured_merge_inputs
        if str(merge_name).lower() != "default"
    }

    while True:
        if state.stage is Stage.PLANT_SELECTION:
            try:
                selected_plants = ask_select_nodes(
                    "Which plants are active in this pipeline?",
                    set(available_plant_names),
                    min_sources=1,
                    allow_back=False,
                )
            except BackRequested:
                continue

            _reset_plants(state, preview)
            for plant_name in selected_plants:
                plant_input = _get_default_plant_input(plant_name)
                state.graph.add_node(plant_name)
                # Save the original plant order on the node.
                state.graph.nodes[plant_name]["plant_index"] = state.plant_index
                state.node_types[plant_name] = "plant"
                state.available_nodes.add(plant_name)
                state.plant_names.append(plant_name)
                state.plant_inputs.append(plant_input)
                state.plant_index += 1

            _refresh_preview(preview, state)
            state.stage = Stage.MERGES
            continue

        if state.stage is Stage.MERGES:
            unused_merge_names = available_merge_names - set(state.merge_history)
            if not unused_merge_names:
                state.stage = Stage.STORAGE
                continue

            merge_prompt = (
                "Do any streams mix together?"
                if not state.merge_history
                else "Do any other streams mix together?"
            )
            try:
                want_merge = ask_yes_no_with_back(merge_prompt)
            except BackRequested:
                if _remove_last_merge(state, preview):
                    continue
                state.stage = Stage.PLANT_SELECTION
                continue

            if not want_merge:
                state.stage = Stage.STORAGE
                continue

            merge_definition = _prompt_merge_definition(state, unused_merge_names)
            if merge_definition is None:
                continue

            merge_name, sources = merge_definition
            merge_pipe_input = _get_default_merge_pipe_input(merge_name)

            _commit_merge(state, preview, merge_name, sources)
            state.merge_pipe_inputs[merge_name] = merge_pipe_input
            continue

        if state.stage is Stage.STORAGE:
            storage_name = str(default_config.get("storage_name") or "Storage")
            try:
                # Storage is the endpoint
                storage_sources = ask_select_nodes(
                    f"Which stream or streams connect to {storage_name}?",
                    state.available_nodes,
                    min_sources=1,
                    allow_back=True,
                )
            except BackRequested:
                # Going back from storage should undo one merge when possible.
                # Otherwise, fall back to plant selection.
                if _remove_last_merge(state, preview):
                    state.stage = Stage.MERGES
                else:
                    state.stage = Stage.PLANT_SELECTION
                continue

            if storage_name in state.graph:
                state.graph.remove_node(storage_name)

            state.graph.add_node(storage_name)
            state.node_types[storage_name] = "storage"
            for source in storage_sources:
                state.graph.add_edge(source, storage_name)
            _refresh_preview(preview, state)

            # Build the final config from the finished graph and the loaded inputs.
            input_config = build_input_config_for_pipe_graph(
                state.graph,
                state.node_types,
                state.plant_inputs,
                state.merge_pipe_inputs,
                float(default_config["p_bara"]),
                storage_name=str(default_config.get("storage_name") or "Storage"),
            )
            set_runtime_input_config(input_config)
            save_pipe_graph_png(state.graph, state.node_types, Path.cwd() / f"pipeline_map_{map_name}.png")
            register_dev_pipeline_map(
                map_name=map_name,
                merge_definitions=input_config["merge_definitions"],
                merge_pipe_inputs=input_config["merge_pipe_inputs"],
                storage_name=str(input_config.get("storage_name") or storage_name),
            )
            input_config["pipeline_map_name"] = map_name
            input_config["pipeline_map_png_path"] = str((Path.cwd() / f"pipeline_map_{map_name}.png").resolve())
            return state.graph, state.node_types, input_config


def build_pipe_graph_interactive() -> tuple[nx.DiGraph, dict[str, str]]:
    """Build pipeline graph with wizard, returning only graph and node types.
    
    Config is saved globally via set_runtime_input_config().
    """
    graph, node_types, _input_config = build_pipe_graph_with_inputs_interactive()
    return graph, node_types


def run_pipemapping() -> None:
    """Interactive pipeline mapping wizard with final visualization and storage.
    
    Shows the wizard, displays created edges, and saves pipeline map PNG.
    """
    init_dialog_root()
    try:
        graph, node_types, input_config = build_pipe_graph_with_inputs_interactive()
    except UserCancelled:
        return

    output_png = str(input_config.get("pipeline_map_png_path", (Path.cwd() / "pipeline_map.png").resolve()))
    map_name = str(input_config.get("pipeline_map_name", "pipeline_map"))

    # Show the final list of edges before opening the graph window
    edges_text = "\n".join(f"- {source} -> {target}" for source, target in graph.edges())
    messagebox.showinfo(
        "Pipe Mapping",
        f"Pipeline map name: {map_name}\n\n"
        "Created edges:\n"
        f"{edges_text if edges_text else '(none)'}\n\n"
        f"Saved PNG:\n{output_png}",
    )

    draw_pipe_graph(graph, node_types)


# Backward-compatible alias
pipemap = run_pipemapping