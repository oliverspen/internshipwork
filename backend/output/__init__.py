
from datetime import datetime
from pathlib import Path
from typing import Any
import re

import networkx as nx

from .excel_export import save_summary_excel
from .html_export import save_interactive_html_map

_NORWEGIAN = str.maketrans({'æ': 'ae', 'Æ': 'ae', 'ø': 'oe', 'Ø': 'oe', 'å': 'aa', 'Å': 'aa'})


def _slugify(name: str) -> str:
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_map_name = _slugify(pipeline_map_name) if pipeline_map_name else 'unnamed'
    output_dir = (Path(__file__).resolve().parents[2] / "results" / model_folder).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session_dir = (output_dir / f"{timestamp}_{safe_map_name}").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    save_summary_excel(results, session_dir, model_used=model_label)

    save_interactive_html_map(
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
    return _save_model_results(
        results,
        pipeline_map_name,
        graph,
        node_types,
        plant_names,
        model_folder="phpitz_reactive",
        model_label="PH_PITZ reactive",
    )
