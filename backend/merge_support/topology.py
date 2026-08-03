"""Topology module for extracting merge definitions from pipeline graph.

Converts a NetworkX directed graph of pipeline components into structured merge definitions.
Merges are extracted in topological order to ensure upstream merges are processed before
downstream merges that depend on them.

Input graph structure:
- Nodes: pipeline components (plants, merges, junctions, storage)
- Edges: stream connections from sources to sinks
- node_types: Mapping of node names to types ('plant', 'merge', 'junction', 'storage')
- plant nodes have 'plant_index' attribute (numeric index into plant inputs)

Output: List of merge definitions ordered for dependency resolution.
"""

import networkx as nx


def build_merge_definitions(
    graph: nx.DiGraph,
    node_types: dict[str, str],
) -> list[dict[str, object]]:
    """Extract merge definitions from pipeline graph in topological order.
    
    Each merge is associated with its source nodes (plants or upstream merges).
    Topological ordering ensures downstream merges can depend on upstream results.
    
    Args:
        graph: NetworkX directed graph with pipeline component nodes and stream edges.
        node_types: Mapping of node name to type ('plant', 'merge', etc.).
    
    Returns:
        List of merge definitions, each containing 'merge_name' and 'sources' list.
        Sources are tuples: ('plant', index) or ('merge', name).
    
    Raises:
        ValueError: If merge source types are invalid or merge dependencies unresolved.
    """
    # This list will contain one dictionary per merge node.
    merge_definitions: list[dict[str, object]] = []
    # Topological order makes sure earlier merges appear before downstream merges.
    for node_name in nx.topological_sort(graph):
        # Only merge nodes are converted here.
        if node_types.get(node_name) != "merge":
            continue

        # Each source is stored as either ("plant", index) or ("merge", name).
        sources: list[tuple[str, int | str]] = []
        # Look at all incoming nodes feeding into this merge.
        for source_name in graph.predecessors(node_name):
            source_type = node_types.get(source_name)
            if source_type == "plant":
                # Plant sources are stored by numeric plant index.
                plant_index = graph.nodes[source_name].get("plant_index")
                if plant_index is None:
                    raise ValueError(f"Plant '{source_name}' is missing a plant_index.")
                sources.append(("plant", int(plant_index)))
                continue

            if source_type == "merge":
                # Upstream merges are stored by merge name.
                sources.append(("merge", source_name))
                continue

            # Any other node type would be invalid for merge calculation input.
            raise ValueError(
                f"Merge '{node_name}' has unsupported source '{source_name}' of type '{source_type}'."
            )

        # Save one complete definition for this merge node.
        merge_definitions.append(
            {
                "merge_name": node_name,
                "sources": sources,
            }
        )

    # The result is ready for the merge flow resolver.
    return merge_definitions
