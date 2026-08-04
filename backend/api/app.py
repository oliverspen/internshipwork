"""FastAPI application entry point."""

import logging
import os

import pyvis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routers import config, maps, results, simulation

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Pipeline Simulation API",
    description="Run TOCOMO / PH_PITZ simulations over HTTP and browse saved results.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve result files (HTML maps, JSON, PNG) as static assets.
_results_dir = Path(__file__).resolve().parents[2] / "results"
_results_dir.mkdir(parents=True, exist_ok=True)
app.mount("/results", StaticFiles(directory=str(_results_dir)), name="results")

# Serve pyvis dependencies (vis-network, tom-select, bindings) used by saved HTML maps.
_lib_dir = Path(__file__).resolve().parents[2] / "lib"
if _lib_dir.is_dir() and os.access(_lib_dir, os.R_OK):
    try:
        app.mount("/lib", StaticFiles(directory=str(_lib_dir)), name="lib")
    except PermissionError:
        logger.warning("Unable to mount /lib because %s is not readable", str(_lib_dir))
else:
    if _lib_dir.exists():
        logger.warning("Unable to mount /lib because %s is not a readable directory", str(_lib_dir))
    else:
        pyvis_lib_dir = Path(pyvis.__file__).resolve().parent / "lib"
        if pyvis_lib_dir.is_dir() and os.access(pyvis_lib_dir, os.R_OK):
            try:
                app.mount("/lib", StaticFiles(directory=str(pyvis_lib_dir)), name="lib")
            except PermissionError:
                logger.warning("Unable to mount /lib because %s is not readable", str(pyvis_lib_dir))
        else:
            logger.warning(
                "Unable to mount /lib because pyvis lib directory %s is unavailable",
                str(pyvis_lib_dir),
            )

# Serve the frontend.
_static_dir = Path(__file__).resolve().parents[2] / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(maps.router, prefix="/api/maps", tags=["maps"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(simulation.router, prefix="/api/simulate", tags=["simulation"])


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "static" / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return an empty favicon response to avoid 404s in browser logs."""
    favicon_path = Path(__file__).resolve().parents[2] / "frontend" / "static" / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=204)
