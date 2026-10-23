# 落地清单

## 阶段 0：项目初始化
- [ ] 建 backend / frontend 目录，初始化 FastAPI 与 Vite
- [ ] 建 docs/ 放入 feature-spec、data-dictionary、api-contract、task-template、roadmap
- [ ] 建 .agents/rules/ 放入 14 个规则文件
- [ ] 建 frontend/src/styles/tokens.css，落地颜色字号变量
- [ ] 配置 .env（数据库、JWT 密钥），提供 .env.example
- [ ] 建 Alembic，配置数据库连接
- [ ] 验证：后端能起、/docs 可访问、前端能起

## 阶段 1：用户与认证
- [ ] users 表 + 迁移
- [ ] 注册 / 登录 / me 接口
- [ ] bcrypt 哈希 + JWT 签发校验
- [ ] get_current_user、require_admin 依赖
- [ ] 前端登录注册页、token 存储、axios 拦截器、路由守卫
- [ ] Swagger 手动验证三个接口
- [ ] 验收：F1 全部验收点

## 阶段 2：词书与单词
- [ ] wordbooks、words 表 + 迁移（含唯一约束）
- [ ] 管理员词书 CRUD 接口
- [ ] 单词手动增删改接口
- [ ] 用户端词书列表 / 详情接口（只返回 published）
- [ ] 前端管理端词书列表页、用户端词书列表页
- [ ] 验收：F2 全部验收点

## 阶段 3：导入
- [x] import_jobs 表 + 迁移
- [x] 文件上传、列映射解析、预览接口
- [x] 逐行校验 + 事务批量入库
- [x] 失败行写 error_detail，大文件后台任务 + 进度查询
- [x] 前端 ImportWizard（上传 → 映射 → 预览 → 导入 → 结果）
- [x] 验收：F3、F12 全部验收点

## 阶段 4：默写核心闭环
- [ ] practice_sessions、practice_records、word_progress、wrong_words 表 + 迁移
- [ ] services/grading.py 判分函数 + 单元测试（大小写/空格/英美/宽松/阈值）
- [ ] 出题接口（不返回拼写）
- [ ] 答题接口（调判分、更新进度、写错词本、防重复计分）
- [ ] 结束接口返回汇总
- [ ] 前端 SpellInput 组件（下划线、状态）
- [ ] 前端练习页状态机 + 就地反馈 + 完成页
- [ ] 验收：F4、F5、F6 全部验收点

## 阶段 5：错词与进度
- [ ] 错词本列表 / 移除接口
- [ ] 错词专项重练（只出 resolved=false）
- [ ] 词书进度接口
- [ ] 前端错词本页、重练入口、词书进度展示
- [ ] 验收：F7、F8 全部验收点

## 阶段 6：数据与个人中心
- [ ] stats 概览 / 趋势接口（聚合查询）
- [ ] 个人中心页：账本式看板 + 印章墙
- [ ] 连续天数按自然日去重计算
- [ ] 验收：F9 全部验收点

## 阶段 7：管理端用户管理
- [x] 用户列表分页搜索筛选接口
- [x] 禁用/启用、重置密码、查看用户数据接口
- [x] 前端用户管理表格页
- [x] 验收：F10 全部验收点

## 阶段 8：发音与概览
- [ ] 音频地址字段使用 + TTS 兜底
- [ ] 管理员数据概览接口与页面
- [ ] 验收：F11、F13 全部验收点

## 阶段 9：AI 对话占位
- [ ] ai_conversations、ai_messages 表 + 迁移
- [ ] /api/v1/ai/* 路由返回 501
- [ ] config 增加 ai_provider_url、ai_api_key（默认空）
- [ ] 前端 AiChat.vue 空状态页、api 封装、入口标注"即将上线"
- [ ] 验收：F14 全部验收点

## 阶段 10：收尾
- [ ] 全站按 08-ui-style 走查
- [ ] 空/错/加载态补齐
- [ ] 移动端适配检查
- [ ] 对照 11-checklist 全量自检
