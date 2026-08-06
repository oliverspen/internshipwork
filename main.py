"""Unified entrypoint for frontend/backend app modes and legacy CLI model runs.

Modes:
- fullstack: run backend API and open frontend in browser
- backend: run backend API only
- frontend: open frontend URL only
- legacy: run the old CLI simulation workflow
"""

from __future__ import annotations

import threading
import webbrowser


# App shell mode for web workflow.
APP_MODE = "fullstack"  # "fullstack", "backend", "frontend", "legacy"
HOST = "0.0.0.0"
PORT = 8000
RELOAD = True
OPEN_BROWSER_ON_START = True
FRONTEND_URL = f"http://{HOST}:{PORT}/"


# Legacy simulation mode (only used when APP_MODE == "legacy").
RUN_MODE = "phpitz_reactive"  # "pipemapping", "merge", "tocomo", "phpitz_reactive", "tocomo_dynamic", "phpitz_dynamic"
USE_DEV_PIPELINE_MAP = True  # True to skip interactive mapping prompts and use a stored map.
DEV_PIPELINE_MAP_NAME: str | None = "1"  # Set a name (for example "default") or keep None to choose at runtime.
SAVE_RESULTS = True  # Save outputs when the selected model supports it.


def open_frontend() -> None:
    """Open the frontend URL in the default browser."""
    webbrowser.open(FRONTEND_URL)


def run_backend() -> None:
    """Start the FastAPI backend (serves API and static frontend)."""
    import uvicorn

    uvicorn.run(
        "backend.api.app:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
    )


def run_legacy_workflow() -> None:
    """Run the original local simulation workflow."""
    from backend.merge_support import run_merge_support
    from backend.models.dynamic.phpitz_dynamic_model import run_reaction_dynamic as run_phpitz_dynamic
    from backend.models.dynamic.runner import DURATION_DAYS, DT_DAYS, DYNAMIC_PROFILE
    from backend.models.dynamic.tocomo_dynamic_model import run_reaction_dynamic as run_tocomo_dynamic
    from backend.models.phpitz_reactive import run_reaction as run_phpitz_reactive
    from backend.models.tocomo import run_reaction as run_tocomo_reaction
    from backend.pipemapping import run_pipemapping
    from backend.pipemapping.dev_pipeline_map import apply_dev_pipeline_map, select_dev_pipeline_map_name

    if USE_DEV_PIPELINE_MAP:  # stored pipeline map
        selected_map_name = select_dev_pipeline_map_name(DEV_PIPELINE_MAP_NAME)
        apply_dev_pipeline_map(map_name=selected_map_name)

    if RUN_MODE == "pipemapping":
        run_pipemapping()
        return

    if RUN_MODE == "merge":
        run_merge_support()
        return

    if RUN_MODE == "tocomo":
        run_tocomo_reaction(
            save_results=SAVE_RESULTS,
        )
        return

    if RUN_MODE == "phpitz_reactive":
        run_phpitz_reactive(
            save_results=SAVE_RESULTS,
        )
        return

    if RUN_MODE == "tocomo_dynamic":
        run_tocomo_dynamic(
            duration_days=DURATION_DAYS,
            dt_days=DT_DAYS,
            dynamic_profile=DYNAMIC_PROFILE,
        )
        return

    if RUN_MODE == "phpitz_dynamic":
        run_phpitz_dynamic(
            duration_days=DURATION_DAYS,
            dt_days=DT_DAYS,
            dynamic_profile=DYNAMIC_PROFILE,
        )
        return

    raise ValueError(f"Unknown RUN_MODE '{RUN_MODE}'.")


def run_project() -> None:
    """Run the app according to APP_MODE."""
    if APP_MODE == "frontend":
        open_frontend()
        return

    if APP_MODE == "backend":
        run_backend()
        return

    if APP_MODE == "fullstack":
        if OPEN_BROWSER_ON_START:
            # Delay opening browser slightly so server can bind first.
            threading.Timer(1.5, open_frontend).start()
        run_backend()
        return

    if APP_MODE == "legacy":
        run_legacy_workflow()
        return

    raise ValueError(f"Unknown APP_MODE '{APP_MODE}'.")


if __name__ == "__main__":
    run_project()

