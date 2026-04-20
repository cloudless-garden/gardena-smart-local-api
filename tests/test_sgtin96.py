import pytest

from gardena_smart_local_api.sgtin96 import Sgtin96Info

PARSE_CASES = pytest.mark.parametrize(
    "hex_str, expected",
    [
        pytest.param(
            "3034F8EE901267400000B333",
            Sgtin96Info(
                serial=45875,
                company_prefix="4078500",
                item_reference="18845",
                check_digit="6",
                gtin13="4078500188456",
                hex_str="3034F8EE901267400000B333",
            ),
            id="sensor1",
        ),
        pytest.param(
            "3034F8319C0075400000010A",
            Sgtin96Info(
                serial=266,
                company_prefix="4066407",
                item_reference="469",
                check_digit="6",
                gtin13="4066407004696",
                hex_str="3034F8319C0075400000010A",
            ),
            id="irrigation_control",
        ),
    ],
)


@PARSE_CASES
def test_parse_sgtin96(hex_str, expected):
    assert Sgtin96Info.from_hex(hex_str) == expected


@PARSE_CASES
def test_parse_sgtin96_lowercase(hex_str, expected):
    assert Sgtin96Info.from_hex(hex_str.lower()) == expected


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
    assert await Sgtin96Info.from_hex(hex_str).get_model_name() == model_name


def test_parse_sgtin96_invalid_length():
    with pytest.raises(ValueError, match="24 hex characters"):
        Sgtin96Info.from_hex("3034F8EE")


def test_parse_sgtin96_invalid_header():
    with pytest.raises(ValueError, match="invalid header"):
        Sgtin96Info.from_hex("FF34F8EE901267400000B333")
