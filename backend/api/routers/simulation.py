"""Simulation endpoints — starts jobs in background threads and exposes a polling endpoint."""

import math
import zipfile
import threading
import uuid
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException

from ..schemas import SimulationRequest
from backend.user_inputs import (
    build_input_config,
    clear_runtime_input_config,
    get_input_config,
    set_runtime_input_config,
)
from backend.pipemapping.dev_pipeline_map import _all_dev_pipeline_maps
from backend.models.phase_envelope.runtime import generate_phase_envelopes_from_config

router = APIRouter()

_RESULTS_ROOT = Path(__file__).resolve().parents[3] / "results"
_MODEL_FOLDERS = {
    "tocomo": "tocomo",
    "phpitz": "phpitz_reactive",
    "tocomo_dynamic": "tocomo_dynamic",
    "phpitz_dynamic": "phpitz_dynamic",
}
_DEFAULT_DYNAMIC_PROFILE: dict[str, Any] = {"plant_profiles": {}}
_DEFAULT_DYNAMIC_DT_DAYS = 0.01
_DEFAULT_DYNAMIC_DURATION_DAYS = 2.0

# Simple in-memory job store; fine for a single-process dev server.
_jobs: dict[str, dict[str, Any]] = {}
_PHASE_ENVELOPES_DIRNAME = "phase envelopes"


def _write_phase_envelope_index(phase_dir: Path, image_names: list[str]) -> Path | None:
    """Write an index page listing all phase envelope images in a session folder."""
    if not image_names:
        return None

    phase_dir.mkdir(parents=True, exist_ok=True)
    image_blocks = "\n".join(
        (
            f"<section><h2>{escape(name)}</h2>"
            f"<p><a href=\"{quote(name)}\" target=\"_blank\">Open image</a></p>"
            "<div class=\"phase-zoom-controls\">"
            "<button type=\"button\" class=\"zoom-btn\" data-zoom=\"out\">-</button>"
            "<button type=\"button\" class=\"zoom-btn\" data-zoom=\"in\">+</button>"
            "<button type=\"button\" class=\"zoom-btn\" data-zoom=\"reset\">Reset</button>"
            "</div>"
            "<div class=\"phase-zoom-frame\">"
            f"<img src=\"{quote(name)}\" alt=\"{escape(name)}\" class=\"phase-zoom-img\" data-scale=\"1\">"
            "</div>"
            "</section>"
        )
        for name in image_names
    )

    html_content = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Phase Envelopes</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;margin:20px;line-height:1.4;background:#f8fafc;color:#111827}"
        "section{margin:0 0 18px 0;padding:12px;border:1px solid #d1d5db;border-radius:8px;background:#fff}"
        ".phase-zoom-controls{display:flex;gap:8px;align-items:center;margin:8px 0}"
        ".zoom-btn{padding:5px 10px;border:1px solid #cbd5e1;background:#f8fafc;border-radius:6px;cursor:pointer}"
        ".zoom-btn:hover{background:#eef2ff}"
        ".phase-zoom-frame{overflow:auto;max-height:72vh;border:1px solid #e5e7eb;border-radius:6px;background:#fff}"
        ".phase-zoom-img{display:block;max-width:none;width:100%;height:auto;transition:width .1s ease}"
        "</style></head>"
        "<body>"
        "<h1>Phase Envelopes</h1>"
        f"<p>Total files: {len(image_names)}. Tip: use mouse wheel over graph to zoom in/out.</p>{image_blocks}"
        "<script>"
        "(function(){"
        "function clamp(v,min,max){return Math.min(max,Math.max(min,v));}"
        "function applyScale(img,scale){img.dataset.scale=String(scale);img.style.width=(scale*100).toFixed(2)+'%';}"
        "document.querySelectorAll('section').forEach(function(section){"
        "  const img=section.querySelector('.phase-zoom-img');"
        "  const frame=section.querySelector('.phase-zoom-frame');"
        "  if(!img||!frame)return;"
        "  section.querySelectorAll('.zoom-btn').forEach(function(btn){"
        "    btn.addEventListener('click',function(){"
        "      const kind=btn.getAttribute('data-zoom');"
        "      const current=Number(img.dataset.scale||'1')||1;"
        "      if(kind==='reset'){applyScale(img,1);return;}"
        "      const next=kind==='in'?current*1.2:current/1.2;"
        "      applyScale(img,clamp(next,0.25,8));"
        "    });"
        "  });"
        "  frame.addEventListener('wheel',function(ev){"
        "    if(!ev.ctrlKey && !ev.metaKey){ev.preventDefault();}"
        "    const current=Number(img.dataset.scale||'1')||1;"
        "    const factor=ev.deltaY<0?1.08:1/1.08;"
        "    applyScale(img,clamp(current*factor,0.25,8));"
        "  },{passive:false});"
        "});"
        "})();"
        "</script></body></html>"
    )

    index_path = phase_dir / "index.html"
    index_path.write_text(html_content, encoding="utf-8")
    return index_path


def _write_phase_envelope_zip(session_dir: Path, phase_dir: Path, image_names: list[str]) -> Path | None:
    """Write a ZIP archive with all phase envelope images for a simulation session."""
    if not image_names:
        return None

    zip_path = session_dir / "phase_envelopes.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for image_name in image_names:
            image_path = phase_dir / image_name
            if image_path.exists():
                zf.write(image_path, arcname=image_name)
    return zip_path


def _find_latest_session(model_folder: str) -> str | None:
    """Return the name of the most recently created session directory."""
    model_dir = _RESULTS_ROOT / model_folder
    if not model_dir.exists():
        return None
    dirs = [d for d in model_dir.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime).name if dirs else None


