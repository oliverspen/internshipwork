"""Simulation endpoints — starts jobs in background threads and exposes a polling endpoint."""

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ..schemas import SimulationRequest
from backend.user_inputs import (
    build_input_config,
    clear_runtime_input_config,
    get_input_config,
    set_runtime_input_config,
)
from backend.pipemapping.dev_pipeline_map import _all_dev_pipeline_maps

router = APIRouter()

_RESULTS_ROOT = Path(__file__).resolve().parents[3] / "results"
_MODEL_FOLDERS = {
    "tocomo": "tocomo",
    "phpitz": "phpitz_reactive",
    "tocomo_dynamic": "tocomo_dynamic",
    "phpitz_dynamic": "phpitz_dynamic",
}

# Simple in-memory job store; fine for a single-process dev server.
_jobs: dict[str, dict[str, Any]] = {}


def _find_latest_session(model_folder: str) -> str | None:
    """Return the name of the most recently created session directory."""
    model_dir = _RESULTS_ROOT / model_folder
    if not model_dir.exists():
        return None
    dirs = [d for d in model_dir.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime).name if dirs else None


def _to_json_safe(obj: Any) -> Any:
    """Recursively convert numpy/non-serializable types to JSON-native equivalents."""
    return json.loads(
        json.dumps(obj, default=lambda o: float(o) if hasattr(o, "__float__") else str(o))
    )


def _build_config_from_request(body: SimulationRequest) -> dict[str, Any]:
    """Resolve a SimulationRequest into a validated runtime config dict."""
    base = get_input_config()

    if body.map_name:
        all_maps = _all_dev_pipeline_maps()
        if body.map_name not in all_maps:
            raise HTTPException(404, f"Pipeline map '{body.map_name}' not found.")
        stored = all_maps[body.map_name]
        merge_definitions = stored["merge_definitions"]
        merge_pipe_inputs = stored["merge_pipe_inputs"]
        storage_name = str(stored.get("storage_name") or base.get("storage_name") or "Storage")
    elif body.pipeline_map:
        merge_definitions = [
            {
                "merge_name": md.merge_name,
                # Pydantic stores tuples; the flow resolver accepts lists too.
                "sources": [list(s) for s in md.sources],
            }
            for md in body.pipeline_map.merge_definitions
        ]
        merge_pipe_inputs = {
            name: inp.model_dump()
            for name, inp in body.pipeline_map.merge_pipe_inputs.items()
        }
        storage_name = str(body.pipeline_map.storage_name or base.get("storage_name") or "Storage")
    else:
        raise HTTPException(422, "Provide either map_name or pipeline_map.")

    plant_inputs = (
        [p.model_dump() for p in body.plant_inputs]
        if body.plant_inputs
        else base["plant_inputs"]
    )
    p_bara = body.p_bara if body.p_bara is not None else float(base["p_bara"])

    config = build_input_config(
        config_plant_inputs=plant_inputs,
        config_merge_pipe_inputs=merge_pipe_inputs,
        config_p_bara=p_bara,
        config_merge_definitions=merge_definitions,
    )
    config["pipeline_map_name"] = body.map_name or "api_request"
    config["storage_name"] = storage_name.strip() or "Storage"
    return config


