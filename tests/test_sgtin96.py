import pytest

from gardena_smart_local_api.sgtin96 import SGTIN96Info


@pytest.mark.parametrize(
    "hex_str, model_name",
    [
        pytest.param("3034F8EE901267400000B333", "smart Sensor", id="sensor1"),
        pytest.param(
            "3034F8319C0075400000010A",
            "smart Irrigation Control",
            id="irrigation_control",
        ),
    ],
)
@pytest.mark.asyncio
async def test_parse_sgtin96_model_name(hex_str, model_name):
    assert await SGTIN96Info.from_hex(hex_str).get_model_name() == model_name


def test_parse_sgtin96_invalid_length():
    with pytest.raises(ValueError, match="24 hex characters"):
        SGTIN96Info.from_hex("3034F8EE")


def test_parse_sgtin96_invalid_header():
    with pytest.raises(ValueError, match="invalid header"):
        SGTIN96Info.from_hex("FF34F8EE901267400000B333")


def test_parse_sgtin96_valid_hex():
    hex_str = "3034F8EE901267400000B333"
    info = SGTIN96Info.from_hex(hex_str)
    assert info.serial == 45875
    assert info.company_prefix == "4078500"
    assert info.item_reference == "18845"
    assert info.check_digit == "6"
    assert info.gtin13 == "4078500188456"
