# 数据库规则

表：users、wordbooks、words、user_wordbooks、word_progress、practice_sessions、practice_records、wrong_words、import_jobs
预留表：ai_conversations、ai_messages（本期不写业务逻辑）

- 每表必须有 id BIGINT PK AUTO_INCREMENT、created_at、updated_at
- 外键显式声明并建索引
- 唯一约束：words(wordbook_id, spelling)、word_progress(user_id, word_id)、wrong_words(user_id, word_id)
- 表结构变更必须走 Alembic 迁移，禁止手改库
- 字符集 utf8mb4，排序规则 utf8mb4_unicode_ci
