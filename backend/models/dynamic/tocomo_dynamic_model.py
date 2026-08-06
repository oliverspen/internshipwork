"""TOCOMO dynamic model wrapper for time-stepping simulations.

Wraps the generic dynamic merge simulation engine (dynamic_model_engine) with a
TOCOMO chemistry evaluator to run equilibrium calculations at each time step with
time-varying inlet stream conditions.

Main entry point: run_reaction_dynamic() orchestrates the entire simulation workflow
including plant state collection, merge property calculation, TOCOMO API evaluation,
and report generation.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from backend.models.acidwatch_run_file import run_model_with_fallback
from backend.models.dynamic.dynamic_model_engine import run_dynamic_merges
from backend.output.dynamic_reporting import render_dynamic_reports
from backend.output.excel_export import save_dynamic_excel
from backend.user_inputs import get_input_config


def _evaluate_tocomo_plant(
    plant_name: str,
    plant_values: dict[str, Any],
    time_days: float,
) -> dict[str, Any]:
    """Call TOCOMO API to evaluate chemistry for a plant inlet stream.
    
    Args:
        plant_name: Name of the plant (for logging).
        plant_values: Plant state dict with inlet_* concentration keys.
        time_days: Current simulation time in days.
    
    Returns:
        Dict with keys 'tocomo_input' (input concentrations sent to API) and
        'final' (equilibrium concentrations returned by TOCOMO).
    """
    # Extract inlet concentrations from plant values
    input_concentrations = {
        "H2O": plant_values.get("inlet_H2O", 0),
        "O2": plant_values.get("inlet_O2", 0),
        "SO2": plant_values.get("inlet_SO2", 0),
        "NO2": plant_values.get("inlet_NO2", 0),
        "H2S": plant_values.get("inlet_H2S", 0),
    }
    
    # Get pressure from input config (consistent with main runners)
    input_config = get_input_config()
    pressure_bara = float(input_config.get("p_bara", 10.0))
    temperature_kelvin = float(plant_values.get("temperature_kelvin", 298.15))
    
    # Call TOCOMO via the shared API client (uses fallback if needed)
    final_values = run_model_with_fallback(
        "tocomo",
        input_concentrations,
        temperature_kelvin=temperature_kelvin,
        pressure_bara=pressure_bara,
    )

    # Enforce uppercase species keys across backend outputs.
    final_normalized = {str(k).upper(): v for k, v in final_values.items()} if final_values else {}

    return {
        "tocomo_input": input_concentrations,
        "final": final_normalized,
    }


def _evaluate_tocomo_merge(
    merge_name: str,
    merge_values: dict[str, Any],
    _time_days: float,
) -> dict[str, Any]:
    """Call TOCOMO API to evaluate chemistry at a merge node.
    
    Args:
        merge_name: Name of the merge node (for logging).
        merge_values: Merge state dict with ppm_molar concentrations.
        _time_days: Current simulation time in days (unused, for callback compatibility).
    
    Returns:
        Dict with keys 'tocomo_input' (input concentrations sent to API) and
        'final' (equilibrium concentrations returned by TOCOMO).
    """
    # Convert from internal representation to capitalized species names matching AcidWatch
    # Note: TOCOMO only supports 5 species (NO is not supported for TOCOMO)
    input_concentrations = {
        "H2O": merge_values["ppm_molar"].get("H2O", 0),
        "O2": merge_values["ppm_molar"].get("O2", 0),
        "SO2": merge_values["ppm_molar"].get("SO2", 0),
        "NO2": merge_values["ppm_molar"].get("NO2", 0),
        "H2S": merge_values["ppm_molar"].get("H2S", 0),
    }
    
    # Get pressure from input config (consistent with main runners)
    input_config = get_input_config()
    pressure_bara = float(input_config.get("p_bara", 10.0))
    temperature_kelvin = float(merge_values.get("temperature_kelvin", 298.15))
    
    # Call TOCOMO via the shared API client (uses fallback if needed)
    final_values = run_model_with_fallback(
        "tocomo",
        input_concentrations,
        temperature_kelvin=temperature_kelvin,
        pressure_bara=pressure_bara,
    )

    # Enforce uppercase species keys across backend outputs.
    final_normalized = {str(k).upper(): v for k, v in final_values.items()} if final_values else {}

    return {
        "tocomo_input": input_concentrations,
        "final": final_normalized,
    }


def run_reaction_dynamic(
    duration_days: float | None,
    dt_days: float,
    dynamic_profile: dict[str, object],
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> list[dict]:
    """Run TOCOMO as a dynamic model with time-varying stream inputs.
    
    Orchestrates a time-stepping simulation where:
    1. Inlet conditions vary according to dynamic_profile
    2. At each time step, merges are calculated with transport delays
    3. TOCOMO API evaluates equilibrium concentrations at each merge
    4. Results are collected for plant states and merge states
    5. Summary reports (graphs, tables) are generated and saved to results/tocomo_dynamic/{timestamp}
    
    Args:
        duration_days: Simulation duration in days, or None to auto-derive from pipe times.
        dt_days: Time step size in days.
        dynamic_profile: Dict with 'plant_profiles' specifying time-varying inlet conditions.
    
    Returns:
        List of merge result dicts (one per time_step, merge_name) with TOCOMO outputs.
    """
    # Create results/tocomo_dynamic/{timestamp} folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (Path(__file__).resolve().parents[3] / "results" / "tocomo_dynamic").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session_dir = (output_dir / timestamp).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    
    plant_results: list[dict[str, Any]] = []

    if progress_callback is not None:
        progress_callback(0, 100, "Preparing dynamic TOCOMO simulation")

    def _engine_progress(completed: int, total: int, source_label: str | None = None) -> None:
        if progress_callback is None:
            return
        safe_total = max(int(total), 1)
        safe_completed = max(0, min(int(completed), safe_total))
        # Reserve 0-90% for time-stepping, remaining for post-processing.
        scaled = int((safe_completed / safe_total) * 90)
        progress_callback(scaled, 100, source_label or "Running dynamic simulation")

    dynamic_results = run_dynamic_merges(
        duration_days=duration_days,
        dt_days=dt_days,
        dynamic_profile=dynamic_profile,
        evaluate_merge=lambda merge_name, merge_values, time_days: _evaluate_tocomo_merge(
            merge_name,
            merge_values,
            time_days,
        ),
        collect_plant_rows=plant_results,
        progress_callback=_engine_progress,
    )
    
    # Evaluate each plant with TOCOMO to get final concentrations
    if progress_callback is not None:
        progress_callback(92, 100, "Evaluating plant chemistry")
    for plant_result in plant_results:
        tocomo_result = _evaluate_tocomo_plant(
            plant_result.get("plant_name", "Unknown"),
            plant_result,
            plant_result.get("time_days", 0),
        )
        plant_result["final"] = tocomo_result.get("final", {})
    
    # Save reports to the session directory
    if progress_callback is not None:
        progress_callback(96, 100, "Generating dynamic reports")
    graph_output_path = session_dir / f"{timestamp}_change_points.png"
    render_dynamic_reports(
        dynamic_results,
        plant_results,
        dynamic_profile,
        graph_output_path=str(graph_output_path),
    )
    
    # Save results to Excel
    if progress_callback is not None:
        progress_callback(98, 100, "Writing Excel output")
    excel_path = save_dynamic_excel(
        dynamic_results,
        plant_results,
        session_dir,
        model_used="TOCOMO dynamic",
    )

    if progress_callback is not None:
        progress_callback(99, 100, "Finalizing outputs")
    
    print(f"Dynamic TOCOMO results saved to: {session_dir}")
    print(f"  - Graph: {graph_output_path}")
    print(f"  - Excel: {excel_path}")
    return dynamic_results
