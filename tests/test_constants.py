import pytest
import backend.constants as constants

@pytest.mark.parametrize(
    "name, value, lower_bound, upper_bound",
    [
        ("mw_o2", constants.mw_o2, 31, 33),
        ("mw_h2o", constants.mw_h2o, 17, 19),
        ("mw_no", constants.mw_no, 29, 31),
        ("mw_no2", constants.mw_no2, 45, 47),
        ("mw_so3", constants.mw_so3, 79, 81),
        ("mw_h2s", constants.mw_h2s, 33, 35),
        ("mw_co2", constants.mw_co2, 43, 45),
        ("mw_h2so4", constants.mw_h2so4, 97, 99),
        ("mw_hno3", constants.mw_hno3, 61, 63),
        ("mw_so2", constants.mw_so2, 63, 65),
        ("mw_hno2", constants.mw_hno2, 45, 47),
    ],
)
def test_molecular_weight_range(name, value, lower_bound, upper_bound):
    assert lower_bound <= value <= upper_bound, (
        f"{name}={value} not in ({lower_bound}, {upper_bound})"
    )

def test_gas_constant_range():
    assert 8.3 <= constants.R <= 8.4, f"R={constants.R} not in (8.3, 8.4)"