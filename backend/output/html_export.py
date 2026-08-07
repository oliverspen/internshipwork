
import html
from pathlib import Path
from typing import Any

import networkx as nx
from pyvis.network import Network

from backend.pipemapping.visuals import layered_or_spring_layout


def _compute_left_to_right_levels(
    graph: nx.DiGraph,
    node_types: dict[str, str],
    storage_name: str,
) -> dict[str, int]:
    levels: dict[str, int] = {}

    for node in graph.nodes():
        if node_types.get(node) == "plant":
            levels[node] = 0

    try:
        topo_nodes = list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        topo_nodes = list(graph.nodes())

    for node in topo_nodes:
        if node in levels:
            continue
        preds = list(graph.predecessors(node))
        if preds:
            levels[node] = max(levels.get(pred, 0) for pred in preds) + 1
        else:
            levels[node] = 1

    if storage_name in levels:
        levels[storage_name] = max(levels.values(), default=0) + 1

    return levels


def _tooltip_lines_to_html(title: str, lines: list[str]) -> str:
    rows: list[str] = []
    for raw_line in lines:
        line = str(raw_line).strip()
        if not line:
            continue

        if ":" not in line:
            rows.append(
                f"<div class='kv-row'><span class='kv-key'>{html.escape(line)}</span></div>"
            )
            continue

        key, value = line.split(":", 1)
        rows.append(
            "<div class='kv-row'>"
            f"<span class='kv-key'>{html.escape(key.strip())}</span>"
            f"<span class='kv-val'>{html.escape(value.strip())}</span>"
            "</div>"
        )

    if not rows:
        rows.append("<div class='kv-row'><span class='kv-key'>No data</span></div>")

    return (
        "<div class='tt-card'>"
        f"<div class='tt-title'>{html.escape(title)}</div>"
        "<div class='tt-body'>"
        + "".join(rows)
        + "</div></div>"
    )


def _make_node_tooltip(node_name: str, source_type: str, row: dict[str, Any]) -> str:
    lines: list[str] = []

    temperature_kelvin = row.get("temperature_kelvin")
    if temperature_kelvin is not None:
        lines.append(f"Temperature: {float(temperature_kelvin):.2f} K")

    total_massflow = row.get("total_massflow")
    if total_massflow is not None:
        lines.append(f"Flow: {float(total_massflow):.1f} kg/hr")

    inlet = row.get("tocomo_input", {})
    for species in sorted(inlet.keys()):
        value = float(inlet.get(species, 0.0))
        if value == 0.0:
            continue
        lines.append(f"Inlet {species}: {value:.1f} molar ppm")

    return _tooltip_lines_to_html("Node Details", lines)


def _make_edge_tooltip(source: str, target: str, final_values: dict[str, Any]) -> str:
    lines: list[str] = []
    for species in sorted(final_values.keys()):
        value = float(final_values.get(species, 0.0))
        if value == 0.0:
            continue
        lines.append(f"Predicted {species.upper()}: {value:.1f} molar ppm")

    return _tooltip_lines_to_html("Stream Composition", lines)


