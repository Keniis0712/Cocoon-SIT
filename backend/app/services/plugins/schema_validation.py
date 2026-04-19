from __future__ import annotations

from collections.abc import Mapping, Sequence


class PluginSchemaValidationError(ValueError):
    """Raised when plugin config data violates a JSON-schema-like contract."""


def validate_json_schema_value(
    schema: Mapping[str, object] | None,
    value: object,
    *,
    location: str = "$",
) -> None:
    if not schema:
        return

    enum_values = schema.get("enum")
    if isinstance(enum_values, Sequence) and not isinstance(enum_values, (str, bytes)) and enum_values:
        if value not in enum_values:
            raise PluginSchemaValidationError(f"{location} must be one of {list(enum_values)}")

    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, Mapping):
            raise PluginSchemaValidationError(f"{location} must be an object")
        required = schema.get("required")
        if isinstance(required, Sequence) and not isinstance(required, (str, bytes)):
            for item in required:
                key = str(item)
                if key not in value:
                    raise PluginSchemaValidationError(f"{location}.{key} is required")
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            for key, sub_schema in properties.items():
                if key not in value:
                    continue
                if isinstance(sub_schema, Mapping):
                    validate_json_schema_value(sub_schema, value[key], location=f"{location}.{key}")
        return

    if schema_type == "array":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise PluginSchemaValidationError(f"{location} must be an array")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                validate_json_schema_value(item_schema, item, location=f"{location}[{index}]")
        return

    if schema_type == "string":
        if not isinstance(value, str):
            raise PluginSchemaValidationError(f"{location} must be a string")
        return

    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise PluginSchemaValidationError(f"{location} must be a boolean")
        return

    if schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise PluginSchemaValidationError(f"{location} must be an integer")
        return

    if schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PluginSchemaValidationError(f"{location} must be a number")
        return

    if schema_type == "null":
        if value is not None:
            raise PluginSchemaValidationError(f"{location} must be null")
