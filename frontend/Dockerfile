# syntax=docker/dockerfile:1
# 前端镜像：pnpm 构建静态产物 → Nginx 托管并反向代理 /api 与 /mcp。
# 构建上下文必须是 frontend/ 目录（docker compose 已按此配置）。

# ---------- 阶段 1：构建 ----------
FROM node:22-alpine AS build

ENV CI=true \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

RUN corepack enable && corepack prepare pnpm@10.15.1 --activate

WORKDIR /app

# 先装依赖，最大化利用层缓存。
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
# 构建期 API 地址：默认走同源 /api/v1，由 Nginx 反代到后端。
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm build

# ---------- 阶段 2：运行时 ----------
FROM nginx:1.27-alpine AS runtime

ENV TZ=Asia/Shanghai

RUN set -eux; \
    apk add --no-cache tzdata; \
    cp /usr/share/zoneinfo/$TZ /etc/localtime; \
    echo "$TZ" > /etc/timezone

# 以官方镜像的 envsubst 模板机制注入后端地址：只替换 ${BACKEND_UPSTREAM}，
# 保留 nginx 自身的 $host / $remote_addr 等变量不被误替换。
ENV NGINX_ENVSUBST_TEMPLATE_SUFFIX=.template \
    NGINX_ENVSUBST_FILTER=BACKEND_UPSTREAM \
    BACKEND_UPSTREAM=backend

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
