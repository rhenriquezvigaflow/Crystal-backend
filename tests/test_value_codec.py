from app.scada.value_codec import (
    is_state_or_bool_value,
    to_storage_fields,
)


def test_int16_named_tag_is_numeric_even_when_value_is_in_state_range():
    assert is_state_or_bool_value(2, "TAGS_01_INT") is False
    assert to_storage_fields(2, "TAGS_01_INT") == (None, 2.0, None)


def test_boolean_named_tag_remains_boolean_state_input():
    assert is_state_or_bool_value(True, "TAGS_03_BOOL") is True
    assert to_storage_fields(True, "TAGS_03_BOOL") == (None, None, True)
