# Docker 部署指南

本文档描述如何用 Docker Compose 把「英语默写练习」平台（Vue 3 前端 + FastAPI 后端 + MySQL 8）部署到一台 Linux/Windows 服务器上。

文档中的命令与配置均已在 Docker 28.3.2 / Compose v2.39.1 上实测通过，实际验证结果见文末「附录 A：部署验证记录」。

---

## 1. 架构概览

三个容器组成一个私有网络 `english-practice-net`，只有前端对公网开放：

```
                        ┌──────────────────────────────────────────────┐
   浏览器 ──── :8080 ──►│ frontend (nginx:1.27-alpine)                 │
                        │  · 托管 Vue 构建产物（history 模式 SPA）     │
                        │  · /api/  ──反代──► backend:8000             │
                        │  · /mcp   ──反代──► backend:8000（SSE）      │
                        └───────────────────┬──────────────────────────┘
                                            │ 内部网络
                        ┌───────────────────▼──────────────────────────┐
                        │ backend (python:3.11-slim + uvicorn)         │
                        │  · FastAPI，/api/v1/*                        │
                        │  · 启动时等待 DB → alembic upgrade head      │
                        │    → 管理员 seed → 启动 2 个 worker          │
                        └───────────────────┬──────────────────────────┘
                                            │
                        ┌───────────────────▼──────────────────────────┐
                        │ db (mysql:8.0)                               │
                        │  · utf8mb4 / +08:00                          │
                        │  · 数据落在命名卷 english-practice-db-data   │
                        └──────────────────────────────────────────────┘
```

| 服务 | 镜像 | 容器内端口 | 宿主机暴露 | 说明 |
| --- | --- | --- | --- | --- |
| `frontend` | nginx:1.27-alpine | 80 | `0.0.0.0:${HTTP_PORT}`（默认 8080） | 唯一对外入口 |
| `backend` | python:3.11-slim | 8000 | `127.0.0.1:${BACKEND_PORT}`（默认 8000） | 仅本机可直连，用于调试 `/docs` |
| `db` | mysql:8.0 | 3306 | `127.0.0.1:${MYSQL_PORT}`（默认 3306） | 仅本机可直连，用于运维 |

> **为什么后端和数据库只绑定 127.0.0.1**：业务流量统一走前端 Nginx 同源代理，后端与数据库不需要对公网暴露。这样即使忘配防火墙，数据库也不会被外部直接访问。

关键设计点：

- **前端使用同源相对路径 `/api/v1`**，由 Nginx 反代到后端容器，因此不存在跨域问题，也不需要在构建时写死服务器 IP。
- **数据库迁移在容器启动时自动执行**，首次启动即建好全部表，可通过环境变量关闭。
- **管理员账号幂等 seed**：存在则改密码，不存在则创建，普通用户会被升级为管理员。
- **前端资源文件名带内容哈希**，`/assets/` 走一年不可变缓存；`index.html` 走 `no-cache`，保证发版后立即生效。
- **SSE 流式接口**（AI 对话 `/api/v1/agent/chat`）与 **MCP 端点**（`/mcp`）在 Nginx 层都关闭了缓冲，避免流式响应被攒包。

---

## 2. 前置条件

| 项目 | 要求 | 检查命令 |
| --- | --- | --- |
| Docker Engine | ≥ 20.10（推荐 24+） | `docker --version` |
| Docker Compose | v2（`docker compose` 子命令形式） | `docker compose version` |
| 内存 | ≥ 2 GB 可用（MySQL 约占 400 MB，后端约 300 MB） | `free -h` |
| 磁盘 | ≥ 5 GB 可用（镜像约 500 MB，其余为数据库增长） | `df -h` |
| 端口 | `${HTTP_PORT}` 空闲 | `ss -lntp \| grep 8080` |

国内网络环境下 Docker Hub 可能拉取失败（`failed to fetch anonymous token` / 连接超时），建议先配置镜像加速器，或提前手动 `docker pull` 本文涉及的基础镜像：

