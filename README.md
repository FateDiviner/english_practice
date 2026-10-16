# 英语练习平台 (English Practice)

聚焦「默写记忆 + AI 场景实战」的极简英语练习 Web 应用。通过「中文释义 + 音标」引导主动拼写，搭配具备实时纠错能力的 AI 英语伴学助手，形成「背 - 练 - 用」闭环。

## 技术栈

| 层 | 选型 |
| :--- | :--- |
| 前端 | React 18 + TypeScript + Vite + Arco Design React + Zustand |
| 后端 | Python 3.11+ / FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| 数据库 | MySQL 8.0（PRD 5.2 指定；SQLAlchemy 抽象，可改 `.env` 一行切换） |
| 发音 | 浏览器原生 `window.speechSynthesis`，零第三方 TTS 成本 |
| AI | OpenAI 兼容协议 SSE 流式（xiaomi-mimo），密钥仅存于后端 `.env` |

## 目录结构

```text
english_practice/
├── AGENTS.md              开发规范与协作守则
├── PRD.md                 产品需求文档
├── backend/
│   ├── app/
│   │   ├── api/           路由控制器（入参校验 + 响应格式化）
│   │   ├── services/      业务逻辑（遗忘曲线调度、练习结算、认证迁移）
│   │   ├── ai/            Prompt 编排、纠错区块解析、SSE 流式客户端
│   │   ├── models/        ORM 模型与参数化查询
│   │   └── schemas/       Pydantic 请求 / 响应契约
│   ├── data/              内置词书数据（CET-4 / CET-6 / 考研 / 高中，共 313 词）
│   ├── scripts/init_db.py 建表 + 词书导入（幂等）
│   └── tests/             2702 项自动化测试
└── frontend/
    └── src/
        ├── api/           HTTP 客户端与 SSE 流解析
        ├── stores/        Zustand：认证 / 全局设置 / 练习状态机
        ├── hooks/         发音、键盘流契约
        ├── pages/         登录、词书中心、默写、错题本、AI 伴学
        └── styles/        设计 Token（深浅色双套）
```

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS / Linux

cp .env.example .env      # 填入 MySQL 连接串与 AI 三项配置
.venv/Scripts/python -m scripts.init_db           # 建表 + 导入 313 词
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173，/api 已代理至 :8000
```

## 环境变量 (`backend/.env`)

| 变量 | 说明 |
| :--- | :--- |
| `DATABASE_URL` | MySQL 连接串，如 `mysql+pymysql://user:pass@127.0.0.1:3306/english_practice?charset=utf8mb4` |
| `SECRET_KEY` | JWT 签名密钥，生产环境务必改为随机长串 |
| `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` | xiaomi-mimo 三项配置；**三项齐全才走真实模型**，否则自动降级为本地 Mock 流式回复 |

`.env` 已被 gitignore，任何凭证都不会进入代码或提交记录。

## 键盘流契约（默写核心场景）

| 按键 | 行为 |
| :--- | :--- |
| `Enter` | 提交当前拼写（答错时若已原地订正则重新校验，否则进入下一词） |
| `Space` / `Ctrl+P` | 重播单词发音 |
| `Tab` | 显示首字母提示 |
| `Esc` / `Ctrl+Enter` | 跳过并查看答案，计入错题本 |

输入框在页面加载与每次切词后**自动聚焦**，整条流程无需鼠标。

## 测试与门禁

```bash
# 后端：2702 项测试（默认跑临时 SQLite，零配置）
cd backend && .venv/Scripts/python -m pytest

# 后端：整套测试改跑真实 MySQL（需先建好 <库名>_test）
RUN_MYSQL_TESTS=1 .venv/Scripts/python -m pytest

# 真实大模型连通性冒烟（唯一会调用付费接口的脚本）
.venv/Scripts/python -X utf8 -m scripts.ai_smoke

# 前端：组件测试（jsdom）+ lint 0 error + 类型检查 + 构建
cd frontend && npm test && npm run lint && npm run build
```