def save_interactive_html_map(
    graph: nx.DiGraph,
    node_types: dict[str, str],
    results: list[dict[str, Any]],
    plant_names: dict[int, str],
    output_path: str | Path,
    pipeline_map_name: str | None = None,
) -> Path:
    graph = graph.copy()
    node_types = dict(node_types)

    colors = {
        "plant": {"background": "#dff5e6", "border": "#2f855a", "font": "#1f5135"},
        "merge": {"background": "#ffe8cc", "border": "#dd6b20", "font": "#7b341e"},
        "storage": {"background": "#dbeafe", "border": "#2563eb", "font": "#1e3a8a"},
        "junction": {"background": "#e5e7eb", "border": "#6b7280", "font": "#1f2937"},
    }

    storage_rows = [row for row in results if str(row.get("source_type", "")) == "storage"]
    storage_name = str(storage_rows[-1].get("source_name") if storage_rows else "Storage").strip() or "Storage"

    if storage_name not in graph:
        graph.add_node(storage_name)
    node_types[storage_name] = "storage"

    has_storage_incoming = any(target == storage_name for _source, target in graph.edges())
    if not has_storage_incoming:
        sinks = [
            node
            for node in graph.nodes()
            if node != storage_name and graph.out_degree(node) == 0
        ]
        for sink in sinks:
            graph.add_edge(sink, storage_name)

    net = Network(
        height="760px",
        width="100%",
        directed=True,
        bgcolor="#f5f7fa",
        font_color="#111827",
    )
    net.set_options("""
    {
      "layout": {
        "improvedLayout": true
      },
      "physics": { "enabled": false },
      "interaction": {
        "hover": true,
        "tooltipDelay": 999999,
        "dragNodes": true,
        "hideEdgesOnDrag": false,
        "hideNodesOnDrag": false,
        "navigationButtons": false,
        "zoomView": true,
        "dragView": true,
        "keyboard": { "enabled": true, "bindToWindow": false }
      },
      "edges": {
        "color": { "color": "#374151", "highlight": "#111827" },
        "width": 3,
        "smooth": { "enabled": false },
        "arrows": { "to": { "enabled": true, "scaleFactor": 1.35 } },
        "selectionWidth": 1.3,
        "hoverWidth": 1.2
      },
      "nodes": {
        "shape": "box",
        "margin": { "top": 18, "right": 20, "bottom": 18, "left": 20 },
        "widthConstraint": { "minimum": 190, "maximum": 260 },
        "shapeProperties": { "borderRadius": 12 },
        "font": {
          "size": 19,
          "face": "Segoe UI",
          "color": "#111827",
          "multi": false,
          "vadjust": 0
        },
        "borderWidth": 2.5,
        "borderWidthSelected": 3,
        "shadow": { "enabled": true, "size": 10, "x": 0, "y": 2, "color": "rgba(15, 23, 42, 0.18)" }
      }
    }
    """)

    node_tooltips: dict[str, str] = {}
    for row in results:
        source_type = str(row.get("source_type", ""))
        source_name = row.get("source_name")

        if source_type == "plant":
            node_name = plant_names.get(int(source_name), f"plant {source_name}")
        elif source_type == "storage":
            node_name = str(source_name)
        else:
            node_name = str(source_name)

        node_tooltips[node_name] = _make_node_tooltip(node_name, source_type, row)

    edge_tooltips: dict[tuple[str, str], str] = {}
    for row in results:
        source_type = str(row.get("source_type", ""))
        source_name = row.get("source_name")
        final_values = row.get("final", {})

        if source_type == "plant":
            source_node = plant_names.get(int(source_name), f"plant {source_name}")
        elif source_type == "storage":
            source_node = str(source_name)
        else:
            source_node = str(source_name)

        if source_node not in graph:
            continue

        for target in graph.successors(source_node):
            edge_tooltips[(source_node, target)] = _make_edge_tooltip(source_node, target, final_values)

    positions = layered_or_spring_layout(graph)
    levels = _compute_left_to_right_levels(graph, node_types, storage_name)
    x_scale = 500
    y_scale = 310

    for node in graph.nodes():
        x, y = positions.get(node, (0, 0))
        role = node_types.get(node, "junction")
        color = colors.get(role, colors["junction"])
        node_label = str(node)
        tooltip_html = node_tooltips.get(node, _tooltip_lines_to_html("Node Details", [f"Node: {node_label}"]))

        net.add_node(
            node,
            label=node_label,
            title="",
            tooltip_html=tooltip_html,
            color=color,
            x=float(x) * x_scale,
            y=float(-y) * y_scale,
            size=44,
            font={"color": color["font"], "size": 19, "face": "Segoe UI"},
            shape="box",
        )

    for source, target in graph.edges():
        tooltip_html = edge_tooltips.get(
            (source, target),
          _tooltip_lines_to_html("Stream Composition", []),
        )
        net.add_edge(
            source,
            target,
            color="#374151",
            width=3,
            title="",
            tooltip_html=tooltip_html,
            arrows={"to": {"enabled": True, "scaleFactor": 1.35}},
        )

    output = Path(output_path)
    html_content = net.generate_html()
    html_content = html_content.replace(' src="lib/', ' src="/lib/').replace(' href="lib/', ' href="/lib/')

    map_title = str(pipeline_map_name or "Pipeline map").strip() or "Pipeline map"
    heading_html = (
        "<div class=\"pfd-header\">"
        f"<h2>{html.escape(map_title)}</h2>"
        "<p>Interactive process-flow diagram</p>"
        "</div>"
    )

    controls_html = (
        "<div class=\"pfd-controls\" aria-label=\"Diagram controls\">"
        "<button type=\"button\" id=\"pfd-zoom-in\">Zoom In</button>"
        "<button type=\"button\" id=\"pfd-zoom-out\">Zoom Out</button>"
        "<button type=\"button\" id=\"pfd-fit\">Fit</button>"
        "<button type=\"button\" id=\"pfd-reset\">Reset</button>"
        "</div>"
        "<div id=\"pfd-tooltip\" class=\"pfd-tooltip\" style=\"display:none;\"></div>"
    )

    custom_style = """
<style>
  body {
    margin: 0;
    background: #f5f7fa;
    color: #1f2937;
    font-family: "Segoe UI", Arial, sans-serif;
  }
  .pfd-header {
    margin: 18px 24px 8px 24px;
    text-align: center;
  }
  .pfd-header h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: #1f3a5f;
    letter-spacing: 0.01em;
    text-transform: capitalize;
  }
  .pfd-header p {
    margin: 4px 0 0 0;
    font-size: 13px;
    color: #526277;
  }
  center > h1:empty {
    display: none;
  }
  center:empty {
    display: none;
  }
  .card {
    position: relative;
    margin: 10px 18px 22px 18px;
    border-radius: 14px;
    border: 1px solid #d9e1ea;
    box-shadow: 0 8px 26px rgba(15, 23, 42, 0.08);
    overflow: hidden;
    background: #ffffff;
  }
  #mynetwork {
    width: 100% !important;
    height: 790px !important;
    background-color: #f5f7fa !important;
    border: none !important;
    padding: 24px !important;
  }
  .pfd-controls {
    position: absolute;
    top: 14px;
    right: 14px;
    z-index: 20;
    display: flex;
    gap: 8px;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #d7dfe8;
    border-radius: 10px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
    padding: 8px;
    backdrop-filter: blur(3px);
  }
  .pfd-controls button {
    border: 1px solid #cbd5e1;
    background: #ffffff;
    color: #334155;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 10px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .pfd-controls button:hover {
    border-color: #93c5fd;
    background: #eff6ff;
    color: #1d4ed8;
  }
  .pfd-controls button:active {
    transform: translateY(1px);
  }
  .pfd-tooltip {
    position: absolute;
    z-index: 30;
    width: 300px;
    max-width: 360px;
    pointer-events: none;
  }
  .tt-card {
    border-radius: 12px;
    border: 1px solid #d6dee8;
    background: #ffffff;
    box-shadow: 0 16px 34px rgba(15, 23, 42, 0.2);
    overflow: hidden;
  }
  .tt-title {
    background: #edf2f7;
    color: #1f2937;
    padding: 9px 12px;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .tt-body {
    padding: 10px 12px 11px 12px;
    display: grid;
    row-gap: 7px;
  }
  .kv-row {
    display: grid;
    grid-template-columns: minmax(100px, 1fr) minmax(120px, 1fr);
    column-gap: 10px;
    align-items: start;
  }
  .kv-key {
    color: #475569;
    font-weight: 600;
    font-size: 12px;
  }
  .kv-val {
    color: #0f172a;
    font-size: 12px;
    text-align: right;
    font-family: "Segoe UI", Arial, sans-serif;
  }
</style>
"""

    control_script = """
<script>
  (function () {
    if (typeof network === "undefined" || typeof nodes === "undefined" || typeof edges === "undefined") {
      return;
    }

    var tooltipEl = document.getElementById("pfd-tooltip");
    var container = document.getElementById("mynetwork");
    if (!tooltipEl || !container) return;

    function positionTooltip(domPoint) {
      var rect = container.getBoundingClientRect();
      var x = Math.min(rect.width - 22, Math.max(16, domPoint.x + 18));
      var y = Math.min(rect.height - 18, Math.max(16, domPoint.y + 18));
      tooltipEl.style.left = x + "px";
      tooltipEl.style.top = y + "px";
    }

    function showTooltip(htmlText, domPoint) {
      if (!htmlText) return;
      tooltipEl.innerHTML = htmlText;
      tooltipEl.style.display = "block";
      positionTooltip(domPoint || { x: 22, y: 22 });
    }

    function hideTooltip() {
      tooltipEl.style.display = "none";
      tooltipEl.innerHTML = "";
    }

    network.on("hoverNode", function (params) {
      var item = nodes.get(params.node);
      showTooltip(item && item.tooltip_html, params.pointer.DOM);
    });

    network.on("hoverEdge", function (params) {
      var item = edges.get(params.edge);
      showTooltip(item && item.tooltip_html, params.pointer.DOM);
    });

    network.on("blurNode", hideTooltip);
    network.on("blurEdge", hideTooltip);
    network.on("dragStart", hideTooltip);
    network.on("zoom", hideTooltip);
    container.addEventListener("mouseleave", hideTooltip);

    var zoomInBtn = document.getElementById("pfd-zoom-in");
    var zoomOutBtn = document.getElementById("pfd-zoom-out");
    var fitBtn = document.getElementById("pfd-fit");
    var resetBtn = document.getElementById("pfd-reset");

    var initialView = { position: { x: 0, y: 0 }, scale: 1 };

    network.once("stabilized", function () {
      network.fit({ animation: { duration: 300, easingFunction: "easeInOutQuad" } });
      if (network.getViewPosition) {
        initialView = { position: network.getViewPosition(), scale: network.getScale() };
      }
    });

    function smoothMove(nextScale) {
      network.moveTo({
        scale: nextScale,
        animation: { duration: 180, easingFunction: "easeInOutQuad" }
      });
    }

    if (zoomInBtn) {
      zoomInBtn.addEventListener("click", function () {
        smoothMove(Math.min(3, network.getScale() * 1.18));
      });
    }
    if (zoomOutBtn) {
      zoomOutBtn.addEventListener("click", function () {
        smoothMove(Math.max(0.2, network.getScale() / 1.18));
      });
    }
    if (fitBtn) {
      fitBtn.addEventListener("click", function () {
        network.fit({ animation: { duration: 280, easingFunction: "easeInOutQuad" } });
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        network.moveTo({
          position: initialView.position,
          scale: initialView.scale,
          animation: { duration: 250, easingFunction: "easeInOutQuad" }
        });
      });
    }
  })();
</script>
"""

    html_content = html_content.replace("<body>", f"<body>\n{heading_html}\n", 1)
    html_content = html_content.replace(
        '<div class="card" style="width: 100%">',
        f'<div class="card" style="width: 100%">\n{controls_html}',
        1,
    )
    html_content = html_content.replace("</head>", f"{custom_style}\n</head>", 1)
    html_content = html_content.replace("</body>", f"{control_script}\n</body>", 1)

    output.write_text(html_content, encoding="utf-8")
    return output.resolve()
