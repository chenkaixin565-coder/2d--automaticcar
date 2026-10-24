"""
FastAPI 应用入口模块。

模块功能：创建 FastAPI 应用，装配日志、CORS、REST 路由、WebSocket 通道，
并托管前端构建产物（dist），实现单容器部署。启动方式：
uvicorn app.main:app --host 0.0.0.0 --port 8000
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.rest import create_rest_router
from app.api.websocket import create_ws_router
from app.core.config import settings
from app.services.simulation_engine import SimulationEngine

# ---------- 日志配置（要求：系统各环节均留日志） ----------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/simulation.log")


def setup_logging() -> None:
    """配置根日志：同时输出到控制台与滚动日志文件。"""
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    # 降低 uvicorn 内部访问日志噪音，保留启动信息。
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("app.main")


async def _run_simulation_loop() -> None:
    """仿真主循环：独立于 WebSocket 连接，按 tick 间隔推进引擎。"""
    while True:
        await asyncio.sleep(settings.tick_interval_ms / 1000)
        engine.tick()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """应用生命周期钩子：启动/关闭时记录关键配置，便于运维排查。"""
    logger.info(
        "仿真系统启动：tick=%dms, 低电量阈值=%.0f%%, 过热阈值=%.0f℃",
        settings.tick_interval_ms,
        settings.low_battery_threshold,
        settings.overheat_threshold,
    )
    tick_task = asyncio.create_task(_run_simulation_loop())
    try:
        yield
    finally:
        tick_task.cancel()
        logger.info("仿真系统已关闭")


# ---------- 应用装配 ----------

app = FastAPI(
    title="智能巡检机器人二维仿真系统",
    description="基于 FastAPI 的二维栅格机器人仿真后端：A* 寻路、虚拟传感器、规则异常检测",
    version="V1.0",
    lifespan=lifespan,
)

# CORS：允许本地前端开发服务器跨域联调。
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局唯一仿真引擎。
engine = SimulationEngine()

# 挂载 REST 与 WebSocket 路由。
app.include_router(create_rest_router(engine))
app.include_router(create_ws_router(engine, settings.tick_interval_ms))


@app.get("/api/v1/health", summary="健康检查")
async def health() -> dict:
    """容器/负载均衡健康探针。"""
    return {"status": "ok", "version": "V1.0"}


# ---------- 前端静态资源托管（单容器部署） ----------

DIST_DIR = Path(os.getenv("DIST_DIR", "static/dist"))

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """
        前端单页应用回退路由：非 API 请求一律返回 index.html。

        :param full_path: 请求的相对路径。
        :return: 静态文件或 index.html。
        """
        candidate = DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")

    logger.info("前端静态资源托管已启用: %s", DIST_DIR)
else:
    logger.warning("未找到前端构建目录 %s，仅提供 API 服务", DIST_DIR)