```bash
docker pull python:3.11-slim
docker pull node:22-alpine
docker pull nginx:1.27-alpine
docker pull mysql:8.0
docker pull ghcr.io/astral-sh/uv:latest
docker pull docker/dockerfile:1
```

---

## 3. 快速开始

### 3.1 上传代码

把仓库部署到服务器，例如：

```bash
git clone <仓库地址> /opt/english-practice
cd /opt/english-practice
```

只需要仓库根目录的 `docker-compose.yml`、`docker.env.example`，以及 `backend/`、`frontend/` 两个目录。`docs/`、`.agents/` 等目录不参与构建。

### 3.2 生成配置文件

```bash
cp docker.env.example .env
```

编辑 `.env`，**至少修改以下 4 项**：

```env
MYSQL_ROOT_PASSWORD=<强随机密码>
MYSQL_PASSWORD=<强随机密码>
JWT_SECRET=<openssl rand -hex 32 的输出>
ADMIN_PASSWORD=<管理员强密码>
```

生成随机密钥的命令：

```bash
openssl rand -hex 32
```

或使用 Docker 直接生成：

```bash
docker run --rm python:3.11-slim python -c "import secrets; print(secrets.token_hex(32))"
```

> `.env` 已被根目录 `.gitignore` 忽略，不会被提交。切勿把它复制进镜像或上传到仓库。

### 3.3 构建并启动

```bash
docker compose up -d --build
```

首次构建约需 2~5 分钟（取决于网络）。启动过程中 Compose 会按依赖顺序等待健康检查：

1. `db` 通过 `mysqladmin ping` 健康检查；
2. `backend` 等待数据库可连接 → 执行 `alembic upgrade head` → 执行管理员 seed → 启动 uvicorn → 通过 `/api/v1/health` 健康检查；
3. `frontend` 启动 Nginx。

### 3.4 确认状态

```bash
docker compose ps
```

期望输出（三行都是 `healthy`）：

```
NAME                        IMAGE                            STATUS                    PORTS
english-practice-backend    english-practice-backend:latest  Up 40 seconds (healthy)   127.0.0.1:8000->8000/tcp
english-practice-db         mysql:8.0                        Up 3 minutes (healthy)    127.0.0.1:3307->3306/tcp
english-practice-frontend   english-practice-frontend:latest Up 2 minutes (healthy)    0.0.0.0:8080->80/tcp
```

### 3.5 访问

- 应用首页：`http://<服务器IP>:8080`
- 管理员账号：`ADMIN_USERNAME` / `ADMIN_PASSWORD`（默认 `admin`）
- 后端接口文档（仅本机）：`http://127.0.0.1:8000/docs`

### 3.6 冒烟验证

```bash
# 1) 前端静态页
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/          # 200

# 2) 经 Nginx 反代到后端的健康接口
curl -s http://127.0.0.1:8080/api/v1/health
# {"code":0,"message":"ok","data":{"status":"up"}}

# 3) SPA 深链接回退（history 模式）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/admin/mcp/approvals   # 200

# 4) 登录拿 token
curl -s -X POST http://127.0.0.1:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account":"admin","password":"<ADMIN_PASSWORD>"}'
```

`/api/v1/auth/login` 的请求字段是 `account`（用户名或邮箱），不是 `username`。

---

## 4. 配置项说明

所有配置集中在根目录 `.env`，由 `docker-compose.yml` 通过 `env_file` 注入后端容器。`docker.env.example` 中有逐项注释，这里说明容易踩坑的部分。

### 4.1 数据库相关

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | 无（必填） | MySQL root 密码，仅供容器健康检查与运维 |
| `MYSQL_DATABASE` | `english_practice` | 业务库名 |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `app` / 无（必填） | 后端连接所用的业务账号，不要用 root |
| `MYSQL_PORT` | `3306` | 宿主机映射端口；本机 3306 被占用时改成 3307 等 |

**`DATABASE_URL` 不要写在 `.env` 里。** 它由 `docker-compose.yml` 依据上面四个变量自动拼装：

```yaml
DATABASE_URL: mysql+asyncmy://${MYSQL_USER}:${MYSQL_PASSWORD}@db:3306/${MYSQL_DATABASE}?charset=utf8mb4
```

