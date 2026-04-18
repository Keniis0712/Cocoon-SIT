# CocoonTagService

源码：`backend/app/services/workspace/cocoon_tag_service.py`

## 功能

- 创建 cocoon 与 tag 的绑定关系。
- 同时把 tag 同步进 `SessionState.active_tags_json`。

## 对外接口

- `bind_tag(session, cocoon_id, tag_id)`

## 交互方式

- 由 `workspace/tags.py` 调用。
- 下游写 `cocoon_tag_bindings` 和 `session_states`。
