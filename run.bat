@echo off
REM 降级运行脚本：未装 Docker 时本地启动系统（需先装 Python 与 Node）
setlocal
cd /d %~dp0

echo ==^> 安装后端依赖
python -m pip install -r backend\requirements.txt

echo ==^> 安装前端依赖并构建
cd frontend
call npm ci
set VITE_BACKEND_SAME_ORIGIN=true
call npm run build
cd ..

if not exist backend\static\dist mkdir backend\static\dist
xcopy /E /Y /I frontend\dist backend\static\dist

echo ==^> 启动后端 (http://localhost:8000)
cd backend
set PORT=8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
endlocal
