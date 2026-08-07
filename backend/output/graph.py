
from typing import Any


def build_graph_from_merge_definitions(
    merge_definitions: list[dict[str, Any]],
    plant_names: dict[int, str],
    storage_name: str = "Storage",
) -> tuple[Any, dict[str, str]]:
    import networkx as nx

    graph = nx.DiGraph()
    node_types: dict[str, str] = {}
    merge_names: set[str] = set()
    upstream_merges: set[str] = set()
    for merge_def in merge_definitions:
        merge_name = str(merge_def["merge_name"])
        merge_names.add(merge_name)
        graph.add_node(merge_name)
        node_types[merge_name] = "merge"
        for source_type, source_value in merge_def["sources"]:
            if source_type == "plant":
                node_name = plant_names.get(int(source_value), f"Plant {source_value}")
                graph.add_node(node_name)
                node_types[node_name] = "plant"
                graph.add_edge(node_name, merge_name)
            elif source_type == "merge":
                source_merge = str(source_value)
                upstream_merges.add(source_merge)
                graph.add_edge(source_merge, merge_name)

    storage_node = str(storage_name or "Storage")
    graph.add_node(storage_node)
    node_types[storage_node] = "storage"
    if merge_definitions:
        terminal_merges = sorted(merge_names - upstream_merges)
        for merge_name in terminal_merges:
            graph.add_edge(merge_name, storage_node)
    else:
        for plant_name in plant_names.values():
            graph.add_node(plant_name)
            node_types[plant_name] = "plant"
            graph.add_edge(plant_name, storage_node)

    return graph, node_types
