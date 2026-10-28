# 接口契约

统一前缀 /api/v1
统一响应：{ "code": 0, "message": "ok", "data": ... }；错误 code 非 0
分页响应：data = { "items": [], "total": 0, "page": 1, "page_size": 20 }
鉴权：Authorization: Bearer <token>
错误码：400 参数错 / 401 未登录 / 403 无权限 / 404 不存在 / 409 冲突 / 422 校验失败 / 501 未实现

## 认证
### POST /auth/register
请求：{ username: str, email: str, password: str }
响应 data：{ id, username, email, role }
错误：409 用户名或邮箱已存在；422 校验失败

### POST /auth/login
请求：{ account: str, password: str }
响应 data：{ access_token: str, token_type: "bearer", user: { id, username, email, role } }
错误：401 账号或密码错误；403 账号被禁用

### GET /auth/me
响应 data：{ id, username, email, role, status, created_at }
错误：401

## 词书（用户端）
### GET /wordbooks
查询：page, page_size
响应 items：{ id, name, description, level, word_count, my_progress: { mastered, total } }
规则：仅返回 status=published

### GET /wordbooks/{id}
响应 data：{ id, name, description, level, word_count }
错误：404

### GET /wordbooks/{id}/words
查询：page, page_size, mastery（可选 0/1/2）
响应 items：{ id, spelling, phonetic_uk, phonetic_us, meaning_cn, part_of_speech, mastery_level }
错误：404

### POST /wordbooks/{id}/start
响应 data：{ user_wordbook_id, status }
规则：已存在则返回既有记录

## 发音
### GET /words/{word_id}/audio
响应 data：{ audio_url, tts_text?, fallback? }
规则：优先返回词库自带音频；无音频时 tts_text 返回单词拼写，fallback=tts
错误：404

### GET /words/{word_id}/audio/file
查询：accent=us|uk（默认 us）
响应：audio/wav（系统语音合成的单词读音，服务端按单词与口音缓存）
错误：404；503 系统语音不可用

## 练习（核心）
### POST /practice/sessions
请求：{ wordbook_id?: int, mode: "normal"|"wrong_only", count?: int, strict_mode?: bool }
响应 data：{ session_id, total, questions: [ { word_id, phonetic_uk, phonetic_us, meaning_cn, part_of_speech, hint: { length: int } } ], notice?: str }
规则：
- normal 需 wordbook_id；wrong_only 忽略 wordbook_id
- 出题不返回 spelling / example；hint 仅返回 length，首字母提示为后续功能
- 词数不足按实际返回并附 notice
错误：400 空词书或错词本为空；404 词书不存在

### POST /practice/sessions/{session_id}/answer
请求：{ word_id: int, user_input: str, used_hint: bool }
响应 data：{ is_correct, mastery_level, correct_spelling?: str, example_en?: str, example_cn?: str }
规则：
- 仅 is_correct=false 时返回 correct_spelling 与例句
- 同一题重复提交不重复计分，返回首次结果
错误：404 session 或 word 不存在；409 session 已结束

### POST /practice/sessions/{session_id}/finish
响应 data：{ session_id, total, correct, accuracy, duration_seconds }
错误：404

### GET /practice/sessions/{session_id}
响应 data：{ id, mode, total_count, correct_count, status, started_at, finished_at }

## 错词本
### GET /wrong-words
查询：page, page_size, resolved（默认 false）
响应 items：{ word_id, spelling, phonetic_uk, phonetic_us, meaning_cn, wrong_count, last_wrong_at, resolved }

### DELETE /wrong-words/{word_id}
响应 data：{ removed: true }
错误：404

## 统计
### GET /stats/overview
响应 data：{ total_practiced, accuracy, streak_days, mastered_words, wrong_words_count }

### GET /stats/daily
查询：from, to
响应 data：{ items: [ { date: "YYYY-MM-DD", answered: int, correct: int } ] }

## 管理员 · 词书
### POST /admin/wordbooks
请求：{ name, description?, level? }
响应 data：{ id, name, status }
错误：403；422

