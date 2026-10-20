# 远程服务器 Docker 部署

面向从零部署到一台全新 Linux 服务器的场景。本地开发不需要看这份文档。

## 一、服务器要求

| 项 | 最低 | 说明 |
| :--- | :--- | :--- |
| CPU | 2 核 | 构建阶段 `npm ci` 会吃满 |
| 内存 | **2 GB** | MySQL 约 400MB + 后端 + nginx；`npm ci` 峰值可能到 1.5GB，1G 服务器会在构建时被 OOM 杀掉 |
| 磁盘 | 10 GB | `node_modules` 构建层 + MySQL 数据 + faiss 索引 |
| **外网出口** | 必须有 | 后端要调 AI 供应商做 embedding 与对话。没外网则 RAG 降级到 BM25，AI 伴学直接不可用 |
| Docker | 20.10+ | 需要 compose v2（`docker compose`，不是老的 `docker-compose`） |

安装 Docker（Ubuntu / Debian）：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER    # 重新登录生效
docker compose version
```

## 二、部署步骤

### 1. 取得代码

```bash
# 方式一：git，更新最方便
git clone <仓库地址> /opt/english_practice
cd /opt/english_practice

# 方式二：打 tar 包传上去，不带 node_modules 与 .venv，体积小速度快
git archive --format=tar.gz -o deploy.tar.gz HEAD
scp deploy.tar.gz user@server:/opt/english_practice/
```

**不要用 rsync 直接同步工作目录**：会把本机的 `node_modules`（数千个小文件）和 `.venv` 一并传上去，既慢又因为是 Windows 构建而在 Linux 上无法使用。

### 2. 配置环境变量

```bash
cd /opt/english_practice
cp .env.example .env
chmod 600 .env
```

必须修改的几项：

```ini
MYSQL_ROOT_PASSWORD=<随机长串>
MYSQL_PASSWORD=<随机长串>
SECRET_KEY=<随机长串>

AI_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
AI_API_KEY=<你的 key>
AI_MODEL=glm-5.3
```

生成随机串：

```bash
openssl rand -hex 32
```

`SECRET_KEY` 是 JWT 的签名密钥，泄漏等于任何人都能伪造任意账号的令牌，务必改成随机长串，不要沿用示例值。

这份 `.env` 严禁提交进 git。`.gitignore` 已覆盖，但若走 tar 包部署，需确认打包时没把本地的 `.env` 带进去。

### 3. 构建并启动

```bash
docker compose up -d --build
```

首次构建较久：`npm ci` + `pip install` 依赖安装，通常 5~15 分钟。之后有层缓存，仅改代码时重建只需一两分钟。

### 4. 验证

```bash
docker compose ps                                # 三个服务都应为 healthy
docker compose logs -f backend | head -30
curl http://localhost:8080/api/health            # 经 nginx 反代到后端
```

浏览器访问 `http://服务器IP:8080`。

## 三、首次启动后必须做的事

### 提升第一个管理员

管理入口只对管理员可见，而注册接口只会把**首个注册用户**自动提升为管理员——这条路径对全新安装有效。若注册时漏掉了（或库里已有历史账号），需手动提升：

```bash
# 先在网页上注册一个普通账号，再执行：
docker compose exec backend python -m scripts.promote_admin <用户名>
```

脚本只做提升，不创建账号，也不打印任何凭据。退出码：`0` 已提升、`1` 未变更（用户不存在 / 已是管理员 / 是游客）、`2` 用法错误。

### 确认向量索引预热完成

后端启动时会在后台线程把 313 个词条向量化（约 32 次 embedding 调用，几十秒）。该线程**不阻塞启动，也不占用用户请求**；预热未完成时的检索会暂时只有 BM25 与图谱两路，向量路无结果。

```bash
docker compose logs backend | grep "索引预热完成"
```

### 上传知识库

管理页「知识库」支持 `.md` / `.txt` / `.pdf` / `.docx`。上传时同步解析与切块，向量化在后台完成。

扫描版 PDF 没有文字层会被明确拒绝——本平台不做 OCR，请改传文字版或导出为 `.md`。

## 四、备份与恢复

数据分布在两个地方：**MySQL 存业务数据**（用户、练习记录、词库、知识库文档与切块），**faiss 卷存向量索引**。后者可以由前者重建，优先级更低。

