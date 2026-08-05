#Molar mass
#Might need to be more accurate
molecular_weights = {
    "O2": 32,
    "H2O": 18,
    "NO": 30,
    "NO2": 46,
    "SO3": 80,
    "H2S": 34,
    "CO2": 44,
    "H2SO4": 98,
    "HNO3": 63,
    "SO2": 64,
    "HNO2": 47,
    "N2": 28,
}

mw_o2 = molecular_weights["O2"]
mw_h2o = molecular_weights["H2O"]
mw_no = molecular_weights["NO"]
mw_no2 = molecular_weights["NO2"]
mw_so3 = molecular_weights["SO3"]
mw_h2s = molecular_weights["H2S"]
mw_co2 = molecular_weights["CO2"]
mw_h2so4 = molecular_weights["H2SO4"]
mw_hno3 = molecular_weights["HNO3"]
mw_so2 = molecular_weights["SO2"]
mw_hno2 = molecular_weights["HNO2"]
mw_n2 = molecular_weights["N2"]

# assuming ideal gas behavior
R = 8.314  # J/(mol*K)

SPECIES_ORDER = ["H2O", "O2", "N2", "SO2", "NO2", "H2S", "NO", "CO2", "H2SO4", "HNO3", "HNO2", "SO3"]