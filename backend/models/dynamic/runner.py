"""Entry point configuration for dynamic TOCOMO/PH_PITZ simulation runs.

Configure the dynamic profile here — specify only the changes from the baseline.
The baseline values (flowrate, temperature, concentrations) are read from input_config.json.

To run TOCOMO dynamic: set RUN_MODE = "tocomo_dynamic" in main.py
To run PH_PITZ dynamic: set RUN_MODE = "phpitz_dynamic" in main.py

Format for time-varying parameters: [(day_of_change, new_value), ...]
Values before the first change point use the input_config.json baseline automatically.
"""

# --- Dynamic profile configuration ---
# Only specify when a value changes from its baseline in input_config.json.
# Example: "flowrate": [(5, 1250.0)] means flowrate stays at config baseline until
# day 5, then switches to 1250.0 kg/h.

DYNAMIC_PROFILE = {
    "plant_profiles": {
        "Plant 1": {
            "flowrate": [(1, 12500.0)],
            # "inlet_conc": {
            #     "SO2": [(2, 8.0), (7, 4.0)],
            #     "NO2": [(2, 2.0)],
            #     "NO" : [(5, 1.0)],
            # },
        },
        # "Plant 2": {
        #     "flowrate": [(3, 750.0)],
        #     # "inlet_conc": {
        #     #     "SO2": [(4, 8.0)],
        #     #     "NO2": [(4, 2.0)],
        #     # },
        # },
        # "Plant 3": {
        #     "flowrate": [(10, 500.0)],
        #     # "inlet_conc": {
        #     #     "SO2": [(6, 8.0)],
        #     #     "NO2": [(6, 2.0)],
        #     # },
        # },
        # "Plant 4": {
        #     "flowrate": [(7, 1500.0)],
        #     "inlet_conc": {
        #         "SO2": [(8, 8.0)],
        #         "NO2": [(8, 2.0)],
        #     },
        # },
    }
}

# Time step size in days
DT_DAYS = 0.01

# Simulation duration in days (or None to auto-derive from max pipe time)
DURATION_DAYS = 2