原因是 `backend/.env` 里的开发配置指向 `127.0.0.1:3306`，在容器内 `127.0.0.1` 指的是后端容器自己，连不上数据库；必须用服务名 `db`。如果在 `.env` 里手写 `DATABASE_URL`，会覆盖这条拼装规则。

> **密码字符限制**：`MYSQL_PASSWORD` 会被直接拼进连接串，请避免使用 `@ : / ? # %` 等字符，否则 URL 解析会出错。建议只用大小写字母、数字和 `-` `_`。

### 4.2 端口

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HTTP_PORT` | `8080` | 前端对外端口。想直接用 80 端口就改成 `80` |
| `BACKEND_PORT` | `8000` | 后端直连端口，只绑定 `127.0.0.1` |
| `VITE_API_BASE_URL` | `/api/v1` | 前端构建期 API 基址。**保持相对路径**，改成交叉域地址会引入 CORS 问题 |
| `IMAGE_TAG` | `latest` | 镜像标签，发版时建议用版本号，便于回滚 |

### 4.3 后端核心

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `JWT_SECRET` | 无（必填） | JWT 签名密钥。修改后所有已登录会话失效 |
| `JWT_EXPIRE_MINUTES` | `120` | 登录令牌有效期（分钟） |
| `APP_TIMEZONE` | `Asia/Shanghai` | 统计口径的自然日时区，影响每日答题量、连续天数 |
| `FRONTEND_ORIGINS` | — | CORS 白名单。走同源 Nginx 代理时实际用不到；前后端分域名部署时必须写上前端对外地址，逗号分隔 |

### 4.4 管理员 seed

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` | `admin` / `admin@example.com` | 管理员账号与邮箱 |
| `ADMIN_PASSWORD` | 无 | 为空则跳过 seed；设置后**每次启动都会把该管理员密码重置为此值** |
| `SEED_ADMIN` | `true` | 关闭后容器不再执行 seed |

seed 逻辑（`backend/scripts/create_admin.py`）是幂等的：

- 账号不存在 → 创建，`action=created`
- 存在且是普通用户 → 升级为管理员，`action=upgraded_to_admin`
- 已是管理员 → 重置密码，`action=password_updated`

> 因为幂等 seed 会重置密码，**生产环境首次启动成功后建议把 `ADMIN_PASSWORD` 清空**（或设 `SEED_ADMIN=false`），否则每次重启都会把你后来在页面上改的密码顶回去。

### 4.5 AI 模型

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | `mock` 使用内置 Mock 客户端，不产生外部调用 |
| `AI_PROVIDER_URL` | 空 | OpenAI 兼容接口的 base URL，代码会拼上 `/chat/completions` |
| `AI_PROVIDER_KEY` | 空 | API Key |
| `AI_MODEL` | 空 | 模型名 |

`AI_PROVIDER` 设为任何非 `mock` 值但 `AI_PROVIDER_URL` / `AI_PROVIDER_KEY` 缺失时，后端会打警告并**静默回退到 Mock 客户端**，AI 对话仍然可用，但返回的是模板化内容。排查「AI 回答很机械」时先看后端日志有没有这条 warning。

后端需要访问外网模型服务。如果所在网络需要代理，请在 `docker-compose.yml` 的 `backend` 服务下增加：

```yaml
    environment:
      HTTPS_PROXY: http://<代理地址>:<端口>
      HTTP_PROXY: http://<代理地址>:<端口>
```

### 4.6 MCP 管理端服务（可选）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MCP_ENABLED` | `false` | 开启后后端挂载 `/mcp` 端点 |
| `MCP_CONFIRM_TTL_MINUTES` | `30` | 变更申请的有效期（分钟） |
| `MCP_PUBLIC_URL` | — | **必须填外部可访问的完整地址**，例如 `https://your-domain.com/mcp`。管理端「接入配置」页会把它原样展示给客户端复制 |
| `MCP_TOKEN_DEFAULT_DAYS` | `90` | 令牌默认有效期 |