def _run_job(
    job_id: str,
    model: str,
    config: dict[str, Any],
    duration_days: float | None = None,
    dt_days: float | None = None,
    dynamic_profile: dict[str, Any] | None = None,
) -> None:
    """Execute a simulation in a background thread and write results into _jobs."""
    set_runtime_input_config(config)

    def _update_progress(completed: int, total: int, source_label: str | None = None) -> None:
        safe_total = max(int(total), 1)
        safe_completed = max(0, min(int(completed), safe_total))
        pct = int((safe_completed / safe_total) * 100)
        _jobs[job_id].update({
            "progress_pct": pct,
            "progress_current": safe_completed,
            "progress_total": safe_total,
            "progress_label": source_label,
        })

    try:
        if model == "tocomo":
            from backend.models.tocomo import run_reaction

            results = run_reaction(
                use_dev_pipeline_map=True,
                save_results=True,
                progress_callback=_update_progress,
            )
        elif model == "phpitz":
            from backend.models.phpitz_reactive import run_reaction

            results = run_reaction(
                use_dev_pipeline_map=True,
                save_results=True,
                progress_callback=_update_progress,
            )
        elif model == "tocomo_dynamic":
            from backend.models.dynamic.runner import DURATION_DAYS, DT_DAYS, DYNAMIC_PROFILE
            from backend.models.dynamic.tocomo_dynamic_model import run_reaction_dynamic

            selected_profile = dynamic_profile if dynamic_profile else DYNAMIC_PROFILE
            results = run_reaction_dynamic(
                duration_days=duration_days if duration_days is not None else DURATION_DAYS,
                dt_days=dt_days if dt_days is not None else DT_DAYS,
                dynamic_profile=selected_profile,
                progress_callback=_update_progress,
            )
        elif model == "phpitz_dynamic":
            from backend.models.dynamic.runner import DURATION_DAYS, DT_DAYS, DYNAMIC_PROFILE
            from backend.models.dynamic.phpitz_dynamic_model import run_reaction_dynamic

            selected_profile = dynamic_profile if dynamic_profile else DYNAMIC_PROFILE
            results = run_reaction_dynamic(
                duration_days=duration_days if duration_days is not None else DURATION_DAYS,
                dt_days=dt_days if dt_days is not None else DT_DAYS,
                dynamic_profile=selected_profile,
                progress_callback=_update_progress,
            )
        else:
            raise ValueError(f"Unknown model '{model}'.")

        folder = _MODEL_FOLDERS[model]
        session_id = _find_latest_session(folder)
        html_url = summary_excel_url = None
        graph_urls: list[str] = []
        if session_id:
            session_dir = _RESULTS_ROOT / folder / session_id
            html_files = list(session_dir.glob("*_map.html"))
            graph_files = sorted((session_dir / "graphs").glob("*.png"))
            html_url = f"/results/{folder}/{session_id}/{html_files[0].name}" if html_files else None
            graph_urls = [
                f"/results/{folder}/{session_id}/graphs/{graph_file.name}"
                for graph_file in graph_files
            ]
            summary_excel_path = session_dir / "summary.xlsx"
            dynamic_excel_path = session_dir / "dynamic_results.xlsx"
            if summary_excel_path.exists():
                summary_excel_url = f"/results/{folder}/{session_id}/summary.xlsx"
            elif dynamic_excel_path.exists():
                summary_excel_url = f"/results/{folder}/{session_id}/dynamic_results.xlsx"

        _jobs[job_id].update({
            "status": "done",
            "progress_pct": 100,
            "progress_current": _jobs[job_id].get("progress_total", 1),
            "progress_label": "Completed",
            "session_id": session_id,
            "results": _to_json_safe(results),
            "html_url": html_url,
            "graph_urls": graph_urls,
            "summary_excel_url": summary_excel_url,
        })
    except Exception as exc:
        _jobs[job_id].update({"status": "error", "error": str(exc)})
    finally:
        clear_runtime_input_config()


@router.post("/{model}")
def start_simulation(model: str, body: SimulationRequest) -> dict[str, str]:
    """Start a simulation and return a job_id immediately. Poll GET /jobs/{job_id} for results."""
    if model not in _MODEL_FOLDERS:
        raise HTTPException(404, f"Unknown model '{model}'. Valid: {list(_MODEL_FOLDERS)}")

    if body.dt_days is not None and body.dt_days <= 0:
        raise HTTPException(422, "dt_days must be positive.")
    if body.duration_days is not None and body.duration_days <= 0:
        raise HTTPException(422, "duration_days must be positive.")

    config = _build_config_from_request(body)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running", "model": model,
        "session_id": None, "results": None,
        "html_url": None, "graph_urls": [], "summary_excel_url": None, "error": None,
        "progress_pct": 0, "progress_current": 0, "progress_total": 1, "progress_label": "Queued",
    }
    threading.Thread(
        target=_run_job,
        args=(job_id, model, config, body.duration_days, body.dt_days, body.dynamic_profile),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "running"}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    """Return current status of a simulation job (running / done / error)."""
    if job_id not in _jobs:
        raise HTTPException(404, f"Job '{job_id}' not found.")
    return _jobs[job_id]
