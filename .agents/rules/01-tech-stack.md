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

- 环境：Conda 只负责 Python 解释器环境，创建 `english_practice`（Python 3.11）。
- 依赖：uv 只负责依赖安装与锁定；在已激活的 Conda 环境中执行 `uv sync`，新增依赖使用 `uv add`；`uv.lock` 是唯一依赖锁定来源并提交。
- 双环境约束：Conda 环境设置 `UV_PROJECT_ENVIRONMENT=<该环境前缀>`，使 `uv sync` 和 `uv run` 使用 Conda 环境，不创建或使用 `backend/.venv`。
- 启动：`conda activate english_practice && cd backend && uv run uvicorn app.main:app --reload --port 8000`
- 测试：`conda activate english_practice && cd backend && uv run pytest -q`
- Lint：`uv run ruff check .`
- 格式检查：`uv run ruff format --check .`
- Node：22 LTS + pnpm 10；前端依赖与脚本使用 `pnpm`。Vite 7 要求 Node 20.19+ 或 22.12+，当前 Node 22.19 满足。
- 数据库：MySQL 8 本地 Docker 运行，连接信息通过 `.env` 配置。
- 后端异步驱动：`asyncmy`。
- JWT：`python-jose[cryptography]`。
- 密码哈希：`bcrypt`（认证必需依赖）。
- 后端测试：`pytest`、`pytest-asyncio`、`httpx`。
- 前端 Lint 与格式化：`eslint`、`prettier`。
- 以上技术选型均已锁定，不得自行替换。