MCP 客户端（Claude Code / Claude Desktop / VS Code）的接入步骤见 `docs/mcp-client.md`。部署要点：

- MCP 与 `/api/v1` 一样经过前端 Nginx 反代，所以对外地址跟访问网站用的是同一个域名和端口。
- 令牌在管理端 `/admin/mcp/access` 页面创建，创建时只显示一次明文。

### 4.7 启动行为

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `WEB_CONCURRENCY` | `2` | uvicorn worker 数。1~2 核用 2，4 核可用 4 |
| `RUN_MIGRATIONS` | `true` | 启动时是否执行 `alembic upgrade head` |
| `SEED_ADMIN` | `true` | 启动时是否执行管理员 seed |

多 worker 需要注意：`WEB_CONCURRENCY > 1` 时每个 worker 是独立进程，进程内缓存（AI 客户端单例、学情画像 cache）各自一份。这不影响正确性，但会让缓存命中率下降；如果使用外部 Redis 之类共享缓存则不受影响。

---

## 5. 构建与镜像说明

### 5.1 后端镜像（`backend/Dockerfile`）

两阶段构建：

1. **deps 阶段**：复制 `pyproject.toml` + `uv.lock`，用 `uv sync --frozen --no-dev` 安装依赖到 `/app/.venv`。只复制依赖描述文件是刻意的——代码改动不会让依赖层缓存失效。
2. **runtime 阶段**：复制 `.venv` 与应用代码，安装 `tzdata`（`ZoneInfo("Asia/Shanghai")` 依赖它），创建非 root 用户 `app`（uid 10001）并 `USER app` 运行。

入口脚本 `backend/docker-entrypoint.sh` 按顺序执行：

| 步骤 | 行为 | 可控变量 |
| --- | --- | --- |
| 1 | 轮询数据库 `SELECT 1`，最多 60 次、每次间隔 2 秒 | `WAIT_FOR_DB`、`DB_WAIT_ATTEMPTS` |
| 2 | `alembic upgrade head` | `RUN_MIGRATIONS` |
| 3 | `python -m scripts.create_admin`（失败只记日志，不阻塞启动） | `SEED_ADMIN`、`ADMIN_PASSWORD` |
| 4 | `exec uvicorn ... --workers N --proxy-headers --forwarded-allow-ips='*'` | `WEB_CONCURRENCY` |

`--proxy-headers` 让后端正确识别 Nginx 传来的 `X-Forwarded-For` / `X-Forwarded-Proto`，这对 MCP 审计日志里记录的客户端 IP 很关键。

### 5.2 前端镜像（`frontend/Dockerfile`）

1. **build 阶段**：`node:22-alpine` + corepack 启用 `pnpm@10.15.1`，`pnpm install --frozen-lockfile` 后 `pnpm build`。构建期通过 `ARG VITE_API_BASE_URL` 注入 API 基址，默认 `/api/v1`。
2. **runtime 阶段**：`nginx:1.27-alpine`，把 `dist/` 复制进 `/usr/share/nginx/html`，`nginx.conf` 放到 `/etc/nginx/templates/default.conf.template`。

Nginx 官方镜像启动时会用 `envsubst` 渲染模板，只替换 `${BACKEND_UPSTREAM}`（通过 `NGINX_ENVSUBST_FILTER=BACKEND_UPSTREAM` 限定），因此 `$host`、`$remote_addr` 等 Nginx 自身变量不会被误替换。渲染结果在容器内可见：

```bash
docker compose exec frontend grep -n 'proxy_pass' /etc/nginx/conf.d/default.conf
# 29:        proxy_pass http://backend:8000;
# 45:        proxy_pass http://backend:8000;
```

### 5.3 镜像体积（实测）

| 镜像 | 体积 |
| --- | --- |
| `english-practice-backend:latest` | 约 300 MB |
| `english-practice-frontend:latest` | 约 49 MB |

### 5.4 只重建某个服务

```bash
docker compose up -d --build backend     # 只重建后端并重启
docker compose up -d --build frontend    # 只重建前端并重启
```

代码改动通常会命中依赖层缓存，重建只需十几秒。

