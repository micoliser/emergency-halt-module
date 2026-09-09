from datetime import timezone

from apps.common.units import (
    JS_SAFE_MAX,
    format_gen,
    json_safe,
    normalize_address,
    string_list,
    to_amount_str,
    to_int,
    unix_to_datetime,
)


def test_to_int_accepts_chain_scalar_shapes():
    assert to_int(5) == 5
    assert to_int("5") == 5
    assert to_int("0x10") == 16
    assert to_int(None) == 0
    assert to_int("garbage") == 0
    assert to_int(True) == 1


def test_amounts_round_trip_as_decimal_strings():
    assert to_amount_str(10**18) == "1000000000000000000"
    assert to_amount_str("1000000000000000000") == "1000000000000000000"


def test_format_gen_trims_trailing_zeros():
    assert format_gen(10**18) == "1"
    assert format_gen(15 * 10**17) == "1.5"
    assert format_gen(1) == "0.000000000000000001"
    assert format_gen(0) == "0"


def test_json_safe_stringifies_js_lossy_integers():
    assert json_safe(JS_SAFE_MAX) == JS_SAFE_MAX
    assert json_safe(JS_SAFE_MAX + 1) == str(JS_SAFE_MAX + 1)
    assert json_safe({"bond": 10**18, "ok": True, "none": None}) == {
        "bond": "1000000000000000000",
        "ok": True,
        "none": None,
    }
    assert json_safe([1, b"\xab"]) == [1, "0xab"]


def test_normalize_address_pads_and_lowercases():
    assert normalize_address("0xAB") == "0x" + "0" * 38 + "ab"
    assert normalize_address("0x" + "F" * 40) == "0x" + "f" * 40
    assert normalize_address(None) == ""


def test_string_list_handles_lists_and_pipe_joined_strings():
    assert string_list(["a", "b"]) == ["a", "b"]
    assert string_list("a|b|") == ["a", "b"]
    assert string_list(None) == []


def test_unix_to_datetime():
    moment = unix_to_datetime(1757318400)
    assert moment is not None
    assert moment.tzinfo == timezone.utc
    assert unix_to_datetime(0) is None
