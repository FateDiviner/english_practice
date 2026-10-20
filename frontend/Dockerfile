# 前端镜像：node 构建 → nginx 托管静态文件
FROM node:20-alpine AS build

WORKDIR /app

# 依赖清单先拷，命中层缓存——源码变更频率远高于依赖
COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .
# 构建产物里不需要 VITE_API_BASE：nginx 会把 /api 反代到后端，
# 前端继续用相对路径，同一份产物既能跑在容器里也能跑在本地 dev server
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