---

## 6. 日常运维

### 6.1 常用命令

```bash
docker compose ps                     # 查看状态
docker compose logs -f backend        # 跟踪后端日志
docker compose logs --tail 100 frontend
docker compose restart backend        # 重启单个服务
docker compose stop                   # 停止全部（保留容器与数据）
docker compose down                   # 删除容器与网络（保留命名卷数据）
docker compose down -v                # 删除容器、网络和**全部数据卷**（不可恢复！）
```

### 6.2 数据库迁移

迁移默认在容器启动时自动执行。手动执行：

```bash
# 查看当前版本
docker compose exec backend alembic current

# 升级到最新
docker compose exec backend alembic upgrade head

# 查看迁移历史
docker compose exec backend alembic history --verbose
```

**新增迁移文件的流程**（在开发机上）：

```bash
cd backend
alembic revision -m "describe_change"      # 手写 upgrade/downgrade
alembic upgrade head                       # 本地验证
```

提交后，服务器上 `docker compose up -d --build backend` 即会自动应用。

> 回滚迁移请谨慎：`alembic downgrade` 会执行 `downgrade()` 里的删表逻辑。生产环境优先考虑「前向修复」而不是降级。

### 6.3 备份与恢复

**逻辑备份（推荐，可跨版本恢复）**：

```bash
# 备份
docker compose exec -T db sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction \
   --routines --triggers --default-character-set=utf8mb4 "$MYSQL_DATABASE"' \
  > backup_$(date +%Y%m%d_%H%M%S).sql

# 恢复
cat backup_20261102_120000.sql | docker compose exec -T db sh -c \
  'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
```

`--single-transaction` 保证 InnoDB 表的一致性快照，不需要停服。

**定时备份**（crontab 示例，每天 3:17，保留 14 天）：

```cron
17 3 * * * cd /opt/english-practice && docker compose exec -T db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --default-character-set=utf8mb4 "$MYSQL_DATABASE"' | gzip > /var/backups/ep_$(date +\%Y\%m\%d).sql.gz && find /var/backups -name 'ep_*.sql.gz' -mtime +14 -delete
```

**物理卷备份**：直接打包命名卷 `english-practice-db-data`。必须在 `docker compose stop db` 之后做，否则可能拷到不一致的 InnoDB 文件。

### 6.4 升级与回滚

**升级**：

```bash
cd /opt/english-practice
git pull
docker compose build
docker compose up -d
```

`up -d` 只会重建有变化的容器，数据库数据卷不受影响，迁移由入口脚本自动执行。

**回滚**：使用版本化镜像标签，`.env` 中改 `IMAGE_TAG` 后重新 `up -d`：

```bash
# 发版时打标签
IMAGE_TAG=v1.2.0 docker compose build
IMAGE_TAG=v1.2.0 docker compose push   # 如果使用私有仓库

# 回滚
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=v1.1.0/' .env
docker compose up -d
```

> 回滚**应用镜像**不会回滚**数据库结构**。如果新版本包含迁移，旧版本代码可能无法在新表结构上运行。因此升级前务必先备份，涉及破坏性迁移时准备对应的 `downgrade` 脚本。

### 6.5 修改配置

`.env` 改动后需要重建容器让环境变量生效：

```bash
docker compose up -d        # 会检测到配置变化并重建
```

只有后端环境变量变化时，`docker compose up -d backend` 就够了。

注意 `VITE_API_BASE_URL` 是**构建期**变量，改了必须 `docker compose build frontend` 重新构建，仅重启无效。

### 6.6 管理员密码找回

无需进数据库，直接改 `.env`：

```bash
sed -i 's/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=NewStrongPass123/' .env
docker compose up -d backend
docker compose logs backend | grep seed   # action=password_updated
```

---

## 7. 生产环境加固

### 7.1 HTTPS

Nginx 容器本身不带证书。两种常见做法：

**方案 A：宿主机加一层反向代理（推荐）**

宿主机用 Caddy / Nginx / Traefik 终止 TLS，转发到 `127.0.0.1:8080`。以 Caddy 为例，`Caddyfile`：

