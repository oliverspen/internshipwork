"""Transport delay functions for dynamic CO2 pipeline simulation.

This module now keeps only contaminant transport delay.

- **Contaminant delay** (`contaminant_pipe_time_s`): fluid residence time in the
    pipe — how long the bulk CO2 (and its dissolved contaminants) takes to travel
    from inlet to outlet. Equal to pipe volume divided by volumetric flow rate.
"""

from __future__ import annotations

import numpy as np

def contaminant_pipe_time_s(
    pipe_length_m: float,
    flowrate_kg_per_h: float,
    pipe_diameter_m: float,
    density_kg_per_m3: float,
) -> float:
    """Calculate fluid residence time in a pipe (contaminant transport delay).

    Changes in contaminant concentrations are noticed at the pipe outlet after
    this delay: the time for the bulk fluid to travel from inlet to outlet.

    Args:
        pipe_length_m: Pipe length in meters.
        flowrate_kg_per_h: Mass flow rate in kg/h.
        pipe_diameter_m: Internal pipe diameter in meters.
        density_kg_per_m3: Fluid density in kg/m³.

    Returns:
        Residence time in seconds (pipe_volume / volumetric_flow_rate).
    """
    flow_rate_kg_per_s = flowrate_kg_per_h / 3600.0
    volumetric_flow_rate_m3_per_s = flow_rate_kg_per_s / density_kg_per_m3
    pipe_area_m2 = np.pi * (pipe_diameter_m / 2.0) ** 2
    flow_speed_m_per_s = volumetric_flow_rate_m3_per_s / pipe_area_m2
    return pipe_length_m / flow_speed_m_per_s
