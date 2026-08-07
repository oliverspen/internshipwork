# Pipeline Simulation Tool

This repository contains a FastAPI application and static frontend for building CO2 pipeline maps, editing stream inputs, running chemistry simulations, and browsing saved outputs.

The app models how impurities in CO2 streams move through a network of plant sources, merge points, and storage. Simulations can be run with steady-state or dynamic chemistry models, and each run is written to disk so results can be revisited from the UI.

## Features

- Build pipeline topologies from plant sources and merge nodes.
- Edit default plant, pressure, and storage inputs from the web UI.
- Run one of four simulation modes:
  - TOCOMO
  - PH_PITZ Reactive
  - TOCOMO Dynamic
  - PH_PITZ Dynamic
- Generate saved result artifacts, including HTML network views, graphs, JSON outputs, and Excel summaries.
- Generate phase-envelope outputs from simulation requests.

## Tech Stack

- Backend: FastAPI + Uvicorn
- Frontend: static HTML, CSS, and JavaScript served by FastAPI
- Chemistry/model dependencies: AcidWatch, NeqSim, Cantera, CoolProp
- Testing: pytest with coverage

## Requirements

- Python 3.14+
- A local environment that can install the dependencies listed in [pyproject.toml](pyproject.toml)

## Quick Start

If you use `uv`:

```bash
uv sync
uv run python main.py
```

If you use plain `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python main.py
```

The app starts on `http://localhost:8000` by default.

## How It Runs

- [main.py](main.py) starts Uvicorn on `0.0.0.0:8000` with reload enabled.
- [backend/api/app.py](backend/api/app.py) serves:
  - `/` for the frontend entry page
  - `/static` for frontend assets
  - `/results` for generated result files
  - `/api/*` for configuration, maps, simulation, and result endpoints

## Configuration

Default runtime inputs are loaded from [input_config.json](input_config.json).

That file defines:

- `plant_inputs`
- `merge_pipe_inputs`
- `p_bara`
- `storage_name`

At runtime, the UI can update and persist this configuration through the config API.

## Simulation Models

| Model | Type | Notes |
|---|---|---|
| TOCOMO | Steady-state | AcidWatch-based reactive chemistry |
| PH_PITZ Reactive | Steady-state | AcidWatch equilibrium chemistry |
| TOCOMO Dynamic | Dynamic | Time-stepping TOCOMO variant |
| PH_PITZ Dynamic | Dynamic | Time-stepping PH_PITZ variant |

CO2 density calculations at merge points use CoolProp.

## Results

Simulation outputs are written under `results/` in model-specific, timestamped session folders. Depending on the run, outputs may include:

- HTML network visualizations
- Graph images
- JSON result payloads
- Excel summary files
- Phase-envelope images, index pages, and ZIP archives

Because the backend mounts `/results` as static content, saved artifacts can be opened directly from the browser after a run completes.

## Running Tests

Run the full test suite with:

```bash
uv run pytest
```

Or, if you are using an activated virtual environment:

```bash
pytest
```

Coverage is configured in [pyproject.toml](pyproject.toml) and targets the `backend` package.

## Project Layout

```text
backend/
  api/                 FastAPI app, routes, request/response schemas
  merge_support/       Flow, topology, and calculation helpers
  models/              Chemistry model pipelines and runners
  output/              Reporting, graphs, HTML, and Excel export
  pipemapping/         Pipeline map models, visuals, and workflow helpers
frontend/static/       Static UI assets
tests/                 Unit and integration-style tests
input_config.json      Default runtime configuration
main.py                Local server entrypoint
```

## Development Notes

- The frontend is served as static files; there is no separate JS build step.
- The backend stores generated outputs on disk, so local runs will create or reuse the `results/` directory.
- CORS is enabled broadly in development.

## API Overview

The app exposes these route groups:

- `/api/config` for reading and updating the default input configuration
- `/api/maps` for saved pipeline-map operations
- `/api/results` for browsing generated results
- `/api/simulate` for launching simulation jobs

For interactive usage, the browser UI at `/` is the main entry point.
