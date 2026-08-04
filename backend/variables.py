import numpy as np

from backend.user_inputs import PLANT_SPECIES, get_input_config


_input_config = get_input_config()
plant_inputs = _input_config["plant_inputs"]
merge_pipe_inputs = _input_config["merge_pipe_inputs"]
p_bara = _input_config["p_bara"]


# concentrations
inlet_conc = {
    species: [plant_input["inlet_conc"][species] for plant_input in plant_inputs]
    for species in PLANT_SPECIES
}

o2 = inlet_conc["o2"]
h2o = inlet_conc["h2o"]
so2 = inlet_conc["so2"]
no2 = inlet_conc["no2"]
no = inlet_conc["no"]
so3 = inlet_conc["so3"]
h2s = inlet_conc["h2s"]

nonco2 = [
    inlet_conc["o2"][i]
    + inlet_conc["h2o"][i]
    + inlet_conc["no"][i]
    + inlet_conc["no2"][i]
    + inlet_conc["so3"][i]
    + inlet_conc["h2s"][i]
    for i in range(len(inlet_conc["o2"]))
]

co2 = [10**6 - value for value in nonco2]  # molar ppm

# reaction rate constants
"""
JUST USED FOR PROTOTYPE, NOT DEFINITIVE NUMBERS, NEED TO IMPORT MODEL FROM ACIDWATCH
Reaction logic:
Sulphuric acid
H2S + 3/2 O2 -> SO2 + H2O
2SO2 + O2 -> 2SO3
SO3 + H2O -> H2SO4

Nitric acid:
2NO + O2 -> 2NO2
2NO2 + H2O -> HNO3 + HNO2
"""

k_h2so4 = 6 * 10**8  # L/mol s
k_so2_h2o = 0.13  # L/mol s
k_so3 = 10 ** (-5)  # L/mol s
k_no2 = 2 * 10**6  # L^2/mol^2 s
k_hno3_hno2 = 10 ** (-2)  # L/mol s

# flow rates
flowrates = [plant_input["flowrate"] for plant_input in plant_inputs]  # kg/hr

# temperature
temperature_celsius = [plant_input["temperature_celsius"] for plant_input in plant_inputs]

# pipe specs for plants
pipelength = [plant_input["pipelength"] for plant_input in plant_inputs]  # m
pipediameter = [plant_input["pipediameter"] for plant_input in plant_inputs]  # m
pipearea = [np.pi * (diameter / 2) ** 2 for diameter in pipediameter]  # m^2

# pipe specs for merge segments keyed by merge name.
merge_pipelength = {
    merge_name: merge_input["pipelength"]
    for merge_name, merge_input in merge_pipe_inputs.items()
}
merge_pipediameter = {
    merge_name: merge_input["pipediameter"]
    for merge_name, merge_input in merge_pipe_inputs.items()
}
merge_pipearea = {
    merge_name: np.pi * (diameter / 2) ** 2
    for merge_name, diameter in merge_pipediameter.items()
}

# Compatibility aliases for older code paths that still reference merge1/merge2 names.
_merge_names = list(merge_pipe_inputs)
if len(_merge_names) >= 1:
    pipelength_merge1 = merge_pipelength[_merge_names[0]]
    pipediameter_merge1 = merge_pipediameter[_merge_names[0]]
    pipearea_merge1 = merge_pipearea[_merge_names[0]]

if len(_merge_names) >= 2:
    pipelength_merge2 = merge_pipelength[_merge_names[1]]
    pipediameter_merge2 = merge_pipediameter[_merge_names[1]]
    pipearea_merge2 = merge_pipearea[_merge_names[1]]

