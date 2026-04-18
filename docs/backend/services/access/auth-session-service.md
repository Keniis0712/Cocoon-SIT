# AuthSessionService

源码：`backend/app/services/access/auth_session_service.py`

## 功能

- 处理登录、refresh、logout 三条认证会话主流程。
- 把 token 签发、session 持久化、refresh 轮换从 router 中抽离。

## 对外接口

- `login(session, email, password)`
- `refresh(session, refresh_token)`
- `logout(session, refresh_token)`

## 交互方式

- 上游由 `access/auth.py` 路由调用。
- 下游依赖 `TokenService`、`verify_secret`、`AuthSession` 表。
