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
    "S8": 256,
    "NH3": 17,
    "N2O": 44,
    "N2O4": 92,
    "NH4HSO4": 115,
    "HCHO": 30,
    "CH3CHO": 44,
    "CH3COCH3": 58,
    "HCOOH": 46,
    "CH3COOH": 60
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
mw_s8 = molecular_weights["S8"]
mw_nh3 = molecular_weights["NH3"]
mw_n2o = molecular_weights["N2O"]
mw_n2o4 = molecular_weights["N2O4"]
mw_nh4hso4 = molecular_weights["NH4HSO4"]
mw_hcho = molecular_weights["HCHO"]
mw_ch3cho = molecular_weights["CH3CHO"]
mw_ch3coch3 = molecular_weights["CH3COCH3"]
mw_hcooh = molecular_weights["HCOOH"]
mw_ch3cooh = molecular_weights["CH3COOH"]

# assuming ideal gas behavior
R = 8.314  # J/(mol*K)

SPECIES_ORDER = ["H2O", "O2", "N2", "SO2", "NO2", "H2S", "NO", "CO2", "H2SO4", "HNO3", "HNO2", "SO3", "S8", "NH3", "N2O", "N2O4", "NH4HSO4", "HCHO", "CH3CHO", "CH3COCH3", "HCOOH", "CH3COOH"]