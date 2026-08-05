"""
Topology extracts merge definitions from the pipeline graph. 

Converts the networkx graph of pipelines to structured merge, extracted in topological order to ensure upstream -> downstream.
"""

import networkx as nx


def build_merge_definitions(
    graph: nx.DiGraph,
    node_types: dict[str, str],
) -> list[dict[str, object]]:
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
                sources.append(("plant", int(plant_index)))
                continue

            if source_type == "merge":
                # Upstream merges are stored by merge name.
                sources.append(("merge", source_name))
                continue

        # Save one complete definition for this merge node.
        merge_definitions.append(
            {
                "merge_name": node_name,
                "sources": sources,
            }
        )

    # The result is ready for the merge flow resolver.
    return merge_definitions
