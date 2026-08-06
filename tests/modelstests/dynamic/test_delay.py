import importlib
import math


delay = importlib.import_module("internshipwork.models.dynamic.delay")


def test_contaminant_pipe_time_matches_manual_formula():
    pipe_length_m = 1000.0
    flowrate_kg_per_h = 3600.0
    pipe_diameter_m = 1.0
    density_kg_per_m3 = 1.0

    actual = delay.contaminant_pipe_time_s(
        pipe_length_m=pipe_length_m,
        flowrate_kg_per_h=flowrate_kg_per_h,
        pipe_diameter_m=pipe_diameter_m,
        density_kg_per_m3=density_kg_per_m3,
    )

    expected = pipe_length_m / (1.0 / (math.pi * (pipe_diameter_m / 2.0) ** 2))
    assert actual == expected


def test_contaminant_pipe_time_scales_linearly_with_pipe_length():
    base = delay.contaminant_pipe_time_s(
        pipe_length_m=100.0,
        flowrate_kg_per_h=5000.0,
        pipe_diameter_m=0.4,
        density_kg_per_m3=2.0,
    )
    doubled = delay.contaminant_pipe_time_s(
        pipe_length_m=200.0,
        flowrate_kg_per_h=5000.0,
        pipe_diameter_m=0.4,
        density_kg_per_m3=2.0,
    )

    assert doubled == 2.0 * base
