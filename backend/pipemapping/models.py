"""Data models for the pipeline mapping wizard.

Defines exception types for wizard control flow and the WizardState dataclass
that tracks the interactive graph building process.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import networkx as nx


class UserCancelled(Exception):
    """Raised when the user cancels an interactive dialog or wizard step."""


class BackRequested(Exception):
    """Raised when the user requests to return to the previous wizard step."""


class Stage(Enum):
    """Wizard progression stages in forward order.
    
    The wizard progresses through these stages sequentially:
    1. PLANT_SELECTION: Choose which configured plants are active
    2. MERGES: Define merge operations (optional)
    3. STORAGE: Connect final stream(s) to storage endpoint
    """

    PLANT_SELECTION = "plant_selection"
    MERGES = "merges"
    STORAGE = "storage"


@dataclass
class WizardState:
    """Complete state of the pipeline mapping wizard.
    
    Tracks the live graph being built, node types, user selections, and
    associated input data through all wizard stages.
    """

    # Graph representation of the pipeline topology
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    
    # Maps node IDs to their types ("plant", "merge", "storage", "junction")
    node_types: dict[str, str] = field(default_factory=dict)
    
    # Nodes that can be used as sources for new merges or storage connections
    available_nodes: set[str] = field(default_factory=set)
    
    # History of plant names in order of selection (for back-navigation)
    plant_names: list[str] = field(default_factory=list)
    
    # History of merge names in order of creation (for back-navigation)
    merge_history: list[str] = field(default_factory=list)
    
    # Plant input configs aligned with graph order (temperature, flow, etc.)
    plant_inputs: list[dict[str, Any]] = field(default_factory=list)
    
    # Merge pipe input configs (diameter, length) indexed by merge name
    merge_pipe_inputs: dict[str, dict[str, float]] = field(default_factory=dict)
    
    # Counter tracking the next plant index for node labeling
    plant_index: int = 0
    
    # Counter tracking the next merge index for node labeling
    merge_index: int = 1
    
    # Current wizard stage (used for state machine progression)
    stage: Stage = Stage.PLANT_SELECTION