```
your-domain.com {
    reverse_proxy 127.0.0.1:8080
}
```

同时把 `.env` 里的 `MCP_PUBLIC_URL` 改成 `https://your-domain.com/mcp`。

**方案 B：挂载证书到前端容器**

在 `docker-compose.yml` 的 `frontend` 服务下挂载证书目录，并在 `frontend/nginx.conf` 增加 443 server 块。这种方式需要自己处理证书续期，运维成本更高。

> 无论哪种方案，反向代理层都必须对 SSE 关闭缓冲，否则 AI 对话会变成「等一大段再一次性出现」。Caddy 默认不缓冲；如果用 Nginx 做外层，要在 `/api/` 和 `/mcp` 上加 `proxy_buffering off;`。

### 7.2 防火墙

只放行 `HTTP_PORT`（以及外层代理的 443）：

```bash
# Ubuntu / Debian (ufw)
sudo ufw allow 8080/tcp
sudo ufw enable

# CentOS / RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

`BACKEND_PORT` 与 `MYSQL_PORT` 已经绑定在 `127.0.0.1`，无需额外放行。**不要**把它们改成 `0.0.0.0`。

### 7.3 资源限制

在 `docker-compose.yml` 中为各服务加限额，防止 MySQL 或后端把宿主机内存吃满：

```yaml
services:
  db:
    deploy:
      resources:
        limits:
          memory: 1G
  backend:
    deploy:
      resources:
        limits:
          memory: 768M
  frontend:
    deploy:
      resources:
        limits:
          memory: 128M
```

> Compose v2 在非 Swarm 模式下也支持 `deploy.resources.limits`。

### 7.4 日志轮转

默认 json-file 日志会无限增长。在 `docker-compose.yml` 顶层或各服务下加：

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"

services:
  backend:
    logging: *default-logging
  db:
    logging: *default-logging
  frontend:
    logging: *default-logging
```

### 7.5 安全检查清单

- [ ] `JWT_SECRET`、`MYSQL_*_PASSWORD`、`ADMIN_PASSWORD` 都是随机强密码，不是示例值
- [ ] `.env` 权限设为 `600`：`chmod 600 .env`
- [ ] 首次部署成功后清空 `ADMIN_PASSWORD` 或设 `SEED_ADMIN=false`
- [ ] `MYSQL_PORT` / `BACKEND_PORT` 保持 `127.0.0.1` 绑定
- [ ] 对外只开放 `HTTP_PORT` 与 443
- [ ] `LANGSMITH_TRACING=false`（除非确实需要把对话内容上报到 LangSmith）
- [ ] 已配置定时备份，且**实际验证过一次恢复流程**
- [ ] 外层代理对 SSE 关闭缓冲

---

## 8. 常见问题排查

### 8.1 构建阶段报 `failed to fetch anonymous token` / 连接超时

Docker Hub 在国内不可直连。配置镜像加速器（Docker Desktop → Settings → Docker Engine，或 `/etc/docker/daemon.json`）：

```json
{
  "registry-mirrors": ["https://<你的加速器地址>"]
}
```

修改后执行 `docker restart`（Linux）或重启 Docker Desktop。若 `ghcr.io/astral-sh/uv:latest` 拉取失败，可改用 Docker Hub 镜像地址 `astral-sh/uv`，或按 §2 预先 pull。

### 8.2 后端反复重启，日志停在「等待数据库就绪」

`docker compose logs db` 查看 MySQL 是否启动失败。常见原因：

- `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD` 未设置 → compose 的 `${VAR:?}` 会直接拒绝启动，报 `请在 .env 中设置 ...`
- 宿主机 3306 被占用 → 改 `.env` 的 `MYSQL_PORT`
- 数据卷里有旧的、密码不同的 MySQL 数据 → 旧密码与当前 `MYSQL_ROOT_PASSWORD` 不一致。确认可以删数据时执行 `docker compose down -v` 重建；不能删则需要按旧密码启动后改密码。

### 8.3 后端日志 `Access denied for user 'app'@'%'`

