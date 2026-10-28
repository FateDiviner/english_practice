# 验收自检表

> 核对日期：2026-10-28。证据以仓库中的测试与实现文件为准；未执行的手工验证会明确标注。

## 一、F1–F14 功能自检

| 功能 | 状态 | 主要证据 | 备注 |
|---|---|---|---|
| F1 注册与登录 | 通过 | `backend/tests/test_auth.py`、`frontend/src/views/auth/`、`router/index.js` | JWT、bcrypt、路由守卫均已覆盖 |
| F2 管理员创建词书 | 通过 | `backend/tests/test_admin_wordbooks.py`、`WordbookManage.vue` | 有单词时禁止删除 |
| F3 管理员导入单词 | 通过 | `backend/tests/test_admin_import.py`、`ImportWizard.vue` | 支持 CSV/TSV/TXT/XLSX |
| F4 选择词书开始默写 | 通过 | `backend/tests/test_practice_sessions.py`、`Practice.vue` | 出题响应不含拼写 |
| F5 判分与即时反馈 | 通过 | `backend/tests/test_grading.py`、`test_practice_answer.py`、`QuestionCard.vue` | 英美拼写、宽松模式、就地反馈 |
| F6 错词本自动生成 | 通过 | `backend/tests/test_wrong_words.py`、`test_practice_answer.py` | 连续正确 2 次消解 |
| F7 掌握度与词书进度 | 通过（本轮修复） | `backend/tests/test_user_wordbooks.py`、`WordbookList.vue`、`WordbookDetail.vue` | 此前 `mastered` 写死 0、`mastery_level` 返回 null，已修复 |
| F8 错词专项重练 | 通过 | `test_practice_sessions.py::test_wrong_only_uses_only_unresolved_wrong_words` | 空错词本返回 40001 |
| F9 个人数据看板 | 通过 | `backend/tests/test_stats.py`、`Profile.vue` | 连续天数按自然日 |
| F10 管理员用户管理 | 通过 | `backend/tests/test_admin_users.py`、`UserManage.vue` | 禁用、重置密码、查看数据 |
| F11 发音播放 | 通过 | `backend/tests/test_audio.py`、`AudioButton.vue` | 无音频用系统语音合成，失败回退浏览器 TTS |
| F12 导入任务进度 | 通过 | `test_admin_import.py`、`ImportWizard.vue` | 状态与失败行明细 |
| F13 管理员数据概览 | 通过 | `backend/tests/test_admin_stats.py`、`Overview.vue` | 六项指标 |
| F14 AI 英语对话（原预留） | 已由正式实现取代 | 见下节 | 原“返回 501”的占位验收不再适用 |
| F14 AI 英语对话（正式） | 通过（本轮实现） | `backend/tests/test_ai.py`、`test_agent.py`、`frontend/tests/sse.test.js`、`AiChat.vue` | 见下节 |
| F15 管理端 MCP 服务 | 通过（本轮实现） | `backend/tests/test_mcp.py`、`McpApprovals.vue` | 见 F15 验收点 |

### F14 新验收点

- [x] 会话列表、创建、详情、删除接口可用，且仅能访问自己的会话
- [x] `/agent/chat` 返回 SSE，事件为 meta / delta / done / error
- [x] `meta` 回传 `conversation_id`，标题按首条消息自动生成并截断
- [x] 用户消息在流开始前落库，assistant 全文在流结束后落库
- [x] 客户端中断时保存已生成的部分回复
- [x] 前端流式打字机、停止生成、会话切换/删除、场景选择
- [x] 刷新页面后可重新载入历史消息
- [x] 不引入模型 SDK，真实模型通过 OpenAI 兼容 HTTP 接口接入
- [x] 未配置模型时使用 Mock 客户端，链路可完整跑通
- [x] 管理端用户数据抽屉可生成学情画像

### F15 验收点

- [x] `/mcp` 以 Streamable HTTP 挂载；无令牌返回 401，普通用户令牌返回 403，管理员可完成握手
- [x] 写工具只创建 `pending` 申请，不直接修改业务数据
- [x] 管理端审批通过后数据真实写入，重复审批返回 409
- [x] 驳回、过期、取消都不会执行业务写入
- [x] 批量导入审批后创建 `import_jobs`，后台任务完成导入并记录失败行
- [x] 工具调用、提案、审批与驳回写入 `mcp_audit_logs`，敏感参数脱敏
- [x] 不开放重置用户密码
- [x] 管理端 `/admin/mcp-approvals` 可选择待审批申请并通过/驳回

### 尚未覆盖 / 后续项

- 未接真实模型服务做端到端联调；默认 Mock。配置 `AI_PROVIDER=openai` 后需另行验证真实回复。
- 原 F14 设想中的“对话中标记生词加入错词本”“朗读 AI 回复”“对话评分”仍未实现。
- 本轮未逐页做浏览器手工走查；已用 preview 验证登录与首页 AI 入口，AI 对话页与学情画像抽屉未完成逐页操作（预览工具分类器超时），相关 UI 由 `pnpm lint`、`pnpm test`、`pnpm build` 与接口级验证覆盖。
- 未在 Swagger 中手工复核所有接口，接口行为由 pytest 覆盖。

## 二、`.agents/rules/11-checklist.md` 自检

| 检查项 | 结论 | 说明 |
|---|---|---|
| 路由有鉴权与角色校验 | 通过 | 前端路由守卫 + 后端 `get_current_user` / `require_admin` |
| 出题接口无答案泄露 | 通过 | `test_practice_sessions.py` 断言响应无 spelling |
| Pydantic schema 覆盖所有输入输出 | 通过 | 新增 `schemas/ai.py`、`schemas/agent.py` 字段 |
| 判分在 service 层且处理英美拼写 | 通过 | `services/grading.py` + `spelling_variants.py` |
| 数据库变更走迁移 | 通过 | 本轮复用 `ai_conversations` / `ai_messages`，无新迁移 |
| 前端无硬编码颜色，走 tokens | 通过 | 新组件仅使用 `--color-*` / `--font-*` 等变量 |
| 判分反馈就地呈现，无弹窗 | 通过 | 练习页沿用原有就地反馈 |
| 无未声明依赖、无硬编码密钥 | 通过 | 未新增依赖；密钥仍走 `.env` |
| 错误响应符合统一包装格式 | 通过 | 复用 `AppError` 与 `ApiResponse` |
| 单文件不超 300 行 | 通过 | AiChat 231、ProfileReport 272、ProfileAgentSection 184、UserManage 256 |
| 动手前已说明改动文件并获确认 | 通过 | 实施前已提交计划并获批准 |
| 本次只做一个原子任务 | 通过 | 按 F7、AI 后端、SSE、对话页、画像、文档、示例数据拆分提交 |
| 函数 ≤40 行、文件 ≤300 行、嵌套 ≤3 层 | 基本通过 | 超长组件已拆分；查询与编排函数保持浅层嵌套 |
| 无魔法数字，阈值已提常量 | 通过 | 标题长度、历史条数、SSE 分包边界均已提常量 |
| 复杂逻辑有注释说明规则来源 | 通过 | 黑板书、SSE 中断落库、F7 统计口径均有说明 |
| service 有对应单元测试且真实通过 | 通过 | 后端 192 个测试全部通过 |
| 已在 Swagger 手动验证接口返回 | 未执行 | 由 pytest 覆盖；如需可按 `.agents/AGENTS.md` 启动后在 `/docs` 复核 |
| 字段名与接口路径与文档一致 | 通过 | 已同步 `docs/api-contract.md` |
