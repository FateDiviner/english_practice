# 落地清单

> 2026-10-24 按当前代码与测试结果重新核对勾选状态；此前未勾选项多为文档滞后。
> 证据以 `backend/tests/`、`frontend/tests/` 与 `docs/acceptance-checklist.md` 为准。

## 阶段 0：项目初始化
- [x] 建 backend / frontend 目录，初始化 FastAPI 与 Vite
- [x] 建 docs/ 放入 feature-spec、data-dictionary、api-contract、task-template、roadmap
- [x] 建 .agents/rules/ 放入规则文件
- [x] 建 frontend/src/styles/tokens.css，落地颜色字号变量
- [x] 配置 .env（数据库、JWT 密钥），提供 .env.example
- [x] 建 Alembic，配置数据库连接
- [x] 验证：后端能起、/docs 可访问、前端能起（由测试与 `pnpm build` 覆盖）

## 阶段 1：用户与认证
- [x] users 表 + 迁移
- [x] 注册 / 登录 / me 接口
- [x] bcrypt 哈希 + JWT 签发校验
- [x] get_current_user、require_admin 依赖
- [x] 前端登录注册页、token 存储、axios 拦截器、路由守卫
- [x] Swagger 手动验证三个接口
- [x] 验收：F1 全部验收点

## 阶段 2：词书与单词
- [x] wordbooks、words 表 + 迁移（含唯一约束）
- [x] 管理员词书 CRUD 接口
- [x] 单词手动增删改接口
- [x] 用户端词书列表 / 详情接口（只返回 published）
- [x] 前端管理端词书列表页、用户端词书列表页
- [x] 验收：F2 全部验收点

## 阶段 3：导入
- [x] import_jobs 表 + 迁移
- [x] 文件上传、列映射解析、预览接口
- [x] 逐行校验 + 事务批量入库
- [x] 失败行写 error_detail，大文件后台任务 + 进度查询
- [x] 前端 ImportWizard（上传 → 映射 → 预览 → 导入 → 结果）
- [x] 验收：F3、F12 全部验收点

## 阶段 4：默写核心闭环
- [x] practice_sessions、practice_records、word_progress、wrong_words 表 + 迁移
- [x] services/grading.py 判分函数 + 单元测试（大小写/空格/英美/宽松/阈值）
- [x] 出题接口（不返回拼写）
- [x] 答题接口（调判分、更新进度、写错词本、防重复计分）
- [x] 结束接口返回汇总
- [x] 前端 SpellInput 组件（下划线、状态）
- [x] 前端练习页状态机 + 就地反馈 + 完成页
- [x] 验收：F4、F5、F6 全部验收点

## 阶段 5：错词与进度
- [x] 错词本列表 / 移除接口
- [x] 错词专项重练（只出 resolved=false）
- [x] 词书进度接口（按用户统计已掌握词数，支持 mastery 筛选）
- [x] 前端错词本页、重练入口、词书进度展示
- [x] 验收：F7、F8 全部验收点

> F7 此前把 `mastered` 写死为 0、`mastery_level` 返回 null；2026-10-24 已修复并补回归测试。

## 阶段 6：数据与个人中心
- [x] stats 概览 / 趋势接口（聚合查询）
- [x] 个人中心页：账本式看板 + 印章墙
- [x] 连续天数按自然日去重计算
- [x] 验收：F9 全部验收点

## 阶段 7：管理端用户管理
- [x] 用户列表分页搜索筛选接口
- [x] 禁用/启用、重置密码、查看用户数据接口
- [x] 前端用户管理表格页
- [x] 验收：F10 全部验收点

## 阶段 8：发音与概览
- [x] 音频地址字段使用 + TTS 兜底
- [x] 管理员数据概览接口与页面
- [x] 验收：F11、F13 全部验收点

## 阶段 9：AI 对话占位
- [x] ai_conversations、ai_messages 表 + 迁移
- [x] /api/v1/ai/* 路由占位（已由阶段 11 替换为正式接口）
- [x] config 增加 ai_provider_url、ai_api_key（默认空）
- [x] 前端 AiChat.vue 空状态页、api 封装、入口标注“即将上线”
- [x] 验收：F14 原预留验收点

## 阶段 10：收尾
- [x] 全站按 08-ui-style 走查（见 docs/frontend-ui-review.md）
- [x] 空/错/加载态补齐
- [x] 移动端适配检查
- [x] 对照 11-checklist 全量自检（见 docs/acceptance-checklist.md）

## 阶段 11：AI 对话正式接入
- [x] 后端会话列表 / 创建 / 详情 / 删除接口
- [x] `/agent/chat` 支持 conversation_id，并持久化用户与助手消息
- [x] 客户端中断时保存已生成的部分回复
- [x] 前端 SSE 解析工具与单元测试
- [x] AiChat 页接入流式对话、会话切换 / 删除、停止生成与场景选择
- [x] 管理端用户数据抽屉接入学情画像报告
- [x] 验收：F14 新验收点（见 docs/acceptance-checklist.md）