### PUT /admin/wordbooks/{id}
请求：{ name?, description?, level?, status? }
响应 data：{ id, name, status }

### DELETE /admin/wordbooks/{id}
响应 data：{ deleted: true }
规则：仅词书下无单词时可删除；存在单词时返回 409，需先清空词书内单词，不支持 force 级联删除。

### POST /admin/wordbooks/{id}/words
请求：{ spelling, phonetic_uk?, phonetic_us?, meaning_cn?, part_of_speech?, example_en?, example_cn?, audio_url?, sort_order? }
错误：409 同词书内重复

### PUT /admin/words/{id}
### DELETE /admin/words/{id}

### POST /admin/wordbooks/{id}/import/preview
Content-Type: multipart/form-data
字段：file
响应 data：{ file_name, sheet_name, headers, rows, total_rows }
规则：支持 CSV / TSV / TXT / XLSX；返回表头与前 20 行样本

### POST /admin/wordbooks/{id}/import
Content-Type: multipart/form-data
字段：file、mapping（JSON 字符串，列名到列下标的映射）
响应 data：{ import_job_id }
状态码：202
规则：立即返回 job_id，后台逐行校验并导入；合法行入库，失败行记录明细

### GET /admin/import-jobs/{id}
响应 data：{ id, status, total_rows, success_rows, failed_rows, errors: [ { row, content, reason } ] }
状态：pending / processing / done / failed

## 管理员 · 用户
### GET /admin/users
查询：page, page_size, keyword, status
响应 items：{ id, username, email, role, status, created_at, total_practiced }

### PATCH /admin/users/{id}/status
请求：{ status: "active"|"disabled" }
响应 data：{ id, status }
规则：不能禁用自己

### POST /admin/users/{id}/reset-password
请求：{ new_password }
响应 data：{ reset: true }

### GET /admin/users/{id}/stats
响应 data：同 /stats/overview

### POST /admin/users/{id}/profile
管理员触发指定用户的“学情画像分析体”。后端将 word_progress、wrong_words、
practice_sessions 装入 Blackboard Context。控制器按技能匹配度、优先级和依赖关系
调度数据、习惯、诊断、规划四位知识源；每次贡献以 BlackboardEntry 写入黑板，
最终由控制器评估整体置信度并组装可渲染标签与雷达图的结构化 JSON。

响应 data：
```json
{
  "user": { "id": 1, "username": "learner" },
  "generated_at": "2026-10-24T00:00:00Z",
  "cache": { "hit": false, "ttl_seconds": 21600, "expires_at": "2026-10-24T06:00:00Z" },
  "coverage": {
    "word_progress_count": 120,
    "wrong_word_count": 18,
    "practice_session_count": 35,
    "first_practice_at": "2026-09-01T08:00:00",
    "last_practice_at": "2026-10-23T12:30:00"
  },
  "summary": {
    "headline": "learner 的学情画像：良好，正确率稳定",
    "confidence": 0.74,
    "level": "good",
    "tags": ["正确率稳定", "连续打卡", "re- 前缀薄弱"],
    "radar_metrics": [
      { "key": "accuracy", "label": "正确率", "score": 82, "category": "data" }
    ],
    "highlights": ["近期正确率较前期提升 6.0 个百分点"],
    "risks": ["re- 前缀错词占比偏高"]
  },
  "agents": {
    "data": { "source": "llm", "confidence": 0.82, "summary": "...", "tags": [], "accuracy_trend": [], "vocabulary_distribution": [], "metrics": [], "highlights": [], "risks": [] },
    "habit": { "source": "llm", "confidence": 0.68, "summary": "...", "tags": [], "weekly_frequency": [], "checkin_pattern": [], "average_duration_minutes": 18.5, "total_duration_minutes": 647.5, "active_days": 24, "current_streak_days": 4, "longest_streak_days": 9, "preferred_time_slot": "晚间", "metrics": [], "highlights": [], "risks": [] },
    "diagnosis": { "source": "llm", "confidence": 0.76, "summary": "...", "tags": [], "error_patterns": [], "focus_words": [], "metrics": [], "risks": [] },
    "planner": { "source": "llm", "confidence": 0.75, "summary": "...", "tags": [], "review_plan": [], "weekly_goals": [], "recommendations": [], "metrics": [] }
  },
  "agent_sequence": ["data", "habit", "diagnosis", "planner"]
}
```
说明：
- `source=heuristic` 表示真实模型不可用或输出不是合法 JSON，已自动回退到可复现的本地统计结果。
- 每位专家的 `confidence` 与 `summary.confidence` 均为 0~1；规划专家依赖前三份黑板条目。
- 控制器通过 `BlackboardEntry` 保留来源、标签、时间戳和置信度，可支持后续审计与扩展。
- `radar_metrics` 中每个 `score` 均为 0~100，可直接映射 ECharts/Chart.js 雷达图。
- 缓存键包含学习数据指纹；数据未变化时直接返回缓存报告，默认 TTL 由
  `PROFILE_CACHE_TTL_SECONDS` 控制（21600 秒）。数据变化后自动生成新报告。
