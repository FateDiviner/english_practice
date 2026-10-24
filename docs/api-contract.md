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

## AI 对话（预留，本期返回 501）
### POST /ai/chat
### GET /ai/sessions
### POST /ai/sessions
响应：{ code: 501, message: "not implemented", data: null }

## 智能伴学 Agent（Router + Skill）
### POST /agent/chat
请求：{ message: str, scene: str | null, history: [ { role: "user" | "assistant", content: str } ] }
响应：SSE 流（text/event-stream），事件序列：
- event: meta  data:
  {
    intent: "EXPLAIN_WORD" | "GRAMMAR" | "ORAL_PRACTICE" | "TRANSLATION" | "GENERAL",
    skill: "explain_word" | "grammar" | "oral_practice" | "translation" | "general",
    scene: str | null,
    confidence: 0~100,
    fallback_used: bool,
    candidates: [ { intent: str, skill: str, score: 0~100 } ],
    reason: str | null
  }
- event: delta  data: { content: str }（增量文本，前端打字机拼接）
- event: done  data: { finish_reason: "stop" }

说明：
- Router 根据注册表动态生成技能说明，请模型为全部技能评分；取最高分技能分发。
- 模型调用或 JSON 解析失败时，使用本地关键词规则，`fallback_used=true`。
- `GENERAL` 是默认兜底技能；`TRANSLATION` 处理中英互译。
- scene 取值 restaurant / interview / hotel / airport，仅 ORAL_PRACTICE 意图使用。
- 未配置 AI_PROVIDER/AI_API_KEY 时返回 Mock 假数据流。