数据卷是上一套 `MYSQL_*` 变量创建的。MySQL 只在**首次初始化**数据目录时创建用户，之后改 `.env` 的账号密码不会同步到数据库。解决方式同上：`down -v` 重建，或进入容器手动 `ALTER USER`。

### 8.4 登录接口返回 422 `validation error`，`loc: ["body","account"]`

请求体字段名错了。登录接口字段是 `account`（用户名或邮箱）+ `password`，不是 `username`。

### 8.5 页面能打开但所有接口 404

前端构建时 `VITE_API_BASE_URL` 被设成了带域名的地址，或 Nginx 反代规则没生效。检查：

```bash
# 1) 前端产物里的 baseURL 应该是 "/api/v1"
docker compose exec frontend sh -c \
  "grep -oE 'baseURL:\"[^\"]*\"' /usr/share/nginx/html/assets/request-*.js"

# 2) Nginx 上空变量会导致 proxy_pass 非法
docker compose exec frontend grep -n proxy_pass /etc/nginx/conf.d/default.conf
```

第二项如果显示 `http://:8000`，说明 `BACKEND_UPSTREAM` 环境变量没注入，检查 compose 里 `frontend.environment.BACKEND_UPSTREAM`。

### 8.6 刷新 `/admin/...` 页面得到 404

SPA 回退没生效。确认 `frontend/nginx.conf` 里 `location /` 有 `try_files $uri $uri/ /index.html;`，且构建后的 `index.html` 在 `/usr/share/nginx/html` 下。

### 8.7 AI 对话不是逐字出现，而是卡住很久后一次性输出

SSE 被缓冲了。检查 `frontend/nginx.conf` 中 `/api/` 与 `/mcp` 的 `proxy_buffering off;`。如果外层还有一层反向代理（如宿主机的 Nginx），那一层也要关。

后端已经主动返回 `X-Accel-Buffering: no` 头，但某些代理不认这个头，仍需显式配置。

### 8.8 单词朗读没有声音

容器内**没有 Windows 系统语音（SAPI）**，`/api/v1/words/{id}/audio/file` 会返回 `503 系统语音不可用`。这是预期行为，不是部署故障。

前端 `AudioButton.vue` 已实现三级降级：

1. 词条配置了 `audio_url` → 直接播放音频地址；
2. 否则调用后端 TTS 合成 WAV（Linux 容器内必然失败）；
3. 再退到浏览器内置 `speechSynthesis` 朗读。

所以只要用户浏览器支持语音合成（Chrome / Edge / Safari 桌面版都支持），朗读功能仍可用。若要求服务端生成音频，需要把 TTS 换成云端语音接口，而不是依赖系统语音。

### 8.9 修改 `.env` 后配置没生效

`docker compose up -d` 只在检测到配置差异时重建容器。若确实没生效：

```bash
docker compose down && docker compose up -d
docker compose exec backend printenv | grep -E 'JWT_SECRET|DATABASE_URL'
```

注意 `backend/.env` 文件在构建时被 `.dockerignore` 排除了，容器内的配置**只来自** compose 注入的环境变量，不存在「容器里还留着旧的 backend/.env」这种情况。

### 8.10 如何进容器排查

```bash
# 后端 shell（非 root 用户 app）
docker compose exec backend sh
docker compose exec backend python -c "from app.core.config import get_settings; print(get_settings().DATABASE_URL)"

# 数据库 shell
docker compose exec db mysql -uapp -p english_practice

# 前端页面目录
docker compose exec frontend ls -la /usr/share/nginx/html
```

### 8.11 健康检查一直 unhealthy

```bash
docker inspect --format '{{json .State.Health}}' english-practice-backend | python -m json.tool
```

健康检查打的是容器内 `http://127.0.0.1:8000/api/v1/health`，不经过 Nginx。如果这个不通但服务看起来正常，多半是 uvicorn 启动到一半崩了——看 `docker compose logs backend` 最末尾的 traceback。

---

## 9. 已知限制

