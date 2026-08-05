"""Results endpoints — browse past simulation sessions and retrieve their outputs."""

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException

from ..schemas import SessionInfo

router = APIRouter()

_RESULTS_ROOT = Path(__file__).resolve().parents[3] / "results"
_MODEL_FOLDERS = {
    "tocomo": "tocomo",
    "phpitz": "phpitz_reactive",
    "tocomo_dynamic": "tocomo_dynamic",
    "phpitz_dynamic": "phpitz_dynamic",
}
_PHASE_ENVELOPES_DIRNAME = "phase envelopes"


@router.get("/{model}", response_model=list[SessionInfo])
def list_sessions(model: str) -> list[SessionInfo]:
    """List all saved sessions for a model, newest first."""
    model_folder = _MODEL_FOLDERS.get(model)
    if model_folder is None:
        raise HTTPException(404, f"Unknown model '{model}'. Valid: {list(_MODEL_FOLDERS)}")

    model_dir = _RESULTS_ROOT / model_folder
    if not model_dir.exists():
        return []

    sessions: list[SessionInfo] = []
    for session_dir in sorted(model_dir.iterdir(), key=lambda d: d.name, reverse=True):
        if not session_dir.is_dir():
            continue
        html_files = list(session_dir.glob("*_map.html"))
        summary_excel_path = session_dir / "summary.xlsx"
        dynamic_excel_path = session_dir / "dynamic_results.xlsx"
        graph_files = sorted((session_dir / "graphs").glob("*.png"))
        phase_envelope_files = sorted((session_dir / _PHASE_ENVELOPES_DIRNAME).glob("*.png"))
        phase_envelope_index_path = session_dir / _PHASE_ENVELOPES_DIRNAME / "index.html"
        phase_envelope_zip_path = session_dir / "phase_envelopes.zip"
        pipeline_map_name: str | None = None
        if not pipeline_map_name:
            parts = session_dir.name.split("_", 1)
            if len(parts) == 2 and parts[1]:
                pipeline_map_name = parts[1]
        sessions.append(
            SessionInfo(
                session_id=session_dir.name,
                model=model,
                pipeline_map_name=pipeline_map_name,
                html_url=f"/results/{model_folder}/{session_dir.name}/{html_files[0].name}" if html_files else None,
                graph_urls=[
                    f"/results/{model_folder}/{session_dir.name}/graphs/{graph_file.name}"
                    for graph_file in graph_files
                ],
                phase_envelope_urls=[
                    f"/results/{model_folder}/{session_dir.name}/{quote(_PHASE_ENVELOPES_DIRNAME)}/{quote(phase_file.name)}"
                    for phase_file in phase_envelope_files
                ],
                phase_envelope_folder_url=(
                    f"/results/{model_folder}/{session_dir.name}/{quote(_PHASE_ENVELOPES_DIRNAME)}/index.html"
                    if phase_envelope_index_path.exists()
                    else None
                ),
                phase_envelope_zip_url=(
                    f"/results/{model_folder}/{session_dir.name}/phase_envelopes.zip"
                    if phase_envelope_zip_path.exists()
                    else None
                ),
                summary_excel_url=(
                    f"/results/{model_folder}/{session_dir.name}/summary.xlsx"
                    if summary_excel_path.exists()
                    else (
                        f"/results/{model_folder}/{session_dir.name}/dynamic_results.xlsx"
                        if dynamic_excel_path.exists()
                        else None
                    )
                ),
            )
        )
    return sessions
