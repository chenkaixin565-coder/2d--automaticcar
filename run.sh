#!/usr/bin/env bash
# 降级运行脚本：未装 Docker 时，本地先后端 + 构建前端启动系统
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> 安装后端依赖"
python3 -m pip install -r backend/requirements.txt

echo "==> 安装前端依赖并构建（同源后端版本）"
cd frontend
npm ci
VITE_BACKEND_SAME_ORIGIN=true npm run build
cd "$ROOT"
mkdir -p backend/static/dist
cp -r frontend/dist/* backend/static/dist/

echo "==> 启动后端 (http://localhost:8000)"
cd backend
PORT=8000 python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
