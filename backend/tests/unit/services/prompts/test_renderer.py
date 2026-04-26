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
    rendered = coerce_render_value({"x": 1, "prompt": "line1\nline2"})
    assert "x: 1" in rendered
    assert "prompt:" in rendered
    assert "line1\n  line2" in rendered


def test_render_template_formats_runtime_variables_as_natural_language():
    rendered = render_template(
        "角色设定：\n{{ character_settings }}\n\n最近消息：\n{{ visible_messages }}\n\n事件：\n{{ runtime_event }}",
        {
            "character_settings": {
                "description": "一个超级智能体",
                "personality_prompt": "你是智子。\n保持冷静、客观、精准。",
            },
            "visible_messages": [
                {"role": "user", "speaker": "ken", "content": "上下文测试", "tags": ["default"]},
                {"role": "assistant", "is_thought": True, "content": "用户在做上下文验证。", "tags": ["default"]},
            ],
            "runtime_event": {
                "event_type": "chat",
                "target_type": "chat_group",
                "external_sender_display_name": "ken",
                "aggregated_message_count": 1,
                "im_context": {"platform": "nonebot_onebot_v11", "conversation_kind": "group"},
            },
        },
    )

    assert "角色描述：一个超级智能体" in rendered
    assert "你是智子。\n保持冷静、客观、精准。" in rendered
    assert "\\n" not in rendered
    assert "1. 用户 ken：上下文测试（标签：default）" in rendered
    assert "2. 助手内部事件摘要：用户在做上下文验证。（标签：default）" in rendered
    assert "当前事件类型为 chat，目标类型为 chat_group。" in rendered
    assert "IM 上下文：platform=nonebot_onebot_v11，conversation_kind=group。" in rendered


def test_render_template_substitutes_sanitized_values_and_raises_for_missing_keys():
    content = "Hello {{ name }}\nConfig: {{ config }}"
    rendered = render_template(content, {"name": "Ada", "config": {"api_key": "secret", "safe": True}})

    assert "Hello Ada" in rendered
    assert "***redacted***" in rendered

    with pytest.raises(KeyError, match="missing"):
        render_template("{{ missing }}", {"name": "Ada"})
