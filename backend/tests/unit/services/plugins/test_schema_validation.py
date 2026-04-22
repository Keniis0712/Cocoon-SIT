import pytest

from app.services.plugins.schema_validation import (
    PluginSchemaValidationError,
    validate_json_schema_value,
)


def test_validate_json_schema_value_accepts_empty_schema():
    validate_json_schema_value(None, {"x": 1})
    validate_json_schema_value({}, {"x": 1})


def test_validate_json_schema_value_validates_enums_and_scalar_types():
    validate_json_schema_value({"enum": ["a", "b"]}, "a")
    validate_json_schema_value({"type": "string"}, "ok")
    validate_json_schema_value({"type": "boolean"}, True)
    validate_json_schema_value({"type": "integer"}, 3)
    validate_json_schema_value({"type": "number"}, 3.5)
    validate_json_schema_value({"type": "null"}, None)

    with pytest.raises(PluginSchemaValidationError, match="must be one of"):
        validate_json_schema_value({"enum": ["a", "b"]}, "c")
    with pytest.raises(PluginSchemaValidationError, match="must be a string"):
        validate_json_schema_value({"type": "string"}, 1)
    with pytest.raises(PluginSchemaValidationError, match="must be a boolean"):
        validate_json_schema_value({"type": "boolean"}, "true")
    with pytest.raises(PluginSchemaValidationError, match="must be an integer"):
        validate_json_schema_value({"type": "integer"}, True)
    with pytest.raises(PluginSchemaValidationError, match="must be a number"):
        validate_json_schema_value({"type": "number"}, False)
    with pytest.raises(PluginSchemaValidationError, match="must be null"):
        validate_json_schema_value({"type": "null"}, "x")


def test_validate_json_schema_value_validates_objects_and_required_fields():
    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
    }

    validate_json_schema_value(schema, {"name": "demo", "enabled": True})

    with pytest.raises(PluginSchemaValidationError, match=r"\$\.name is required"):
        validate_json_schema_value(schema, {"enabled": True})
    with pytest.raises(PluginSchemaValidationError, match=r"\$\.enabled must be a boolean"):
        validate_json_schema_value(schema, {"name": "demo", "enabled": "yes"})
    with pytest.raises(PluginSchemaValidationError, match=r"\$ must be an object"):
        validate_json_schema_value(schema, [])


def test_validate_json_schema_value_validates_arrays_and_nested_items():
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["count"],
            "properties": {"count": {"type": "integer"}},
        },
    }

    validate_json_schema_value(schema, [{"count": 1}, {"count": 2}])

    with pytest.raises(PluginSchemaValidationError, match=r"\$ must be an array"):
        validate_json_schema_value(schema, "nope")
    with pytest.raises(PluginSchemaValidationError, match=r"\$\[0\]\.count must be an integer"):
        validate_json_schema_value(schema, [{"count": "bad"}])
