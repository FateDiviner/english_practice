# 管理端 (admin)

管理端的前后端都在这个目录下，与用户端 `user/` 完全平行、完全独立。

| 目录 | 说明 | 端口 |
| :--- | :--- | :--- |
| `admin/frontend/` | 管理界面（Vite + React + TS） | `5174` |
| `admin/backend/` | 管理端 API（FastAPI，包名 `app`） | `8100` |

两端共用仓库根的 `core/`（表结构、鉴权、数据质量规则）与 `shared/design/`（设计
Token），但进程、构建产物与部署单元都各自独立，因此可以只把整个 `admin/` 放在
内网，公网只暴露 `user/`。

管理端后端不自带 venv，直接沿用用户端后端的：

```bash
cd admin/backend
../../user/backend/.venv/Scripts/python -m uvicorn app.main:app --port 8100
../../user/backend/.venv/Scripts/python -m pytest
```

细节见 [frontend/README.md](frontend/README.md)；全局约定见仓库根 [README.md](../README.md)。
