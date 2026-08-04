"""Pipeline graph visualization and layout algorithms.

Provides functions to compute node positions (layered DAG or spring layout),
render graphs to matplotlib, and save pipeline diagrams as PNG files.
"""

from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx


def layered_or_spring_layout(
    graph: nx.DiGraph,
    previous_positions: dict[str, tuple[float, float]] | None = None,
) -> dict[str, tuple[float, float]]:
    """Compute a layout for the pipeline graph.
    
    Prefers a left-to-right layered layout for acyclic graphs (cleaner visual),
    falling back to spring layout for graphs with cycles.
    
    Args:
        graph: NetworkX directed graph to lay out
        
    Returns:
        Dict mapping node IDs to (x, y) position tuples
    """
    if graph.number_of_nodes() == 0:
        return {}

    # For DAGs, compute layered layout based on topological depth
    if nx.is_directed_acyclic_graph(graph):
        nodes_in_order = list(nx.topological_sort(graph))

        # Earliest-depth placement keeps existing nodes stable when adding downstream merges.
        depth: dict[str, int] = {}
        for node in nodes_in_order:
            preds = list(graph.predecessors(node))
            depth[node] = max((depth[p] + 1 for p in preds), default=0)

        # Group nodes by their depth (layer)
        grouped: dict[int, list[str]] = defaultdict(list)
        for node, level in depth.items():
            grouped[level].append(node)

        def _node_sort_key(node: str) -> tuple[float, int, int, str]:
            if previous_positions and node in previous_positions:
                # Preserve relative vertical ordering from previous frame to reduce jumping.
                return (-float(previous_positions[node][1]), 9, 999999, node)

            node_type = str(graph.nodes[node].get("node_type", ""))
            if not node_type:
                node_type = "plant" if "plant_index" in graph.nodes[node] else "merge"
            type_rank = {"plant": 0, "merge": 1, "storage": 2}.get(node_type, 3)

            if node_type == "plant":
                order = int(graph.nodes[node].get("plant_index", 999999))
            elif node_type == "merge":
                order = int(graph.nodes[node].get("merge_order", 999999))
            else:
                order = 999999
            return (0.0, type_rank, order, node)

        for level in grouped:
            grouped[level].sort(key=_node_sort_key)

        def _build_positions(horizontal_gap: float, vertical_gap: float) -> dict[str, tuple[float, float]]:
            positions: dict[str, tuple[float, float]] = {}
            for level in sorted(grouped):
                nodes_at_level = grouped[level]
                count = len(nodes_at_level)
                spread = vertical_gap * (count - 1)
                start = spread / 2
                for idx, node in enumerate(nodes_at_level):
                    y = 0.0 if count == 1 else (start - idx * vertical_gap)
                    positions[node] = (float(level) * horizontal_gap, float(y))
            return positions

        def _has_overlap(positions: dict[str, tuple[float, float]]) -> bool:
            # Approximate overlap check in layout units for the current node size/font.
            x_min_gap = 1.05
            y_min_gap = 1.05
            nodes = list(positions.keys())
            for i in range(len(nodes)):
                x1, y1 = positions[nodes[i]]
                for j in range(i + 1, len(nodes)):
                    x2, y2 = positions[nodes[j]]
                    if abs(x1 - x2) < x_min_gap and abs(y1 - y2) < y_min_gap:
                        return True
            return False

        # Default compact layout.
        positions = _build_positions(horizontal_gap=1.0, vertical_gap=1.0)

        # Only expand spacing when actual overlap is detected.
        if _has_overlap(positions):
            positions = _build_positions(horizontal_gap=1.5, vertical_gap=1.35)

        return positions
    
    # For cyclic graphs, use spring layout (force-directed)
    return nx.spring_layout(graph, seed=42)


