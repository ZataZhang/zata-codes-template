# API 参考

本页通过 `mkdocstrings` 自动渲染核心模块的公开 API，并补充 HTTP 接口说明。

## 认证接口

所有认证接口位于 `/auth/*`，使用 HTTP-only `session_id` cookie 维持会话。

### `POST /auth/register`

创建新账号并自动登录。

**请求体**

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | string | 用户唯一标识（登录名） |
| `display_name` | string | 显示名称 |
| `email` | string | 邮箱 |
| `password` | string | 密码 |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | string | 用户唯一标识 |
| `display_name` | string | 显示名称 |
| `email` | string | 邮箱 |

**状态码**

- `201 Created`：注册并登录成功
- `400 Bad Request`：参数校验失败或用户已存在

### `POST /auth/login`

使用账号/邮箱和密码登录。

**请求体**

| 字段 | 类型 | 说明 |
|---|---|---|
| `identifier` | string | 用户 ID 或邮箱 |
| `password` | string | 密码 |

**响应**：同 `POST /auth/register`。

**状态码**

- `200 OK`：登录成功
- `401 Unauthorized`：凭据错误

### `POST /auth/logout`

销毁当前会话并清除 cookie。

**状态码**

- `204 No Content`：登出成功

### `GET /auth/me`

获取当前登录用户信息，同时触发会话滑动窗口续期。

**响应**：同 `POST /auth/register`。

**状态码**

- `200 OK`：会话有效
- `401 Unauthorized`：未登录或会话已过期

## 基础设施模块

## 基础设施模块

### `backend.infrastructure.config.settings`

::: backend.infrastructure.config.settings
    handler: python
    options:
      show_root_heading: true
      members_order: source

### `backend.infrastructure.logger`

::: backend.infrastructure.logger
    handler: python
    options:
      show_root_heading: true
      members_order: source

### `backend.infrastructure.persistence.database`

::: backend.infrastructure.persistence.database
    handler: python
    options:
      show_root_heading: true
      members_order: source

### `backend.infrastructure.helpers`

::: backend.infrastructure.helpers
    handler: python
    options:
      show_root_heading: true
      members_order: source

## 模型模块

`create_chat_model` / `list_providers` / `ModelConfigError` 由上方的
`backend.infrastructure.config.settings` 块通过 mkdocstrings 自动渲染。
