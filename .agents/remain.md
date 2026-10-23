# 剩余任务清单

使用方式：
- 一次只让 AI 做一个任务
- 每个任务先把「发给 AI 的内容」整段贴过去
- AI 完成后按「验收」逐条打勾，通过再进下一个
- 每个任务通过后单独 commit

任务编号规则：阶段.序号，如 5.1、6.3

---

## 阶段 5 收尾

### 5.1 时区关键验证

发给 AI 的内容：
本轮基本通过。补一个时区关键验证后再进下一块：

在 test_stats.py 中新增测试并贴出实际输出：
1. 构造 practice_records，answered_at 存 UTC 2026-10-22 23:30:00
2. 调用 GET /stats/daily?from=2026-10-22&to=2026-10-23
3. 断言该记录落在 2026-10-23（Asia/Shanghai 次日），不是 2026-10-22
4. 断言 streak_days 在该场景下按 2026-10-23 计算

若发现按 UTC 日期分组，修正后重跑。
不改其他逻辑、不建表、不动前端。

验收：
- [x] UTC 23:30 记录落在 Asia/Shanghai 次日
- [x] streak_days 按次日计算
- [x] 该场景已补进 test_stats.py 作为回归测试
- [x] 125 个测试不减少

---

### 5.2 管理员数据概览（F13）

发给 AI 的内容：
进入任务 5.2：管理员数据概览。

范围：
- schemas/admin_stats.py：AdminOverviewOut
- services/admin_stats.py：
  - get_admin_overview()：total_users、active_users（近7天有练习记录）、total_wordbooks、total_words、today_sessions、today_answers
  - 今日按 APP_TIMEZONE 自然日
  - 聚合查询，避免 N+1
- api/v1/admin_stats.py（require_admin）：GET /admin/overview
- 挂进 router.py
- 统一响应包装与业务码
- 测试覆盖：普通用户 40301、未登录 40101、各指标数值正确、无数据返回 0 不报错

约束：不写前端、不建表、不新增迁移。

验收：
- [x] 未登录 40101，普通用户 40301
- [x] 六个指标正确，无数据返回 0
- [x] 今日按 Asia/Shanghai 自然日
- [x] 聚合查询无 N+1
- [x] pytest 真实通过

---

## 阶段 6 发音播放

### 6.1 音频地址与 TTS 兜底

发给 AI 的内容：
进入任务 6.1：发音播放后端支持。

范围：
- 确认 words.audio_url 字段已在模型中，用户端单词/题目响应已包含 audio_url（若出题响应未包含，补上 audio_url 字段，不影响答案安全）
- services/audio.py：
  - get_word_audio(word_id)：返回 audio_url；无则返回 None
- api/v1/audio.py（需登录）：GET /words/{word_id}/audio
  - 响应 { audio_url: str | null, fallback: "tts" | null }
  - 无 audio_url 时 fallback 返回 "tts"，由前端用浏览器 TTS 播放
- 挂进 router.py
- 测试覆盖：有 audio_url 正常返回、无 audio_url 返回 fallback=tts、单词不存在 40401、未登录 40101

约束：
- 不接入第三方 TTS 服务
- 不生成音频文件
- 不建表、不新增迁移
- 不改判分与答题逻辑

验收：
- [x] 有音频返回 audio_url
- [x] 无音频返回 fallback=tts
- [x] 出题响应含 audio_url 且不含 spelling
- [x] 未登录 40101
- [x] pytest 真实通过

---

## 阶段 7 管理员用户管理

### 7.1 用户列表与状态管理

发给 AI 的内容：
进入任务 7.1：管理员用户列表与状态管理。

范围：
- schemas/admin_user.py：AdminUserItem、AdminUserListOut、UserStatusIn
- services/admin_user.py：
  - list_users(page, page_size, keyword, status)：keyword 模糊匹配 username/email；返回 total_practiced
  - update_user_status(admin_id, target_id, status)：
    - 不能禁用自己，返回 40001
    - 状态变更后该用户已有 token 立即失效（依赖 get_current_user 查 status，已实现）
