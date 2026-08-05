import networkx as nx
import pytest

from internshipwork.merge_support.topology import build_merge_definitions


def test_build_merge_definitions_orders_merges_topologically():
    graph = nx.DiGraph()
    graph.add_node("Plant A", plant_index=0)
    graph.add_node("Plant B", plant_index=1)
    graph.add_node("Plant C", plant_index=2)
    graph.add_node("Merge 1")
    graph.add_node("Merge 2")

    graph.add_edge("Plant A", "Merge 1")
    graph.add_edge("Plant B", "Merge 1")
    graph.add_edge("Merge 1", "Merge 2")
    graph.add_edge("Plant C", "Merge 2")

    node_types = {
        "Plant A": "plant",
        "Plant B": "plant",
        "Plant C": "plant",
        "Merge 1": "merge",
        "Merge 2": "merge",
    }

    merge_definitions = build_merge_definitions(graph, node_types)

    assert [item["merge_name"] for item in merge_definitions] == ["Merge 1", "Merge 2"]
    assert merge_definitions[0]["sources"] == [("plant", 0), ("plant", 1)]
    assert merge_definitions[1]["sources"] == [("merge", "Merge 1"), ("plant", 2)]


def test_build_merge_definitions_ignores_unsupported_source_type():
    graph = nx.DiGraph()
    graph.add_node("Storage")
    graph.add_node("Merge 1")
    graph.add_edge("Storage", "Merge 1")

    node_types = {
        "Storage": "storage",
        "Merge 1": "merge",
    }

    result = build_merge_definitions(graph, node_types)
    assert result == [{"merge_name": "Merge 1", "sources": []}]
