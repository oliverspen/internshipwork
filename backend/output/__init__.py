"""TOCOMO output export system with multi-format support.

Exports TOCOMO simulation results to Excel, PNG, and interactive HTML formats.
All outputs are organized into timestamped subdirectories within outputs/tocomo/.
"""

from datetime import datetime
from pathlib import Path
from typing import Any
import re

import networkx as nx

from .excel_export import save_summary_excel
from .html_export import save_interactive_html_map

_NORWEGIAN = str.maketrans({'æ': 'ae', 'Æ': 'ae', 'ø': 'oe', 'Ø': 'oe', 'å': 'aa', 'Å': 'aa'})


def _slugify(name: str) -> str:
    """Convert a display name to a filesystem-safe ASCII slug."""
    transliterated = name.translate(_NORWEGIAN)
    return re.sub(r'[^A-Za-z0-9_-]+', '_', transliterated.strip().lower()).strip('_') or 'unnamed'


def _save_model_results(
    results: list[dict[str, Any]],
    pipeline_map_name: str | None,
    graph: nx.DiGraph,
    node_types: dict[str, str],
    plant_names: dict[int, str],
    model_folder: str,
    model_label: str,
) -> str:
    """Save model results to multiple formats in an organized directory.

    Creates a timestamped output directory and exports:
    - Per-source Excel files
    - Summary Excel combining all results
    - Static annotated PNG map
    - Interactive HTML map

    Args:
        results: List of result dicts per source (plant, merge, storage)
        pipeline_map_name: Optional name of pipeline map configuration
        graph: networkx DiGraph of the pipeline structure
        node_types: Dict mapping node IDs to types ("plant", "merge", "storage", etc.)
        plant_names: Dict mapping plant indices to their display names
        model_folder: Output subfolder under results/ (for example "tocomo")
        model_label: Display label for console output (for example "TOCOMO")

    Returns:
        Path to the output directory as a string
    """
    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_map_name = _slugify(pipeline_map_name) if pipeline_map_name else 'unnamed'
    output_dir = (Path(__file__).resolve().parents[2] / "results" / model_folder).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session_dir = (output_dir / f"{timestamp}_{safe_map_name}").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    # Export summary files
    save_summary_excel(results, session_dir, model_used=model_label)

    # Export interactive HTML map
    html_path = save_interactive_html_map(
        graph,
        node_types,
        results,
        plant_names,
        session_dir / f"{timestamp}_map.html",
        pipeline_map_name=pipeline_map_name,
    )

    return str(session_dir)


def save_tocomo_results(
    results: list[dict[str, Any]],
    pipeline_map_name: str | None,
    graph: nx.DiGraph,
    node_types: dict[str, str],
    plant_names: dict[int, str],
) -> str:
    """Save TOCOMO results under results/tocomo/."""
    return _save_model_results(
        results,
        pipeline_map_name,
        graph,
        node_types,
        plant_names,
        model_folder="tocomo",
        model_label="TOCOMO",
    )


def save_phpitz_reactive_results(
    results: list[dict[str, Any]],
    pipeline_map_name: str | None,
    graph: nx.DiGraph,
    node_types: dict[str, str],
    plant_names: dict[int, str],
) -> str:
    """Save PH_PITZ reactive results under results/phpitz_reactive/."""
    return _save_model_results(
        results,
        pipeline_map_name,
        graph,
        node_types,
        plant_names,
        model_folder="phpitz_reactive",
        model_label="PH_PITZ reactive",
    )
