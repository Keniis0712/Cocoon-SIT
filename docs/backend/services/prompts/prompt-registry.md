# Prompt Registry

源码：`backend/app/services/prompts/registry.py`

## 功能

- 声明系统内置模板的默认内容。
- 声明每种模板类型允许使用的变量及其语义说明。

## 对外接口

- `DEFAULT_TEMPLATES`
- `PROMPT_VARIABLES_BY_TYPE`

## 交互方式

- 被 `PromptTemplateService.ensure_defaults()` 和 `upsert_template()` 使用。
- 也给前端和文档提供模板变量约束的事实来源。

## 注意点

- runtime 新增变量时，需要同步更新这里，否则模板写入会被拒绝。
