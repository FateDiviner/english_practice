# Docker 部署步骤

本文用 Docker Compose 部署整套平台（前端 + 后端 + MySQL），共 6 步。

---

## 第 1 步：准备环境

服务器上装好 Docker，确认能正常使用：

```bash
docker --version
docker compose version
```

要求：Docker ≥ 20.10，Compose v2，内存 ≥ 2 GB，磁盘 ≥ 5 GB。

国内服务器建议先配镜像加速器，并提前拉好基础镜像（否则构建会卡在下载超时）：

```bash
docker pull python:3.11-slim
docker pull node:22-alpine
docker pull nginx:1.27-alpine
docker pull mysql:8.0
docker pull ghcr.io/astral-sh/uv:latest
docker pull docker/dockerfile:1
```

---

## 第 2 步：上传代码

把项目放到服务器上，例如：

```bash
cd /opt
git clone <仓库地址> english-practice
cd english-practice
```

---

## 第 3 步：创建配置文件

```bash
cp docker.env.example .env
```

---

## 第 4 步：修改 `.env`

打开 `.env`，**必须改这 4 项**，其余保持默认即可：

```env
MYSQL_ROOT_PASSWORD=<随机密码>
MYSQL_PASSWORD=<随机密码>
JWT_SECRET=<随机字符串>
ADMIN_PASSWORD=<管理员登录密码>
```

生成随机字符串：

```bash
openssl rand -hex 32
```

其余常用项（一般不用动）：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `HTTP_PORT` | `8080` | 网站端口，想用 80 就改成 `80` |
| `MYSQL_PORT` | `3306` | 数据库端口，服务器 3306 被占用时改掉 |
| `ADMIN_USERNAME` | `admin` | 管理员账号 |
| `MCP_PUBLIC_URL` | `http://127.0.0.1:8080/mcp` | 用 MCP 时改成对外域名 |

> `MYSQL_PASSWORD` 只使用字母、数字、`-`、`_`，不要用 `@ : / ? #` 等符号。

---

## 第 5 步：构建并启动

```bash
docker compose up -d --build
```

首次构建约 2~5 分钟。启动时会自动建表、自动创建管理员账号，无需手动操作数据库。

---

## 第 6 步：确认与访问

查看状态，三个容器都要是 `healthy`：

```bash
docker compose ps
```

验证服务正常：

```bash
curl http://127.0.0.1:8080/api/v1/health
# 返回 {"code":0,"message":"ok","data":{"status":"up"}}
```

浏览器打开 `http://<服务器IP>:8080`，用 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录。

**如果对外网访问，记得开放端口：**

```bash
sudo ufw allow 8080/tcp
```

---

## 常用命令

```bash
docker compose ps                  # 查看状态
docker compose logs -f backend     # 看后端日志
docker compose restart backend     # 重启后端
docker compose stop                # 停止服务
docker compose up -d               # 启动服务
```

**升级到新版本：**

```bash
git pull
docker compose up -d --build
```

数据保存在 Docker 卷里，升级不会丢数据。

**备份数据库：**

```bash
docker compose exec -T db sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction \
   --default-character-set=utf8mb4 "$MYSQL_DATABASE"' \
  > backup_$(date +%Y%m%d).sql
```

---

## 常见问题

**构建时报网络超时 / `failed to fetch anonymous token`**
Docker 拉不到镜像。配置镜像加速器，或按第 1 步提前 `docker pull`。

**后端一直重启，日志停在「等待数据库就绪」**
多为端口冲突或密码不一致。改 `.env` 里的 `MYSQL_PORT`；如果之前用旧密码启动过，执行 `docker compose down -v` 清空数据后重新启动（**会删除已有数据**）。

**页面能打开但接口全部 404**
前端只支持同源访问。确认 `.env` 里的 `VITE_API_BASE_URL` 是 `/api/v1`（不要改成带域名或 IP 的地址），改完要重新 `docker compose build frontend`。

**AI 回答很机械、像模板**
后端日志里会有一条回退警告。说明 `AI_PROVIDER_URL` 或 `AI_PROVIDER_KEY` 没填对，AI 已回退到内置 Mock 模式。填好这三项后重启后端：

```env
AI_PROVIDER=openai
AI_PROVIDER_URL=https://<模型服务地址>/v1
AI_PROVIDER_KEY=<你的 Key>
AI_MODEL=<模型名>
```

**单词朗读没有声音**
服务器上没有系统语音（Windows 语音），后端生成音频会失败，但页面会自动改用浏览器朗读，功能仍可用。

**忘记管理员密码**
改 `.env` 的 `ADMIN_PASSWORD`，然后重启后端即可自动重置：

```bash
docker compose up -d backend
```

---

## 安全提示

部署到公网前请确认：

- 第 4 步的 4 个密码都换成了随机强密码，不是示例值
- `.env` 权限设为只有本人可读：`chmod 600 .env`
- 对外只开放 `HTTP_PORT`，不要开放数据库端口
- 首次启动成功后，把 `.env` 里的 `ADMIN_PASSWORD` 清空，否则每次重启都会重置管理员密码
- 需要 HTTPS 时，在服务器上用 Nginx 或 Caddy 反代到 `127.0.0.1:8080` 即可
