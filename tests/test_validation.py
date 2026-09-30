import pytest
from src.parse_assets import parse_validation


@pytest.mark.parametrize("raw,expected", [("checked", True), (" TRUE ", True), ("no", False), ("0", False), ("", None), ("not known", None), ("probably", None)])
def test_validation_is_three_state(raw, expected):
    assert parse_validation(raw) is expected


def test_boolean_and_zero_values_are_not_mistaken_for_blank():
    assert parse_validation(False) is False
    assert parse_validation(0) is False
    assert parse_validation("", config={"validation": {"blank_is_unknown": False}}) is False
