# Prompt Renderer

源码：`backend/app/services/prompts/renderer.py`

## 功能

- 负责模板占位符发现、变量快照净化和最终字符串替换。
- 保证复杂对象在进入模板前先被转换成可序列化快照。

## 对外接口

- `sanitize_snapshot(value)`
- `find_placeholders(content)`
- `coerce_render_value(value)`
- `render_template(content, variables)`

## 交互方式

- 由 `PromptTemplateService.render()` 直接调用。
- 生成的快照会继续被 runtime audit helper 写成 artifact。
