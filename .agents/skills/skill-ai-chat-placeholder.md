# Skill：AI 对话功能占位

## 触发场景
涉及 AI 英语对话入口、接口、数据表、配置的占位实现。

## 步骤
1. 后端：新建 api/v1/ai.py，路由返回 501，响应走统一包装
2. 模型：按 05-database 建 ai_conversations、ai_messages 表并写迁移
3. 配置：core/config.py 增加 ai_provider_url、ai_api_key（从 .env 读取，默认空）
4. 前端：新增 views/user/AiChat.vue 空状态页 + api/ai.js 封装
5. 入口：首页与导航加入口，标注"即将上线"，点击进入空状态页
6. 在 feature-spec.md F14 标注状态

## 红线
- 不引入模型 SDK
- 不写对话业务逻辑
- 密钥不得硬编码
- 接口必须返回 501 而非假数据
