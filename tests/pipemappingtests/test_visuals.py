import networkx as nx

from internshipwork.pipemapping.visuals import layered_or_spring_layout


def test_layered_layout_returns_empty_for_empty_graph():
    graph = nx.DiGraph()

    assert layered_or_spring_layout(graph) == {}


def test_layered_layout_orders_dag_left_to_right():
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("Plant 1", "Merge 1"),
        ("Plant 2", "Merge 1"),
        ("Merge 1", "Storage"),
    ])

    positions = layered_or_spring_layout(graph)

    assert set(positions) == set(graph.nodes)
    for source, target in graph.edges:
        assert positions[source][0] < positions[target][0]


def test_layered_layout_handles_cycles_with_fallback():
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("A", "B"),
        ("B", "A"),
    ])

    positions = layered_or_spring_layout(graph)

    assert set(positions) == {"A", "B"}
    assert all(len(position) == 2 for position in positions.values())
