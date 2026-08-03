"""Shared AcidWatch helpers used by model packages.

This module provides a robust wrapper around the AcidWatch API with automatic
fallback handling. Instead of failing when the API response schema changes, the
code gracefully degrades:

1. Try the fast direct method (session.run_model)
2. If it fails for any reason, automatically fall back to raw REST polling
3. Both paths handle old and new API response formats
4. Callers never need to know which method succeeded

This approach allows the code to survive API changes without requiring immediate
updates, and makes it easier to debug which method is working in production.
"""

import time
import uuid
from typing import Any

from acidwatch import Client


def extract_result_concentrations(result_item: dict[str, Any]) -> dict[str, float]:
    """Extract chemical concentrations from a model result, handling multiple response formats.
    
    The AcidWatch API can return results in different shapes:
    1. Old format: result has "concentrations" key directly
    2. New format: result has "phases" list with concentrations in each phase
    
    This function normalizes both formats to a flat dict: {"species_name": concentration_value}
    Returns the last (final) phase's concentrations if multiple phases exist.
    """
    direct = result_item.get("concentrations")
    if isinstance(direct, dict):
        return {str(k): float(v) for k, v in direct.items()}

    phases = result_item.get("phases")
    if isinstance(phases, list):
        # Use the last valid phase as the final state.
        for phase in reversed(phases):
            if not isinstance(phase, dict):
                continue
            phase_concs = phase.get("concentrations")
            if not isinstance(phase_concs, dict):
                continue
            return {str(k): float(v) for k, v in phase_concs.items()}

    raise ValueError("Unsupported simulation result shape")


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
    """Run a chemistry model using raw REST API calls (polling fallback method).
    
    When the primary session.run_model() method fails, this is the backup approach.
    It works by:
    1. POST to /simulations to start the model run (returns simulation_id)
    2. Poll /simulations/{id}/result repeatedly to check if done (up to 120 times)
    3. Wait 0.5 seconds between polls to avoid hammering the server
    4. Once status="done", extract and return the chemical concentrations
    
    This method is slower but more robust to API response format changes.
    
    Args:
        session: AcidWatch Client connection
        model_id: Which model to run (e.g., "phpitz_reactive", "tocomo")
        concs: Input chemical concentrations {species: ppm_value}
        params: Model-specific parameters
        temperature: Temperature in Kelvin
        pressure: Pressure in bar-absolute
        retries: Max polling attempts (120 * 0.5s = 60 seconds timeout)
    
    Returns:
        dict of output concentrations {species: ppm_value} after model reaction
    """
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
            return extract_result_concentrations(results[0])

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
    """Run a chemistry model with automatic fallback if primary method fails.
    
    This is the main entry point for all model runs. It tries two approaches:
    
    PRIMARY (fast but fragile):
    - Use session.run_model() from AcidWatch library
    - Returns results as a DataFrame
    - Works only if API response exactly matches expected schema
    
    FALLBACK (slower but robust):
    - If primary fails with any exception, automatically try run_model_compat()
    - Uses raw REST API calls with polling instead of library method
    - Handles older/newer API response formats automatically
    
    The fallback is transparent to callers—they always get results if either
    method succeeds. This handles API evolution and schema mismatches gracefully.
    
    Args:
        model_id: Which model to run (e.g., "phpitz_reactive", "tocomo")
        input_concentrations: Input chemical species concentrations
        temperature_kelvin: Temperature in Kelvin (e.g., 298.15 K)
        pressure_bara: Pressure in bar-absolute (e.g., 1.0 bara)
        params: Optional model-specific parameters (default: empty dict)
    
    Returns:
        dict of output concentrations after the chemical reaction
        Returns empty dict {} if model run produces no results
    """
    model_params = params or {}

    with Client() as session:
        try:
            df = session.run_model(
                model_id,
                input_concentrations,
                model_params,
                temperature=temperature_kelvin,
                pressure=pressure_bara,
            )
            if df.empty:
                return {}
            return {str(k): float(v) for k, v in df.iloc[0].to_dict().items()}
        except Exception as e:
            # Keep broad fallback handling to tolerate client/back-end schema drift.
            return run_model_compat(
                session,
                model_id,
                input_concentrations,
                model_params,
                temperature=temperature_kelvin,
                pressure=pressure_bara,
            )

