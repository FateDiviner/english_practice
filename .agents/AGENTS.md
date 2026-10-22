# 项目协作规则

本文件适用于本仓库内的所有改动，并优先于代理的默认工作习惯。

## 1. 改动必 Commit

- **每个逻辑改动必须对应一个 Git commit。** 实现代码、相关测试和必要文档应放在同一个提交中，保证该提交可独立追踪、回滚和测试。
- **交付前必须完成提交。** 不得把已完成的改动以未提交状态留给用户；一次任务包含多个相互独立的逻辑改动时，应拆分为多个原子 commit。
- **禁止混合无关改动。** 不把格式化、依赖升级、功能修复等互不相关的变更塞进同一个 commit。
- **提交前必须通过全部验证。** 测试未通过时不得提交，也不得宣称任务完成。
- **提交信息采用 Conventional Commits 格式**，例如：`feat: 添加练习记录页面`、`fix: 修复答案校验错误`、`test: 补充发音测试`、`docs: 更新协作规则`、`chore: 配置构建工具`。
- 使用 `git status --short` 检查工作区，只暂存本次改动涉及的文件；禁止使用会混入无关文件的一揽子暂存方式。
- 提交前检查 `git diff --check` 和完整 diff；不得提交密钥、令牌、个人配置、依赖目录或构建产物。

## 2. 测试必覆盖

- **任何功能、缺陷修复、重构或运行行为变更，都必须新增或更新相关自动化测试。**
- 缺陷修复至少包含一个能在修复前失败、修复后通过的回归测试。
- 测试应覆盖正常路径、关键边界和错误路径；仅增加不验证行为的“占位测试”不算覆盖。
- 严禁通过删除测试、跳过测试、降低断言强度或吞掉错误来制造“测试通过”。
- 提交前先运行针对性测试，再运行仓库要求的完整测试、Lint、类型检查和构建验证；所有命令必须成功。
- 纯文档、注释或非运行配置改动无需虚构自动化测试，但仍必须执行与其风险匹配的验证，例如 Markdown 内容断言、配置解析、链接检查、`git diff --check` 等。
- 当仓库建立技术栈后，应在此文件补充项目实际的安装、测试、Lint、类型检查和构建命令，后续代理必须遵循。

## 3. 标准工作流

1. 运行 `git status --short`，确认现有改动及其归属；不得擅自提交用户未要求处理的改动。
2. 实施一个内聚的逻辑改动，并同步新增或更新测试。
3. 运行针对性测试，再运行完整测试与验证。
4. 检查 diff、文件范围和敏感信息，执行 `git diff --check`。
5. 所有验证通过后创建对应 commit。
6. 再次运行 `git status --short` 和必要的最终验证，确认工作区中不残留本次未提交改动。
7. 向用户报告 commit 哈希、执行的测试/验证命令及其结果。

## 4. 完成定义

只有同时满足以下条件，才可宣称任务完成：

- 需求已全部实现；
- 相关测试已新增或更新；
- 所有测试、Lint、类型检查和构建验证均通过；
- 每个逻辑改动都有对应 commit；
- 本次改动的所有文件均已提交，工作区干净；
- 最终交付说明包含 commit 哈希和验证结果。

## 5. 当前后端命令

环境分工：

- Conda 只负责 Python 解释器环境：环境名 `english_practice`，Python 3.11。
- uv 只负责依赖安装与锁定：在已激活的 Conda 环境中执行 `uv sync`，新增依赖使用 `uv add`。
- `uv.lock` 是唯一依赖锁定来源，必须提交。
- Conda 环境必须设置 `UV_PROJECT_ENVIRONMENT=<该环境前缀>`，确保 `uv sync` 和 `uv run` 使用 Conda 环境，不创建或使用 `backend/.venv`。
- 证书：Conda 环境的 `SSL_CERT_FILE` 应指向 `<env>\Library\ssl\cacert.pem`，`SSL_CERT_DIR` 应指向 `<env>\Library\ssl\certs`；`certs` 目录必须包含证书文件，若只有 `.keep`，将 `Library\ssl\cacert.pem` 复制到 `Library\ssl\certs\cacert.pem`。PowerShell 示例：`$env:SSL_CERT_FILE = "$env:CONDA_PREFIX\Library\ssl\cacert.pem"`，`$env:SSL_CERT_DIR = "$env:CONDA_PREFIX\Library\ssl\certs"`。

命令：

- 创建环境：`conda create -n english_practice -c conda-forge --override-channels python=3.11`
- 绑定 uv 环境：`conda env config vars set "UV_PROJECT_ENVIRONMENT=<该环境前缀>" -n english_practice`，随后重新激活环境。
- 安装/同步依赖：`conda activate english_practice && cd backend && uv sync`
- 新增依赖：`conda activate english_practice && cd backend && uv add <package>`
- 启动：`conda activate english_practice && cd backend && uv run uvicorn app.main:app --reload --port 8000`
- 测试：`conda activate english_practice && cd backend && uv run pytest -q`
- Lint：`uv run ruff check .`
- 管理员 seed：`cd backend && conda run -n english_practice uv run python -m scripts.create_admin`


Alembic 命令：

- 新建迁移：`cd backend && conda run -n english_practice uv run alembic revision -m "describe_change"`
- 升级到最新：`cd backend && conda run -n english_practice uv run alembic upgrade head`
- 降级到初始：`cd backend && conda run -n english_practice uv run alembic downgrade base`

环境变量配置：

- 复制示例文件：`cd backend` 后执行 `Copy-Item .env.example .env`。
- 按本机实际环境填写 `DATABASE_URL`、`JWT_SECRET` 等配置；不要提交 `.env`。
- `ADMIN_USERNAME`、`ADMIN_EMAIL`、`ADMIN_PASSWORD` 是后续 seed 脚本的占位配置；本轮不实现 seed 脚本。
- `backend/.gitignore` 已忽略 `.env`。

## 6. 当前前端命令

- 环境：Node 22 LTS + pnpm 10；Vite 7 要求 Node 20.19+ 或 22.12+，当前 Node 22.19 满足。
- 安装依赖：`cd frontend && pnpm install`
- 开发启动：`cd frontend && pnpm dev`
- 构建：`cd frontend && pnpm build`
- Lint：`cd frontend && pnpm lint`
- 格式检查：`cd frontend && pnpm format:check`
- 依赖锁定文件：`frontend/pnpm-lock.yaml`，必须提交。
