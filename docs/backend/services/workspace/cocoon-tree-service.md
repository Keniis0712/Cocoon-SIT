# CocoonTreeService

源码：`backend/app/services/workspace/cocoon_tree_service.py`

## 功能

- 把平铺的 `Cocoon` 记录组装成递归树结构。
- 将树构建逻辑从 router 中抽离，避免路由文件里夹杂纯结构转换代码。

## 对外接口

- `build_tree(nodes, parent_id=None)`

## 交互方式

- 由 `workspace/cocoons.py` 的树查询路由调用。
- 输入是平铺 cocoon 列表，输出是 `CocoonTreeNode` 列表。
