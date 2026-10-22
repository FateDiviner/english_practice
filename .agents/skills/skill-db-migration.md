# Skill：数据库表结构变更

## 触发场景
新增表、加字段、改约束、加索引。

## 步骤
1. 修改 models/ 下 SQLAlchemy 模型
2. 生成 Alembic 迁移：alembic revision --autogenerate
3. 人工检查迁移脚本：字段类型、默认值、外键、索引、唯一约束
4. 补充 down_revision 回滚逻辑
5. 本地执行 alembic upgrade head 验证
6. 同步更新 05-database.md 规则文档

## 红线
- 不手改数据库
- 不删字段不写迁移说明
- 唯一约束和索引不得遗漏
