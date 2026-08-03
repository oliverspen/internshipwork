"""Shared AcidWatch API helper for all models."""

from typing import Any

from ._acidwatch_helpers import run_model_with_fallback


def post_model(
    model_id: str,
    input_concentrations: dict[str, float],
    *,
    temperature_kelvin: float,
    pressure_bara: float,
) -> dict[str, Any]:
    """Run any AcidWatch model using the official session.run_model format."""
    return run_model_with_fallback(
        model_id,
        input_concentrations,
        temperature_kelvin=temperature_kelvin,
        pressure_bara=pressure_bara,
    )