- api/v1/admin_users.py（require_admin）：
  - GET /admin/users
  - PATCH /admin/users/{id}/status
- 挂进 router.py
- 统一响应包装与业务码
- 测试覆盖：分页、keyword 搜索、status 筛选、禁用成功、禁用自己被拒、禁用后该用户访问接口 40101、普通用户 40301

约束：不写重置密码、不写用户数据查看、不写前端、不建表。

验收：
- [ ] 列表分页、keyword、status 筛选有效
- [ ] 禁用后该用户已有 token 立即失效
- [ ] 不能禁用自己
- [ ] 普通用户 40301
- [ ] pytest 真实通过

---

### 7.2 重置密码与查看用户数据

发给 AI 的内容：
进入任务 7.2：重置密码与查看用户数据。

范围：
- schemas/admin_user.py 补：ResetPasswordIn、UserStatsOut
- services/admin_user.py：
  - reset_password(admin_id, target_id, new_password)：
    - 密码长度≥8，否则 42201
    - bcrypt 哈希后更新
  - get_user_stats(target_id)：复用 stats.get_overview 逻辑，返回该用户统计
- api/v1/admin_users.py 补：
  - POST /admin/users/{id}/reset-password
  - GET /admin/users/{id}/stats
- 测试覆盖：重置成功、长度不足 42201、用户不存在 40401、查看统计数据正确、普通用户 40301

约束：不写前端、不建表、不改认证接口。

验收：
- [ ] 重置后新密码可登录，旧密码失效
- [ ] 长度不足 42201
- [ ] 查看统计数据与 stats/overview 一致
- [ ] 普通用户 40301
- [ ] pytest 真实通过

---

## 阶段 8 AI 对话占位

### 8.1 AI 对话表与路由占位

发给 AI 的内容：
进入任务 8.1：AI 对话占位。

范围：
- 按 data-dictionary 创建模型：
  - models/ai_conversation.py：AiConversation（id、user_id、title、scene、created_at、updated_at），user_id FK CASCADE
  - models/ai_message.py：AiMessage（id、conversation_id、role、content、created_at），conversation_id FK CASCADE，索引 idx_ai_messages_conversation
  - __init__.py 导出
- 生成 Alembic 迁移并 upgrade head
- schemas/ai.py：占位响应 schema
- api/v1/ai.py：
  - POST /ai/chat
  - GET /ai/sessions
  - POST /ai/sessions
  - 全部返回 501，业务码 50101，message="not implemented"
  - 均需登录
- core/config.py 增加可选 ai_provider_url、ai_api_key（默认空）
- .env.example 补 AI_PROVIDER_URL、AI_API_KEY 占位
- 挂进 router.py
- 数据字典补两张表
- 测试覆盖：三个接口未登录 40101、登录后返回 50101、表结构约束正确

约束：
- 不接入任何大模型
- 不写对话业务逻辑
- 不引入模型 SDK
- 密钥不得硬编码

验收：
- [x] 两张表字段、外键、索引正确
- [x] 三个接口登录后返回 50101
- [x] 未登录 40101
- [x] 无模型 SDK 依赖
- [x] 配置从 .env 读，默认空
- [x] pytest 真实通过

---

## 阶段 9 前端基础

### 9.1 API 封装与统一请求

发给 AI 的内容：
进入任务 9.1：前端 API 封装。

范围：
- frontend/src/api/request.js：
  - axios 实例，baseURL 从 import.meta.env.VITE_API_BASE_URL 读取
  - 请求拦截器附加 Authorization: Bearer <token>（token 从 Pinia auth store 读）
  - 响应拦截器：code=0 返回 data；40101 清 token 跳登录；其他 code 抛出带 message 的错误
- frontend/src/api/auth.js、wordbooks.js、practice.js、wrongWords.js、stats.js、admin.js
  - 按 api-contract.md 封装，函数名动词开头，路径与契约一致
- frontend/src/stores/auth.js：
  - state：token、user
  - actions：login、logout、fetchMe、setToken
  - token 持久化到 localStorage，初始化时读取
- .env.development：VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
- 不写任何页面，只做基础设施
- 用 tokens.css 变量，不硬编码颜色