def _to_json_safe(obj: Any) -> Any:
    """Recursively convert values to JSON-safe primitives.

    FastAPI/Starlette JSON responses reject NaN/Infinity by default, so these values
    must be normalized (to None) before storing into the job payload.
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    if isinstance(obj, dict):
        return {str(key): _to_json_safe(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_json_safe(value) for value in obj]

    if hasattr(obj, "__float__"):
        value = float(obj)
        return value if math.isfinite(value) else None

    # Last resort: string representation for unknown objects.
    return str(obj)


def _build_config_from_request(body: SimulationRequest) -> dict[str, Any]:
    """Resolve a SimulationRequest into a validated runtime config dict."""
    base = get_input_config()
    selected_plant_indexes: list[int] = []

    if body.map_name:
        all_maps = _all_dev_pipeline_maps()
        if body.map_name not in all_maps:
            raise HTTPException(404, f"Pipeline map '{body.map_name}' not found.")
        stored = all_maps[body.map_name]
        merge_definitions = stored["merge_definitions"]
        merge_pipe_inputs = stored["merge_pipe_inputs"]
        selected_plant_indexes = [int(idx) for idx in (stored.get("selected_plant_indexes") or [])]
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
        selected_plant_indexes = [int(idx) for idx in (body.pipeline_map.selected_plant_indexes or [])]
        storage_name = str(body.pipeline_map.storage_name or base.get("storage_name") or "Storage")
    else:
        raise HTTPException(422, "Provide either map_name or pipeline_map.")

    plant_inputs = (
        [p.model_dump() for p in body.plant_inputs]
        if body.plant_inputs
        else base["plant_inputs"]
    )
    if not merge_definitions and selected_plant_indexes:
        selected_index_set = set(selected_plant_indexes)
        plant_inputs = [
            plant_input
            for idx, plant_input in enumerate(plant_inputs)
            if idx in selected_index_set
        ]
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
                progress_callback=_update_progress,
            )
        elif model == "phpitz":
            from backend.models.phpitz_reactive import run_reaction

            results = run_reaction(
                progress_callback=_update_progress,
            )
        elif model == "tocomo_dynamic":
            from backend.models.dynamic.tocomo_dynamic_model import run_reaction_dynamic

            selected_profile = dynamic_profile if dynamic_profile else _DEFAULT_DYNAMIC_PROFILE
            results = run_reaction_dynamic(
                duration_days=(
                    duration_days if duration_days is not None else _DEFAULT_DYNAMIC_DURATION_DAYS
                ),
                dt_days=dt_days if dt_days is not None else _DEFAULT_DYNAMIC_DT_DAYS,
                dynamic_profile=selected_profile,
                progress_callback=_update_progress,
            )
        elif model == "phpitz_dynamic":
            from backend.models.dynamic.phpitz_dynamic_model import run_reaction_dynamic

            selected_profile = dynamic_profile if dynamic_profile else _DEFAULT_DYNAMIC_PROFILE
            results = run_reaction_dynamic(
                duration_days=(
                    duration_days if duration_days is not None else _DEFAULT_DYNAMIC_DURATION_DAYS
                ),
                dt_days=dt_days if dt_days is not None else _DEFAULT_DYNAMIC_DT_DAYS,
                dynamic_profile=selected_profile,
                progress_callback=_update_progress,
            )
        else:
            raise ValueError(f"Unknown model '{model}'.")

        folder = _MODEL_FOLDERS[model]
        session_id = _find_latest_session(folder)
        html_url = summary_excel_url = None
        graph_urls: list[str] = []
        phase_envelope_urls: list[str] = []
        phase_envelope_folder_url: str | None = None
        phase_envelope_zip_url: str | None = None
        phase_envelope_warning: str | None = None
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

            if model in {"tocomo", "phpitz"}:
                try:
                    generated_paths = generate_phase_envelopes_from_config(
                        config,
                        session_dir / _PHASE_ENVELOPES_DIRNAME,
                    )
                    quoted_phase_dir = quote(_PHASE_ENVELOPES_DIRNAME)
                    phase_envelope_urls = [
                        f"/results/{folder}/{session_id}/{quoted_phase_dir}/{quote(path.name)}"
                        for path in generated_paths
                    ]
                    index_path = _write_phase_envelope_index(
                        session_dir / _PHASE_ENVELOPES_DIRNAME,
                        [path.name for path in generated_paths],
                    )
                    zip_path = _write_phase_envelope_zip(
                        session_dir,
                        session_dir / _PHASE_ENVELOPES_DIRNAME,
                        [path.name for path in generated_paths],
                    )
                    if index_path is not None:
                        phase_envelope_folder_url = (
                            f"/results/{folder}/{session_id}/{quoted_phase_dir}/{quote(index_path.name)}"
                        )
                    if zip_path is not None:
                        phase_envelope_zip_url = f"/results/{folder}/{session_id}/{quote(zip_path.name)}"
                except Exception as phase_exc:
                    phase_envelope_warning = str(phase_exc)

        _jobs[job_id].update({
            "status": "done",
            "progress_pct": 100,
            "progress_current": _jobs[job_id].get("progress_total", 1),
            "progress_label": "Completed",
            "session_id": session_id,
            "results": _to_json_safe(results),
            "html_url": html_url,
            "graph_urls": graph_urls,
            "phase_envelope_urls": phase_envelope_urls,
            "phase_envelope_folder_url": phase_envelope_folder_url,
            "phase_envelope_zip_url": phase_envelope_zip_url,
            "phase_envelope_warning": phase_envelope_warning,
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
        "html_url": None, "graph_urls": [], "phase_envelope_urls": [], "phase_envelope_folder_url": None, "phase_envelope_zip_url": None, "phase_envelope_warning": None, "summary_excel_url": None, "error": None,
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
