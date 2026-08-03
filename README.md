# Pipeline Simulation Tool

A web-based tool for simulating CO₂ pipeline chemistry using the **TOCOMO** and **PH_PITZ** reactive chemistry models. It models how impurities in a CO₂ stream (H₂O, O₂, SO₂, NO₂, H₂S) behave as the stream flows through a pipeline network made up of plant sources and merge points.

## What it does

- **Defines a pipeline topology** — connect multiple plant sources (CO₂ streams with known compositions) into a network of merge points, representing how streams combine in a real pipeline.
- **Runs chemistry simulations** — passes the merged stream conditions through one of four models:
  - *TOCOMO* — steady-state reactive chemistry
  - *PH_PITZ Reactive* — equilibrium chemistry using the Pitzer activity model
  - *TOCOMO Dynamic* — time-stepping version of TOCOMO
  - *PH_PITZ Dynamic* — time-stepping version of PH_PITZ
- **Saves and browses results** — each simulation run is saved to a timestamped folder under `results/`. Results include JSON data, graphs, and interactive HTML network maps.
- **Editable configuration** — stream compositions, pressures, temperatures, and model parameters can be edited through the web UI without touching any code.

## Models

| Model | Type | Library |
|---|---|---|
| TOCOMO | Steady-state | AcidWatch |
| PH_PITZ Reactive | Equilibrium | AcidWatch |
| TOCOMO Dynamic | Transient | AcidWatch |
| PH_PITZ Dynamic | Transient | AcidWatch |

CO₂ density at merge points is calculated using **CoolProp**.

## Running locally

Requires **Python ≥ 3.14**.

```powershell
uv run uvicorn backend.api.app:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.
