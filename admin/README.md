# 管理端（admin）

独立部署的管理界面，与用户端 `frontend/` 共用后端与设计 Token，但工程、构建与
部署完全分离。

## 与用户端的边界

| 项 | 处理 |
| :--- | :--- |
| 后端接口 | 共用 `/api/*`，管理接口一律在 `/api/admin/*` 且强制 `require_admin` |
| 设计 Token | 引用 `shared/design/tokens.css`，两端同一份，改动只需一处 |
| 类型定义 | 各写各的，管理端 DTO 与用户端本就不同，不引入跨工程构建耦合 |
| 端口 | 开发期 `5174`（用户端 `5173`），互不占用 |

## 启动

```bash
cd admin
npm install
npm run dev          # http://localhost:5174，/api 代理至 :8000
```

生产部署时用 `VITE_API_BASE` 指定后端地址：

```bash
VITE_API_BASE=https://api.example.com npm run build
```

## 成为管理员

首个管理员必须走 CLI，不提供网页注册入口：

```bash
cd backend
python -m scripts.create_admin <用户名>
```

## 门禁

```bash
npm run lint && npm run typecheck && npm test && npm run build
```
