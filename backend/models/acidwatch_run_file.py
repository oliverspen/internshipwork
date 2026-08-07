import time
import uuid
from typing import Any

from acidwatch import Client


def _normalize_species_keys(values: dict[str, float]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key, value in values.items():
        normalized_key = str(key).strip().upper()
        normalized[normalized_key] = float(value)
    return normalized


def run_model_compat(
    session: Client,
    model_id: str,
    concs: dict[str, float],
    params: dict[str, Any],
    *,
    temperature: float,
    pressure: float,
    retries: int = 120,
) -> dict[str, float]:

    payload = {
        "concentrations": concs,
        "conditions": {
            "temperature": temperature,
            "pressure": pressure,
        },
        "models": [{"modelId": model_id, "parameters": params}],
    }

    start = session.post("/simulations", json=payload)
    if start.status_code != 200:
        raise RuntimeError("Couldn't start model run", start.json())

    simulation_id = uuid.UUID(start.json())

    for _ in range(retries):
        poll = session.get(f"/simulations/{simulation_id}/result")
        if poll.status_code != 200:
            raise RuntimeError("Couldn't poll model run", poll.json())

        data = poll.json()
        if data.get("status") == "done":
            results = data.get("results", [])
            if not isinstance(results, list) or not results:
                return {}
            result = results[0]
            # Try direct format first, then phases format.
            direct = result.get("concentrations")
            if isinstance(direct, dict):
                return {str(k): float(v) for k, v in direct.items()}
            phases = result.get("phases")
            if isinstance(phases, list):
                for phase in reversed(phases):
                    if isinstance(phase, dict):
                        phase_concs = phase.get("concentrations")
                        if isinstance(phase_concs, dict):
                            return {str(k): float(v) for k, v in phase_concs.items()}
            raise ValueError(f"Unrecognised result shape from API: {result!r}")

        time.sleep(0.5)

    raise RuntimeError("Out of retries")


def run_model_with_fallback(
    model_id: str,
    input_concentrations: dict[str, float],
    *,
    temperature_kelvin: float,
    pressure_bara: float,
    params: dict[str, Any] | None = None,
) -> dict[str, float]:

    model_params = params or {}
    temperature_celsius = temperature_kelvin - 273.15

    with Client() as session:
        try:
            df = session.run_model(
                model_id,
                input_concentrations,
                model_params,
                temperature=temperature_celsius,
                pressure=pressure_bara,
            )
            if df.empty:
                return {}
            return _normalize_species_keys(df.iloc[0].to_dict())
        except Exception:
            return _normalize_species_keys(run_model_compat(
                session,
                model_id,
                input_concentrations,
                model_params,
                temperature=temperature_celsius,
                pressure=pressure_bara,
            ))

