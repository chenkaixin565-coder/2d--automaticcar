# 智能巡检机器人二维仿真系统 —— 全栈单容器镜像
# 多阶段构建：前端用 Node 构建静态产物，后端用 Python 托管并 serve 前端
FROM node:20-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
# 共享规则与默认地图（前端构建时 import ../../../shared/*.json）
COPY shared/ /shared/
# 同源部署：前端由后端托管，构建期开启自动接入后端开关
RUN VITE_BACKEND_SAME_ORIGIN=true npm run build

FROM python:3.11-slim AS backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
# 运行时读取 shared/simulation-rules.json 与 shared/default-map.json
COPY shared/ ./shared/
COPY --from=frontend /frontend/dist ./backend/static/dist

WORKDIR /app/backend
EXPOSE 8000

# 端口（PORT）与仿真 tick 速率（TICK_INTERVAL_MS）可通过环境变量覆盖
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
