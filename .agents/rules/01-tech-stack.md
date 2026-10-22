# 技术栈（不得擅自替换）

前端：Vue 3（Composition API + <script setup>）、Vite、Vue Router 4、Pinia、Axios
后端：Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2.x、Alembic
数据库：MySQL 8.x（utf8mb4 / utf8mb4_unicode_ci）
认证：JWT + bcrypt
导入：pandas + openpyxl

禁止引入：TypeScript（除非明确要求）、Nuxt、Next、Django、MongoDB、Redis（除非要求）、付费授权库。

预留（本期不引入依赖）：AI 对话能力，接入时再评估模型服务与 SDK。

## 上下文文件（动手前必读）
- docs/feature-spec.md：功能范围唯一依据
- docs/data-dictionary.md：字段定义与类型
- docs/api-contract.md：接口字段级契约
- frontend/src/styles/tokens.css：UI 颜色字号变量

字段名、接口路径以文档为准，不得擅自更改；要改先改文档再改代码。


## 开发环境与工具链锁定

- Python 3.11，Node 20 LTS。
- 后端使用 `pyproject.toml` 声明依赖；使用 Conda 环境 `english_practice`（Python 3.11）运行和测试；前端使用 `pnpm`。
- MySQL 8 本地 Docker 运行，数据库连接信息统一通过 `.env` 配置。
- 后端异步驱动使用 `asyncmy`。
- JWT 使用 `python-jose[cryptography]`。
- 后端测试使用 `pytest`、`pytest-asyncio`、`httpx`；后端 Lint 使用 `ruff`。
- 前端 Lint 与格式化使用 `eslint`、`prettier`。
- 以上技术选型均已锁定，不得自行替换。
- `uv.lock` 仅用于锁定依赖版本；Python 3.11 环境、启动、测试和 lint 统一由 Conda 管理。