def draw_pipe_graph_on_axis(
    graph: nx.DiGraph,
    node_types: dict[str, str],
    ax: plt.Axes,
    title: str,
) -> None:
    """Draw pipeline graph on existing matplotlib axis with type-based coloring.
    
    Args:
        graph: NetworkX directed graph to visualize
        node_types: Dict mapping node IDs to type strings ("plant", "merge", "storage", etc.)
        ax: Matplotlib axis to draw on
        title: Title for the graph visualization
    """
    # Define colors for each node type
    colors = {
        "plant": "forestgreen",
        "merge": "darkorange",
        "storage": "steelblue",
        "junction": "dimgray",
    }

    node_colors = [colors.get(node_types.get(node, "junction"), "dimgray") for node in graph.nodes()]
    previous_positions = getattr(ax, "_last_positions", None)
    positions = layered_or_spring_layout(graph, previous_positions=previous_positions)
    setattr(ax, "_last_positions", positions)

    ax.clear()
    if graph.number_of_nodes() > 0:
        labels = {node: graph.nodes[node].get("label", node) for node in graph.nodes()}
        # Redraw from scratch each time (live preview updates after every wizard step)
        nx.draw(
            graph,
            pos=positions,
            labels=labels,
            node_size=2400,
            node_color=node_colors,
            edge_color="black",
            font_size=9,
            font_color="white",
            width=2,
            arrows=True,
            ax=ax,
        )
    ax.set_title(title)
    ax.axis("off")


def init_live_preview() -> tuple[plt.Figure, plt.Axes]:
    """Create and show a non-blocking live preview window for wizard visualization.
    
    Returns:
        Tuple of (figure, axes) for updating during wizard steps
    """
    # Interactive mode keeps preview responsive while Tk dialogs are open
    plt.ion()
    fig, ax = plt.subplots(figsize=(18, 10))
    try:
        fig.canvas.manager.set_window_title("Pipeline Map Preview")
    except Exception:
        pass
    try:
        # On TkAgg/Qt backends, maximize window so full graph remains visible.
        manager = fig.canvas.manager
        window = getattr(manager, "window", None)
        if window is not None and hasattr(window, "state"):
            window.state("zoomed")
        elif hasattr(manager, "full_screen_toggle"):
            manager.full_screen_toggle()
    except Exception:
        pass
    fig.tight_layout()
    fig.show()
    return fig, ax


def update_live_preview(
    preview: tuple[plt.Figure, plt.Axes],
    graph: nx.DiGraph,
    node_types: dict[str, str],
) -> None:
    """Refresh the live preview with current graph state.
    
    Args:
        preview: Tuple of (figure, axes) from init_live_preview()
        graph: Current pipeline graph
        node_types: Node type mapping
    """
    fig, ax = preview
    # If user closes preview manually, stop updating instead of failing
    if not plt.fignum_exists(fig.number):
        return
    draw_pipe_graph_on_axis(graph, node_types, ax, "Interactive Pipeline Map (Live)")
    fig.canvas.draw_idle()
    fig.canvas.flush_events()
    plt.pause(0.01)


def draw_pipe_graph(graph: nx.DiGraph, node_types: dict[str, str]) -> None:
    """Render a pipeline graph with type-based coloring.
    
    Shows a blocking window with the finished graph (called after wizard exits).
    
    Args:
        graph: Pipeline topology graph
        node_types: Node type mapping
    """
    fig, ax = plt.subplots(figsize=(18, 10))
    draw_pipe_graph_on_axis(graph, node_types, ax, "Interactive Pipeline Map")
    fig.tight_layout()
    plt.show()


def save_pipe_graph_png(
    graph: nx.DiGraph,
    node_types: dict[str, str],
    output_path: str | Path = "pipeline_map.png",
) -> Path:
    """Save the pipeline graph as a PNG file.
    
    Args:
        graph: Pipeline topology graph
        node_types: Node type mapping
        output_path: Output PNG file path
        
    Returns:
        Resolved Path to the saved PNG file
    """
    output = Path(output_path)
    fig, ax = plt.subplots(figsize=(10, 5))
    draw_pipe_graph_on_axis(graph, node_types, ax, "Interactive Pipeline Map")
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output.resolve()