约束：不引入清单外依赖；不写业务页面。

验收：
- [ ] 拦截器附加 token、处理 40101
- [ ] 各模块 api 函数与契约一致
- [ ] auth store 持久化与初始化正确
- [ ] pnpm lint 通过

---

### 9.2 登录注册页与路由守卫

发给 AI 的内容：
进入任务 9.2：登录注册页与路由守卫。

范围：
- views/auth/Login.vue、Register.vue：
  - 下划线式输入框（按 08-ui-style，不用圆角边框）
  - 登录支持 username 或 email
  - 错误就地提示，不弹窗
  - 注册成功跳登录
- router/index.js：
  - /login、/register 公开
  - / 及其他用户页需登录
  - /admin/* 需 role=admin，否则跳首页
  - 全局守卫读 auth store
- layouts/UserLayout.vue：
  - 左侧竖导航（桌面）/ 底部 Tab（移动）
  - 导航项：首页、词书、练习、错词本、我的
  - 纸感学院风：米白底、墨蓝文字、赭石黄当前项标记
- views/user/Home.vue 改为简单欢迎页占位（真实内容下个任务）
- 不接练习、词书接口

约束：
- 颜色只用 tokens.css 变量
- 判分反馈不用弹窗（本任务尚无判分）
- 不引入 UI 组件库默认皮肤

验收：
- [ ] 登录成功写入 token 并跳首页
- [ ] 未登录访问受保护页跳登录
- [ ] 普通用户访问 /admin/* 被拦截
- [ ] 登录/注册页为下划线式输入
- [ ] 导航当前项有赭石黄标记
- [ ] pnpm lint 通过

---

## 阶段 10 用户端词书

### 10.1 词书列表与详情页

发给 AI 的内容：
进入任务 10.1：用户端词书列表与详情页。

范围：
- views/user/WordbookList.vue：
  - 目录式列表（编号 + 词书名 + 词数 + 我的进度 + 开始默写）
  - 行间实线分隔，不用卡片堆砌
  - 分页
- views/user/WordbookDetail.vue：
  - 词书信息 + 单词表格（单词/音标/释义/掌握度色点）
  - 掌握度筛选
  - 分页
  - 「开始默写」按钮跳练习页并带 wordbook_id
- 接 9.1 的 api
- 空状态用鼓励文案
- 加载态用细线 skeleton，不用大块灰块

约束：不写练习页、不写管理端、不硬编码颜色。

验收：
- [ ] 列表只显示 published 词书
- [ ] 详情单词表格分页、掌握度色点正确
- [ ] 空状态为鼓励文案
- [ ] 颜色全走 tokens
- [ ] pnpm lint 通过

---

## 阶段 11 默写练习页（核心）

### 11.1 SpellInput 组件

发给 AI 的内容：
进入任务 11.1：SpellInput 组件。

范围：
- components/SpellInput.vue：
  - 下划线式输入，无圆角边框
  - props：modelValue、disabled、status（default/correct/wrong）、hint（{length}）
  - 状态样式：默认墨蓝下划线；correct 墨绿对勾在右侧；wrong 朱红波浪下划线
  - 回车触发 submit 事件
  - 使用提示后显示长度占位（如 _ _ _ _）
- components/GradeMark.vue：
  - props：type（correct/wrong），手绘感 SVG
- 不接接口

约束：只用 tokens 变量；不用弹窗；不用 emoji 当图标。

验收：
- [ ] 下划线输入，无圆角边框
- [ ] 三种状态样式正确
- [ ] 回车触发 submit
- [ ] 对勾/圈为 SVG 手绘感
- [ ] pnpm lint 通过

---

### 11.2 练习页状态机与作答

发给 AI 的内容：
进入任务 11.2：练习页状态机与作答。

范围：
- views/user/Practice.vue：
  - 进入时调 POST /practice/sessions 创建会话，展示第一题
  - 每题展示：音标衬线大字 + 中文释义 + 词性 + SpellInput + 发音按钮（调 /words/{id}/audio，无音频用 TTS 兜底）
  - 状态机：idle → answering → submitting → submitted(correct/wrong) → next → finished
  - 提交调 POST /practice/sessions/{id}/answer
  - 正确：墨绿对勾 + 例句就地展示；错误：朱红标记 + 正确拼写 + 例句 + 加入错词本提示
  - 提交中禁用按钮防重复
  - 回车进入下一题
  - notice 存在时顶部细条提示
- stores/practice.js 管理当前会话状态

约束：
- 判分只在服务端，前端不持有答案
- 反馈就地呈现不弹窗
- 不写完成页（下个任务）

验收：
- [ ] 出题、作答、就地反馈完整
- [ ] 提交中按钮禁用
- [ ] 前端不存储 spelling
- [ ] 回车可连续作答
- [ ] notice 正常展示
- [ ] pnpm lint 通过

---

### 11.3 完成页与错词本联动

发给 AI 的内容：
进入任务 11.3：练习完成页。

范围：
- 全部题目完成后调 POST /practice/sessions/{id}/finish
- 完成页就地展示（不跳新页也可，覆盖练习区）：
  - 印章式「完成」标记（墨蓝描边圆章，轻微旋转）
  - 本轮正确率、用时
  - 按钮：再来一组、查看错词
- 错词本入口跳转 /wrong-words
- 空状态与加载态

约束：不写错词本页面、不用弹窗、不用 emoji。

验收：
- [ ] finish 被调用且展示正确率
- [ ] 印章样式符合纸感学院风
- [ ] 再来一组重新创建会话
- [ ] 查看错词跳转正确
- [ ] pnpm lint 通过

---

## 阶段 12 错词本

### 12.1 错词本页面与重练入口

发给 AI 的内容：
进入任务 12.1：错词本页面。

范围：
- views/user/WrongWords.vue：
  - 列表式：单词 + 音标 + 释义 + 错误次数 + 移除 + 重练
  - 分页
  - resolved 筛选切换
  - 「重练错词」按钮跳练习页 mode=wrong_only
- 移除调 DELETE /wrong-words/{word_id}
- 空状态鼓励文案

约束：不写管理端、不硬编码颜色、不用弹窗。

验收：
- [ ] 列表字段齐全，分页正常
- [ ] 移除后列表刷新
- [ ] resolved 筛选有效
- [ ] 重练按钮带 mode=wrong_only
- [ ] 空状态为鼓励文案
- [ ] pnpm lint 通过

---

## 阶段 13 个人中心

### 13.1 数据看板与印章墙

发给 AI 的内容：
进入任务 13.1：个人中心。

范围：
- views/user/Profile.vue：
  - 顶部头像 + 昵称 + 加入天数
  - 账本式数据看板：累计默写、正确率、连续天数、已掌握词数、未解决错词，四到五行，右侧细线趋势
  - 近 7/30 天练习量细线折线图（无渐变填充）
  - 印章成就墙：已得实心墨蓝，未得虚线框
- 接 /stats/overview 与 /stats/daily

约束：图表不用渐变填充、不引入重型图表库（可用轻量 SVG 手写）。

验收：
- [ ] 五个指标正确展示
- [ ] 折线图无渐变填充
- [ ] 印章墙状态正确
- [ ] 无数据展示鼓励文案
- [ ] pnpm lint 通过

---

## 阶段 14 管理端

### 14.1 管理端布局与词书管理

发给 AI 的内容：
进入任务 14.1：管理端布局与词书管理。

范围：
- layouts/AdminLayout.vue：左侧导航（词书管理、用户管理、数据概览），纸感学院风但更表格化
- views/admin/WordbookManage.vue：
  - 表格：名称、状态、词数、创建时间、操作
  - 新建/编辑弹层用侧滑或就地展开，不用居中大弹窗
  - 上下架、删除（有单词时提示先清空）
- 接 admin api

约束：不写单词管理、不写导入、不用默认组件库皮肤。

验收：
- [ ] 管理端需 admin 才能进
- [ ] 词书 CRUD 可用
- [ ] 有单词删除被拒并提示
- [ ] 表格样式与纸感风格一致
- [ ] pnpm lint 通过

---

### 14.2 管理端单词管理

发给 AI 的内容：
进入任务 14.2：管理端单词管理。

范围：
- views/admin/WordManage.vue：
  - 按词书查看单词表格：spelling、音标、释义、词性、排序
  - 新增/编辑/删除
  - keyword 搜索
  - 分页
- 接 admin words api

约束：不写导入、不用默认组件库皮肤。

验收：
- [ ] 单词 CRUD 可用
- [ ] keyword 搜索、分页正常
- [ ] 同词书重复 spelling 提示 40901
- [ ] pnpm lint 通过

---

### 14.3 导入向导

发给 AI 的内容：
进入任务 14.3：导入向导。

范围：
- views/admin/ImportWizard.vue：
  - 步骤：上传文件 → 列映射 → 预览校验 → 确认导入 → 结果页
  - 预览展示列、总行数、前 20 行样本、错误摘要
  - 确认后带同一文件与列映射调正式导入
  - 结果页展示成功/失败行数与失败明细
- 接 admin import api

约束：不用居中大弹窗、不用默认组件库皮肤、不硬编码颜色。

验收：
- [ ] 五步流程完整
- [ ] 预览显示错误摘要
- [ ] 结果页显示失败行号与原因
- [ ] pnpm lint 通过

---

### 14.4 用户管理与概览

发给 AI 的内容：
进入任务 14.4：管理端用户管理与数据概览。

范围：
- views/admin/UserManage.vue：
  - 表格：用户名、邮箱、角色、状态、注册时间、累计练习、操作
  - 搜索、状态筛选、分页
  - 禁用/启用、重置密码、查看用户数据
- views/admin/Overview.vue：
  - 六个指标卡片（用分割线与数字，不用大圆角卡片）
- 接 admin users、admin overview api

约束：不用默认组件库皮肤、不硬编码颜色。

验收：
- [ ] 用户列表搜索筛选分页正常
- [ ] 禁用后用户无法登录
- [ ] 重置密码、查看数据可用
- [ ] 概览六指标正确
- [ ] pnpm lint 通过

---

## 阶段 15 AI 对话占位页

### 15.1 AI 对话空状态页

发给 AI 的内容：
进入任务 15.1：AI 对话占位页。

范围：
- views/user/AiChat.vue：空状态页，展示「即将上线」与一段说明，不接对话
- 首页与导航加入口，标注「即将上线」
- api/ai.js 封装三个占位接口
- 点击入口进入空状态页

约束：不接大模型、不写对话逻辑、不引入 SDK。

验收：
- [ ] 入口可见且标注即将上线
- [ ] 空状态页可访问
- [ ] 无模型相关依赖
- [ ] pnpm lint 通过

---

## 阶段 16 收尾

### 16.1 全站 UI 走查与状态补齐

发给 AI 的内容：
进入任务 16.1：全站 UI 走查。

范围：
- 对照 08-ui-style.md 与去AI化检查清单逐条走查所有页面：
  - 无紫色渐变、无玻璃拟态、无光晕、无机器人形象、无 emoji 图标、无大圆角卡片堆砌
  - 颜色全部走 tokens.css
  - 判分反馈均就地呈现
- 补齐所有页面的空状态、错误态、加载态
- 移动端适配检查：导航变底部 Tab，表格可横向滚动
- 输出一份走查报告：问题清单 + 修复情况

约束：不新增功能、不改后端。

验收：
- [ ] 去AI化清单逐条通过
- [ ] 空/错/加载态全覆盖
- [ ] 移动端可用
- [ ] 走查报告提交

---

### 16.2 对照验收清单全量自检

发给 AI 的内容：
进入任务 16.2：全量自检。

范围：
- 对照 docs/feature-spec.md 的 F1–F14 验收点逐条打勾，输出自检表
- 对照 .agents/rules/11-checklist.md 逐条打勾
- 对照 docs/roadmap.md 阶段 0–10 确认全部完成
- 列出未完成项与原因

约束：不新增功能。

验收：
- [ ] F1–F14 自检表完整，未通过项有原因说明
- [ ] 11-checklist 逐条打勾
- [ ] roadmap 阶段全部完成或有明确结论