| 限制 | 影响 | 建议 |
| --- | --- | --- |
| 系统语音 TTS 仅 Windows | 容器内 `/words/{id}/audio/file` 返回 503，前端降级到浏览器 `speechSynthesis` | 见 §8.8；若必须服务端合成，改为云端 TTS |
| 单机部署，无编排 | 服务器宕机需手动恢复；无横向扩展 | 更高可用需求请改用 Kubernetes 或云托管数据库 |
| 进程内缓存 | 多 worker 下缓存不共享，Nginx 不做负载均衡到多实例 | 单机多 worker 无功能问题；多实例需引入 Redis |
| 导入任务在应用内后台执行 | 后端重启会中断进行中的导入任务 | 需要可靠任务队列时改用 Celery / RQ |
| 无内置 HTTPS | 明文 HTTP | 见 §7.1 |
| 数据库不做自动备份 | 卷丢失即数据丢失 | 见 §6.3，务必配定时备份 |

---

## 附录 A：部署验证记录

以下验证于 2026-11-02 在 Windows 11 + Docker Desktop（Engine 28.3.2 / Compose v2.39.1）上完成，`MYSQL_PORT` 因本机 3306 被占用改为 3307。

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 镜像构建 | `docker compose build` | 后端 300 MB，前端 49 MB，均成功 |
| 三容器健康 | `docker compose ps` | db / backend / frontend 全部 `healthy` |
| 自动迁移 | `docker compose logs backend` | 依次执行 0001 → ... → `e7b2c4d9a1f3 (head)`，无报错 |
| 管理员 seed | 同上 | 首次 `action=created user_id=1`，重启后 `action=password_updated`（幂等） |
| 前端静态页 | `curl :8080/` | 200，返回 `index.html` |
| API 反代 | `curl :8080/api/v1/health` | `{"code":0,...,"data":{"status":"up"}}` |
| SPA 深链接 | `curl :8080/admin/mcp/approvals` | 200（回退到 index.html） |
| 登录 | `POST /api/v1/auth/login` | 200，返回 access_token |
| 用户注册 | `POST /api/v1/auth/register` | 201，创建成功 |
| 业务写操作 | 创建词书 / 单词 | 201，数据落库 |
| 重启后数据保留 | `docker compose restart backend` | 词书与单词仍在 |
| 前端构建期变量 | 检查产物 `request-*.js` | `baseURL:"/api/v1"`（同源相对路径） |
| 资源缓存头 | `curl -I /assets/<hash>.js` | `Cache-Control: public, max-age=31536000, immutable` |
| SSE 流式 | `POST /api/v1/agent/chat` | 逐事件返回 `event: meta` / `event: delta`，未被缓冲 |
| MCP 端点 | `POST /mcp`（initialize） | 200，返回 `serverInfo: english-practice-admin` |
| 非 root 运行 | `docker exec backend id` | `uid=10001(app)` |
| 卷可写 | 在容器内 `touch /app/var/tts/.probe` | 成功 |
| 数据库版本 | `SELECT VERSION()` | MySQL 8.0.46，库 `english_practice` 存在 |
| Nginx 模板渲染 | `grep proxy_pass /etc/nginx/conf.d/default.conf` | `http://backend:8000`（变量已替换） |
| TTS 降级 | `GET /api/v1/words/1/audio/file` | 503（预期，见 §8.8） |

验证结束后已执行 `docker compose down -v` 清理测试环境。

---

## 附录 B：文件清单

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 三服务编排、卷、网络、健康检查 |
| `docker.env.example` | 部署环境变量模板（复制为 `.env`） |
| `.gitignore` | 忽略根目录 `.env` |
| `backend/Dockerfile` | 后端两阶段镜像 |
| `backend/docker-entrypoint.sh` | 等库 → 迁移 → seed → 启动 |
| `backend/.dockerignore` | 排除 `.venv`、`tests`、`var` 等 |
| `frontend/Dockerfile` | 前端 pnpm 构建 + Nginx 运行 |
| `frontend/nginx.conf` | SPA 回退、API/MCP 反代、缓存策略 |
| `frontend/.dockerignore` | 排除 `node_modules`、`dist` 等 |
| `docs/docker-deployment.md` | 本文档 |
