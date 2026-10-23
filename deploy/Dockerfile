# 智能巡检机器人二维仿真系统 V1.0 前端 Docker 构建
# 作者：前端开发组
# 日期：2026-10-23
# 版本：V1.0
#
# 多阶段构建：
#   Stage 1 使用 Node 镜像构建前端静态产物。
#   Stage 2 使用 Nginx 镜像托管 dist/。
# 后续接入 FastAPI 后端时，可将 Stage 2 替换为 python:3.11-slim
# 并通过 FastAPI 的 StaticFiles 托管 dist/。

FROM node:22-alpine AS builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
