import numpy as np
from backend.variables import *
from backend.constants import *
from calculatedvariables import *

# Create lists for final concentration storage
num_streams = len(pipe_time)
updated_h2so4 = [0.0] * num_streams
updated_h2o = [0.0] * num_streams
updated_so3 = [0.0] * num_streams
updated_no2 = [0.0] * num_streams
updated_o2 = [0.0] * num_streams
updated_no = [0.0] * num_streams
updated_so2 = [0.0] * num_streams
updated_h2s = [0.0] * num_streams
updated_hno3 = [0.0] * num_streams
updated_hno2 = [0.0] * num_streams

# loop every second
dt = 1.0

for stream_idx in range(num_streams):
  current_pipe_time = pipe_time[stream_idx] #extracts number from a list of streams
  time = 0.0

  # Initial concentrations
  c_h2so4 = 0.0
  c_h2o = initial_h2o_conc[stream_idx]
  c_so3 = initial_so3_conc[stream_idx]
  c_no2 = initial_no2_conc[stream_idx]
  c_o2 = initial_o2_conc[stream_idx]
  c_no = initial_no_conc[stream_idx]
  c_so2 = 0.0
  c_h2s = initial_h2s_conc[stream_idx]
  c_hno3 = 0.0
  c_hno2 = 0.0

  # Iterate through each second
  while time < current_pipe_time:
    time += dt

    #SO3 + H2O -> H2SO4
    if c_so3 > 0 and c_h2o > 0:
      prodrate_h2so4_i = k_h2so4 * c_so3 * c_h2o
      prodconc_h2so4_i = max(0.0, min(prodrate_h2so4_i * dt, c_so3, c_h2o)) #limiting factor logic
      c_h2so4 += prodconc_h2so4_i
      c_h2o -= prodconc_h2so4_i
      c_so3 -= prodconc_h2so4_i

    #2NO + O2 -> 2NO2
    if c_no > 0 and c_o2 > 0:
      prodrate_no2_i = 2 * k_no2 * (c_no ** 2) * c_o2
      prodconc_no2_i = max(0.0, min(prodrate_no2_i * dt, c_no, c_o2 * 2)) #limiting factor logic
      c_no2 += prodconc_no2_i
      c_o2 -= prodconc_no2_i / 2
      c_no -= prodconc_no2_i

    #H2S + 3/2 O2 -> SO2 + H2O
    if c_h2s > 0 and c_o2 > 0:
      prodrate_so2_i = k_so2_h2o * c_h2s * c_o2
      prodconc_so2_i = max(0.0, min(prodrate_so2_i * dt, c_h2s, c_o2 * (2 / 3))) #limiting factor logic
      c_so2 += prodconc_so2_i
      c_h2o += prodconc_so2_i
      c_h2s -= prodconc_so2_i
      c_o2 -= 1.5 * prodconc_so2_i

    #2NO2 + H2O -> HNO3 + HNO2
    if c_no2 > 0 and c_h2o > 0:
      prodrate_hno3_i = k_hno3_hno2 * c_no2 * c_h2o
      prodconc_hno3_i = max(0.0, min(prodrate_hno3_i * dt, c_no2 / 2, c_h2o)) #limiting factor logic
      c_hno3 += prodconc_hno3_i
      c_hno2 += prodconc_hno3_i
      c_h2o -= prodconc_hno3_i
      c_no2 -= 2 * prodconc_hno3_i

    #2SO2 + O2 -> 2SO3
    if c_so2 > 0 and c_o2 > 0:
      prodrate_so3_i = k_so3 * c_so2 * c_o2
      prodconc_so3_i = max(0.0, min(prodrate_so3_i * dt, c_so2 / 2, c_o2)) #limiting factor logic
      c_so3 += prodconc_so3_i
      c_so2 -= prodconc_so3_i
      c_o2 -= prodconc_so3_i / 2

  # Store final concentrations in mol/L for the current stream
  updated_h2so4[stream_idx] = c_h2so4
  updated_h2o[stream_idx] = c_h2o
  updated_so3[stream_idx] = c_so3
  updated_no2[stream_idx] = c_no2
  updated_o2[stream_idx] = c_o2
  updated_no[stream_idx] = c_no
  updated_so2[stream_idx] = c_so2
  updated_h2s[stream_idx] = c_h2s
  updated_hno3[stream_idx] = c_hno3
  updated_hno2[stream_idx] = c_hno2