`RUN_MYSQL_TESTS=1` 时，连接串由 `.env` 的 `DATABASE_URL` 自动把库名改写为
`<库名>_test`，凭证只存在于进程环境变量，不会进入命令行或日志；且强制要求
库名含 `test`，并在开跑前 `drop_all` 重建，防止误清生产数据。

pytest 一律强制走 Mock 流式（不读 `.env` 的真实密钥），以保证断言确定、
不消耗 API 额度；真实模型只通过 `scripts/ai_smoke.py` 验证。

测试覆盖：遗忘曲线调度、拼写校验与逐字符比对、例句挖空防泄漏、纠错区块解析、
端到端 API 流程（含游客数据迁移、越权会话拒绝、SSE 流式一致性）、词书数据质量
红线（音标格式、词性前缀、中英混杂、重复词、例句必须体现目标词），以及全项目
无 Emoji 自检。

前端为 Vitest + Testing Library（jsdom），覆盖 AI 伴学的布局回归契约
（消息区必须挂在可滚动的 flex 链路上、卡片自身裁剪溢出、气泡允许长文本断行）、
键盘流（进入页面自动聚焦、Enter 发送、Shift+Enter 换行）、纠错区块渲染，
以及滚动贴底判定的边界值。

## 设计取舍说明

**发音字段 `speak`**：浏览器 `speechSynthesis` 只能朗读真实文本，因此默写线索中
必须携带目标词原文才能实现「Space 重播发音」这一键盘契约。作为补偿，例句会对目标词
**及其全部屈折形式**挖空（`abandon` 连同 `abandoned` 一并遮蔽），防止从例句反查拼写。
本项目定位为个人练习工具而非监考场景，该取舍已在权衡后接受。

**错题本移出规则**：单词答错后进入错题本，须累计答对 2 次才会移出，避免「订正一次
就消失」导致错题本失去复盘价值。

**PRD 内部冲突的处理**：数据库按 PRD 5.2 选 MySQL（AGENTS.md 与架构图写的 SQLite，
以你确认的为准）；纠错区块标签按 AGENTS.md 第 7.2 节采用 `[语法指正]` / `[地道表达]`。

## 版本记录

| 版本 | 日期 | 主要变更 |
| :--- | :--- | :--- |
| v1.0.0 | 2026-10-15 | MVP：认证与游客迁移、词书中心、默写全键盘流、错题本、AI 伴学 SSE 流式与纠错区块 |
| v1.1.0 | 2026-10-16 | 修复 AI 伴学对话框内容溢出（flex 约束下沉至 Card body 并裁剪）、长文本断行兜底、贴底跟随滚动、输入框自动聚焦、引入前端测试（12 项） |

## 里程碑状态

| 阶段 | 内容 | 状态 |
| :--- | :--- | :--- |
| Phase 1 | 数据库建表、313 词导入、注册登录与游客迁移 | 已完成 |
| Phase 2 | 默写核心界面、全键盘交互、即时判定、错题沉淀 | 已完成 |
| Phase 3 | AI 对话、SSE 流式、实时纠错卡片 | 已完成，真实模型连通性已验证 |
| Phase 4 | 联调、界面美化、端到端验证 | 后端联调完成（MySQL 全量测试通过），界面美化与浏览器端实操待验收 |

### 已验证事实

- MySQL 8.0 连接、建表、313 词导入与幂等重跑均正常（`dialect: mysql`）。
- 整套 2702 项测试在 **MySQL** 与 **SQLite** 两种后端上结果一致，全部通过。
- 真实模型端点为 OpenAI 兼容 SSE，逐字流式可用（实测分片间隔最大 0.26s），
  `[语法指正]` / `[地道表达]` 两个区块均能被正确解析。
- 首字延迟受网络路径影响波动较大：受控 A/B 实测 **0.74 ~ 2.2s**（典型值约 1s），
  但在部分时段曾观测到 8 ~ 19s。同一时刻对比长短请求无差异，可确认瓶颈在
  网络与端点侧而非请求体或客户端实现，故未做无效改动。
