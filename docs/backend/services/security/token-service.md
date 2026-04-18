# TokenService

源码：`backend/app/services/security/token_service.py`

## 功能

- 负责 access token、refresh token 的签发和解析。
- 是认证路由和 token 校验服务的底层能力。

## 对外接口

- `create_access_token(user_id)`
- `create_refresh_token(user_id)`
- `decode_token(token)`

## 交互方式

- 由 `access/auth` 路由和 `TokenAuthenticationService` 调用。
- 运行时依赖 `Settings` 提供 secret、过期时间。