```bash
# 数据库备份
docker compose exec db sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" english_practice' \
  > backup-$(date +%F).sql

# 向量索引备份（可选，不备份也能靠重新索引恢复）
docker run --rm -v english_practice_rag-index:/data -v "$PWD":/backup alpine \
  tar czf /backup/rag-index-$(date +%F).tgz -C /data .
```

卷名前缀由 compose 的项目名决定（默认取目录名）。实际名字用 `docker volume ls` 确认。

恢复：

```bash
docker compose exec -T db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" english_practice' \
  < backup-2026-10-20.sql
```

**危险操作**：`docker compose down -v` 会连同两个卷一起删除，即清空全部学习数据。生产环境慎用。

## 五、更新与回滚

```bash
cd /opt/english_practice
git pull
docker compose up -d --build      # 只重建有变化的服务
```

数据在卷中，重建容器不会丢失。表结构变更会在后端启动时由 `init_db()` 幂等补齐——它只加列、不删列、不改列。

回滚到某个版本：

```bash
git checkout <commit>
docker compose up -d --build
```

代码可以回滚，但**数据库结构回不去**：`init_db()` 补的列不会因为回滚代码而消失。若回滚后需要连数据一起退回，用备份的 SQL 恢复。

## 六、安全边界

compose 的默认暴露面是收敛的，需保持：

| 服务 | 暴露方式 |
| :--- | :--- |
| `frontend` | `8080:80`，**唯一对公网开放的端口** |
| `backend` | 仅 `expose`，走 compose 内部网络 |
| `db` | 连 `expose` 都没有，完全隔离在内部网络 |

服务器防火墙只开 80（或 443）。**不要开放 3306 与 8000**：

```bash
sudo ufw allow 80/tcp
sudo ufw enable
```

HTTPS 建议在服务器上再套一层 Caddy 或 certbot 反代到 8080，而不是改容器内 nginx 的证书配置——后者要把证书续期挂进 volume，复杂度不划算。

```nginx
# Caddy 一行配置，自动签发与续期证书
your.domain.com {
    reverse_proxy 127.0.0.1:8080
}
```

## 七、常见问题

### 构建时 `npm ci` 卡住或超时

`frontend/.npmrc` 钉了 `registry.npmmirror.com`（本机直连 npmjs.org 会 ECONNRESET）。**服务器若在海外，该镜像源会很慢**。临时覆盖：

```bash
docker compose build --build-arg npm_config_registry=https://registry.npmjs.org frontend
```

永久生效则删除或改写 `frontend/.npmrc`。

### MySQL 反复重启，`docker compose ps` 显示 Restarting

大概率是内存不足被 OOM Killer 杀掉。给 compose 加资源限制：

```yaml
  db:
    deploy:
      resources:
        limits:
          memory: 1G
```

或者直接给服务器加内存——MySQL 是三者中最吃内存的。

### 后端日志出现「向量服务返回 400」

当前供应商的 embedding 单次批量上限是 10 条，配置项 `EMBEDDING_BATCH_SIZE` 若被改大就会触发。该失败是静默降级的，症状表现为「向量路没有召回」，排查时容易误判成检索逻辑问题。

### RAG 检索不到知识库内容

按顺序检查：

```bash
docker compose logs backend | grep -i "索引\|embedding"
docker compose exec backend python -c \
  "from app.rag import store; print(store.get_store().count('kb_chunks'), store.get_store().count('word_chunks'))"
```

两个计数都为 0 说明 embedding 调用失败（通常是 `AI_API_KEY` 无效或服务器无外网）。管理页「检索调试」可直接试跑一次检索并查看各阶段耗时与候选。

### 容器起来就退出

```bash
docker compose logs backend
```

若报 `python: can't open file '/app/main.py'`，说明镜像构建时漏拷了入口文件。当前 Dockerfile 已显式 `COPY main.py`，重新构建即可。

### 数据库连接被拒

后端启动早于 MySQL 就绪。compose 里已用 `depends_on: condition: service_healthy` 加 `mysqladmin ping` 健康检查保证顺序。若仍是此错误，检查 `db` 服务是否 healthy：

```bash
docker compose ps
docker compose logs db | tail -20
```

## 八、运维常用命令

```bash
docker compose ps                     # 服务状态与健康度
docker compose logs -f backend        # 跟随后端日志
docker compose restart backend        # 重启后端（数据不受影响）
docker compose down                   # 停止并删除容器，保留卷
docker compose down -v                # 停止并删除容器与卷（清空数据）
docker compose up -d --build          # 更新后重建
docker system df                      # 查看镜像与卷占用
docker volume ls                      # 列出所有卷
```
