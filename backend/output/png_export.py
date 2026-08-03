"""Static PNG map export for TOCOMO results."""

from pathlib import Path
from typing import Any

import matplotlib

# Use a headless backend so PNG export is safe in worker threads and API servers.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from backend.pipemapping.visuals import layered_or_spring_layout


def save_annotated_png_map(
    graph: nx.DiGraph,
    node_types: dict[str, str],
    node_labels: dict[str, str],
    output_path: str | Path,
) -> Path:
    """Save an annotated PNG map with TOCOMO species values displayed below each node."""
    colors = {
        "plant": "#2d8a4e",
        "merge": "#d97706",
        "storage": "#2563eb",
        "junction": "#6b7280",
    }

    fig, ax = plt.subplots(figsize=(16, 10), dpi=100)
    pos = layered_or_spring_layout(graph)

    # Draw edges
    nx.draw_networkx_edges(
        graph,
        pos,
        ax=ax,
        edge_color="#374151",
        arrowsize=20,
        arrowstyle="->",
        width=2,
    )

    # Draw nodes by type to use appropriate colors
    node_color_map: dict[str, list[Any]] = {color: [] for color in colors.values()}
    node_type_map: dict[str, list[Any]] = {node_type: [] for node_type in node_types.values()}
    for node in graph.nodes():
        nt = node_types.get(node, "junction")
        node_type_map[nt].append(node)
        node_color_map[colors[nt]].append(node)

    for color, nodes in node_color_map.items():
        if nodes:
            nx.draw_networkx_nodes(
                graph,
                pos,
                nodelist=nodes,
                ax=ax,
                node_color=color,
                node_size=2000,
                node_shape="s",
            )

    # Draw node labels
    nx.draw_networkx_labels(
        graph,
        pos,
        ax=ax,
        labels={n: n for n in graph.nodes()},
        font_size=9,
        font_color="white",
        font_weight="bold",
    )

    # Draw annotation boxes below nodes
    for node in graph.nodes():
        if node in node_labels:
            x, y = pos[node]
            label_text = node_labels[node]
            ax.text(
                x,
                y - 0.18,
                label_text,
                fontsize=8,
                ha="center",
                va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#f3f4f6", alpha=0.9),
                family="monospace",
            )

    ax.set_title("TOCOMO Pipeline Map with Species Concentrations", fontsize=14, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()

    output = Path(output_path)
    fig.savefig(output, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)
    return output.resolve()
