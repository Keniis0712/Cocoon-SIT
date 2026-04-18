# MemoryService

源码：`backend/app/services/memory/service.py`

## 功能

- 提供 runtime 可见记忆片段查询。
- 根据 `active_tags` 对记忆做轻量过滤，并在必要时回退到 `MemoryTag` 关联表。

## 对外接口

- `get_visible_memories(session, cocoon_id, active_tags, limit=5)`

## 交互方式

- 上游由 `ContextBuilder` 和 `DurableJobExecutor` 使用。
- 下游读取 `memory_chunks` 和 `memory_tags`。

## 注意点

- 没有 active tag 时按最近时间窗口直接返回。
- 有 active tag 但 `tags_json` 没命中时，会再查 `MemoryTag` 做兜底。
