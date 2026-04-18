# WakeupCommandParser

源码：`backend/app/services/runtime/meta/wakeup_command_parser.py`

## 功能

- 专门解析用户消息里的 `/wakeup` 指令。
- 把文本命令转成 `SchedulerNode` 可消费的统一 hint 格式。

## 对外接口

- `parse(latest_content)`

## 交互方式

- 由 `MetaNode` 调用。
- 输出字段包括 `delay_seconds`、`reason`、`payload_json`。

## 支持格式

- `/wakeup 15m xxx`
- `/wakeup 2h xxx`
- `/wakeup 1d xxx`
