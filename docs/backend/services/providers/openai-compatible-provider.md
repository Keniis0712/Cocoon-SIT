# OpenAI Compatible Provider

源码：`backend/app/services/providers/openai_compatible.py`

## 功能

- 适配 OpenAI 兼容接口的流式文本生成。
- 将 runtime 组装好的 prompt、messages 和 provider config 发往兼容网关。

## 对外接口

- `stream_text(prompt, messages, model_name, provider_config)`

## 交互方式

- 由 `ProviderRegistry` 返回给 `GeneratorNode` 或 `DurableJobExecutor`。
- 依赖 `provider_config` 中的 `base_url`、`api_key` 等字段。
