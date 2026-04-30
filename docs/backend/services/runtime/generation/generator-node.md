# GeneratorNode

源码：`backend/app/services/runtime/generation/generator_node.py`

## 功能

- 在 `MetaNode` 决定需要回复时，真正调用 chat provider 生成回复。
- `GeneratorNode` 现在也要求 provider 返回结构化 JSON。
- 当前约定的输出对象主字段是 `reply_text`。

## 结构化输出

- `GeneratorNode` 会给 provider 注入 `COCOON_GENERATOR_OUTPUT_V1` 标记。
- provider 应返回：

```json
{
  "reply_text": "..."
}
```

- runtime 会：
  - 使用 `reply_text` 持久化消息和 memory
  - 基于 `reply_text` 重新切 chunk 做 WS 推送
  - 记录原始 provider 响应和解析后的结构化对象

## 和 wakeup 的关系

- 当当前事件是 idle wakeup 时，prompt 包装层会把 `wakeup_context`、`pending_wakeups`、`now_utc` 带给模型。
- 这让 AI 在真正发出主动消息时，能自然说明“对话安静了一段时间”以及对应原因。
