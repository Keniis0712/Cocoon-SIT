import pytest

from app.services.prompts.renderer import (
    coerce_render_value,
    find_placeholders,
    render_template,
    sanitize_snapshot,
)


def test_sanitize_snapshot_redacts_sensitive_keys_recursively():
    payload = {
        "api_key": "secret",
        "nested": {"token": "value", "safe": 1},
        "items": [{"password": "hidden"}, {"ok": True}],
    }

    assert sanitize_snapshot(payload) == {
        "api_key": "***redacted***",
        "nested": {"token": "***redacted***", "safe": 1},
        "items": [{"password": "***redacted***"}, {"ok": True}],
    }


def test_find_placeholders_and_coerce_render_value():
    assert find_placeholders("Hi {{ name }} and {{name}} {{ count }}") == ["count", "name"]
    assert coerce_render_value("plain") == "plain"
    assert '"x": 1' in coerce_render_value({"x": 1})


def test_render_template_substitutes_sanitized_values_and_raises_for_missing_keys():
    content = "Hello {{ name }}\nConfig: {{ config }}"
    rendered = render_template(content, {"name": "Ada", "config": {"api_key": "secret", "safe": True}})

    assert "Hello Ada" in rendered
    assert "***redacted***" in rendered

    with pytest.raises(KeyError, match="missing"):
        render_template("{{ missing }}", {"name": "Ada"})