- 未登录返回 401，非管理员返回 403，用户不存在返回 404。

## 管理员 · 概览
### GET /admin/overview
响应 data：{ total_users, active_users, total_wordbooks, total_words, today_sessions, today_answers }

## 管理员 · MCP 审批
以下接口均需要管理员令牌。MCP 客户端提交的增删改申请由这里审批。

### GET /admin/mcp-changes
查询：page, page_size, status（pending / approved / executed / rejected / failed / expired / cancelled）
响应 items：
{ id, action_type, target_type, target_id, payload, summary, reason, status,
  requested_by, requested_by_username, approved_by, client_name, result,
  error_message, created_at, expires_at, approved_at, executed_at }
规则：请求时会先把已过期的 pending 申请标记为 expired；按 created_at 倒序返回。

### GET /admin/mcp-changes/{id}
响应 data：同上单条记录。
错误：404 申请不存在

### POST /admin/mcp-changes/{id}/approve
响应 data：执行后的申请记录，`status=executed`，`result` 含执行结果（如 `word_id` / `wordbook_id` / `import_job_id`）。
规则：
- 仅 `pending` 且未过期可审批；使用条件更新防止并发重复执行。
- 执行失败时申请记为 `failed`，仍返回对应业务错误。
- `word.import` 审批通过后创建 `import_jobs` 记录并在后台解析文件。
错误：404 不存在；409 已被处理或已过期；422 执行参数失效

### POST /admin/mcp-changes/{id}/reject
请求：{ reason?: str（≤500） }
响应 data：`status=rejected` 的申请记录。
错误：404；409 已被处理

## 管理员 · MCP 接入令牌
所有接口需要管理员 JWT；客户端令牌明文只在创建响应出现一次。

### GET /admin/mcp-tokens/connection
响应 data：{ enabled: bool, endpoint: str, default_expires_in_days: int }

### GET /admin/mcp-tokens
响应 data：{ items: [ { id, name, token_prefix, scopes, created_by, created_by_username,
created_at, expires_at, last_used_at, revoked_at } ] }
规则：不返回令牌明文与哈希；`scopes` 为 read / write。

### POST /admin/mcp-tokens
请求：{ name: str（≤100）, scopes: "read" | "write"（默认 read）, expires_in_days: int | null（默认 90） }
响应 201 data：令牌字段 + { token: "mcp_...", endpoint: str }
规则：`token` 只在本响应返回一次；`expires_in_days=null` 表示永不过期。

### POST /admin/mcp-tokens/{id}/revoke
响应 data：被吊销的令牌记录；重复吊销返回 409。

## MCP 服务（Streamable HTTP）
- 端点：`POST /mcp`，独立于 `/api/v1`；需在 `.env` 设置 `MCP_ENABLED=true` 后启用。
- 鉴权：`Authorization: Bearer mcp_...`（管理端创建的长期客户端令牌）或 `Bearer <管理员 JWT>`；
  缺失或无效返回 401，非管理员返回 403。
