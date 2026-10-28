# 管理端 MCP 客户端接入

本服务把管理后台的只读查询与写操作申请暴露为 MCP 工具。写操作不会直接执行，必须由管理员在
`/admin/mcp-approvals` 页面确认。

## 1. 启用服务

在 `backend/.env` 中设置：

```env
MCP_ENABLED=true
MCP_CONFIRM_TTL_MINUTES=30
```

启动后端：

```bash
conda activate english_practice
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

MCP 端点为 `http://127.0.0.1:8000/mcp`，与 `/api/v1` 相互独立。

## 2. 获取管理员令牌

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"account\":\"<管理员账号>\",\"password\":\"<密码>\"}"
```

响应中的 `data.access_token` 即管理员 JWT。令牌默认 120 分钟过期
（`JWT_EXPIRE_MINUTES`），过期后重新登录并在客户端更新请求头。

## 3. 配置客户端

### Claude Code

```bash
claude mcp add --transport http english-practice-admin http://127.0.0.1:8000/mcp --header "Authorization: Bearer <管理员 JWT>"
```

### 通用 MCP JSON 配置

```json
{
  "mcpServers": {
    "english-practice-admin": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer <管理员 JWT>"
      }
    }
  }
}
```

如果客户端只支持 stdio，可用 `mcp-remote` 之类的桥接工具转发到上面的 HTTP 端点。

## 4. 典型流程

1. 只读查询：`admin_overview`、`list_users`、`list_wordbooks`、`list_words`。
2. 提交变更：例如 `propose_word_create`，返回 `request_id` 与 `status=pending`。
3. 管理员打开管理端 `/admin/mcp-approvals`，核对摘要和参数后点击「通过并执行」。
4. 客户端调用 `get_change_request` 获取执行结果；也可用 `list_change_requests` 查看队列。
5. 审批前可用 `cancel_change_request` 由发起人撤回。

## 5. 工具清单

| 类型 | 工具 |
|---|---|
| 只读 | `admin_overview`、`list_users`、`get_user_stats`、`list_wordbooks`、`list_words`、`get_import_job` |
| 写提案 | `propose_wordbook_create/update/delete`、`propose_word_create/update/delete`、`propose_user_status`、`propose_profile_refresh`、`propose_import`、`preview_import` |
| 追踪 | `get_change_request`、`list_change_requests`、`cancel_change_request` |

不开放：重置用户密码。

## 6. 安全约束

- 每个 HTTP 请求都会校验管理员 JWT，并回查数据库确认 `role=admin`、`status=active`。
- 写工具只写 `mcp_change_requests`，不触碰业务表；执行只发生在管理端审批接口。
- 审批使用条件更新防止并发重复执行；申请默认 30 分钟过期。
- `mcp_audit_logs` 记录工具调用、提案、审批与驳回，参数中的密码/令牌/文件内容会脱敏。
- 导入文件暂存在 `mcp_import_uploads`，上限 10MB，审批执行后标记为已消费。