- 权限：`scopes=read` 的令牌只能调用只读工具；`scopes=write` 才能调用 `propose_*` 与 `cancel_change_request`，
  且写操作仍需人工审批。
- 传输：stateless streamable HTTP，JSON 响应；待审批申请默认 30 分钟过期（`MCP_CONFIRM_TTL_MINUTES`）。

只读工具：
`admin_overview`、`list_users`、`get_user_stats`、`list_wordbooks`、`list_words`、`get_import_job`

写提案工具（只创建待审批记录，不直接写业务数据）：
`propose_wordbook_create/update/delete`、`propose_word_create/update/delete`、
`propose_user_status`、`propose_profile_refresh`、`propose_import`、`preview_import`

申请追踪工具：
`get_change_request`、`list_change_requests`、`cancel_change_request`

规则：
- 写工具返回 `request_id` 与 `pending` 状态，管理端审批后才会执行。
- 不开放重置用户密码。
- 批量导入使用 base64 文件内容，解码后上限沿用 10MB，文件暂存在 `mcp_import_uploads`。
- 每次工具调用、提案、审批与驳回写入 `mcp_audit_logs`；密码、令牌、文件内容脱敏。

## AI 对话会话
所有接口需要登录，仅能访问当前用户自己的会话。

### GET /ai/sessions?page=&page_size=
响应 data：
{ items: [ { id, title, scene, created_at, updated_at, message_count } ], total, page, page_size }
按 `updated_at` 倒序排列。

### POST /ai/sessions
请求：{ title?: str, scene?: str }
响应 201 data：{ id, title, scene, created_at, updated_at }

### GET /ai/sessions/{id}
响应 data：
{ id, title, scene, created_at, updated_at, messages: [ { id, role, content, created_at } ] }
消息按 `id` 正序。会话不存在或不属于当前用户统一返回 404。

### DELETE /ai/sessions/{id}
响应 data：{ deleted: true }；消息随外键级联删除。

## 智能伴学 Agent（Router + Skill）
### POST /agent/chat
请求：
{ message: str, scene: str | null, conversation_id?: int | null,
  history: [ { role: "user" | "assistant", content: str } ] }

- 传入 `conversation_id` 时，后端校验会话归属并读取最近 20 条数据库消息作为上下文；
- 不传时新建会话，标题取首条用户消息压缩空白后的前 30 字；
- 用户消息在流开始前写入 `ai_messages`，assistant 全文在流结束后写入；
  客户端中断时保存已生成的部分文本。

响应：SSE 流（text/event-stream），事件序列：
- event: meta  data:
  {
    intent: "EXPLAIN_WORD" | "GRAMMAR" | "ORAL_PRACTICE" | "TRANSLATION" | "GENERAL",
    skill: "explain_word" | "grammar" | "oral_practice" | "translation" | "general",
    scene: str | null,
    confidence: 0~100,
    fallback_used: bool,
    candidates: [ { intent: str, skill: str, score: 0~100 } ],
    reason: str | null,
    conversation_id: int
  }
- event: delta  data: { content: str }（增量文本，前端打字机拼接）
- event: done  data: { finish_reason: "stop" }
- event: error  data: { message: str }（生成失败时出现，已生成的部分仍会落库）

说明：
- Router 先做本地关键词匹配，意图明确时直接分发；未命中关键词时再调用模型为全部技能评分，取最高分技能分发。
- 模型调用或 JSON 解析失败时，使用本地关键词规则，`fallback_used=true`。
- `GENERAL` 是默认兜底技能；`TRANSLATION` 处理中英互译。
- scene 取值 restaurant / interview / travel / campus，仅 ORAL_PRACTICE 意图使用。
- 未配置 AI_PROVIDER/AI_PROVIDER_KEY 时返回 Mock 假数据流。
- 未登录返回 401；会话不存在或不属于当前用户返回 404。
