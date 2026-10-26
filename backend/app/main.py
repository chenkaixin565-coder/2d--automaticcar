"""
FastAPI 应用入口模块。

模块功能：创建 FastAPI 应用，装配日志、CORS、REST 路由、WebSocket 通道，
并托管前端构建产物（dist），实现单容器部署。启动方式：
uvicorn app.main:app --host 0.0.0.0 --port 8000

V2.0 变更：
  - 仿真主循环加异常兜底：单次 tick 抛错不再让整个仿真静默停摆；
  - state 帧推送循环改为全进程一份（与 WebSocket 连接数无关）；
  - /health 额外返回 tick 健康状况，可发现"进程活着但仿真死了"；
  - 静态托管做路径解析防穿越。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.rest import create_rest_router
from app.api.websocket import bind_engine_events, create_ws_router, push_state_loop
from app.core.config import settings
from app.services.simulation_engine import SimulationEngine

# ---------- 日志配置（要求：系统各环节均留日志） ----------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/simulation.log")


def setup_logging() -> None:
    """配置根日志：同时输出到控制台与日志文件（文件不可写时降级为仅控制台）。"""
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    try:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:  # pragma: no cover - 只读文件系统（如部分容器）时降级
        logging.getLogger("app.main").warning("日志文件不可写，仅输出到控制台: %s", LOG_FILE)

    # 降低 uvicorn 内部访问日志噪音，保留启动信息。
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("app.main")

# 仿真健康状态：最后一次成功 tick 的时间戳与连续失败次数。
_TICK_STATE = {"last_tick_at": None, "tick_errors": 0}


async def _run_simulation_loop() -> None:
    """
    仿真主循环：独立于 WebSocket 连接，按 tick 间隔推进引擎。

    V2.0：单次 tick 异常只记日志并计数，不终止循环——历史上任意一个
    未捕获异常都会让仿真永久冻结，而 HTTP 仍然返回 200，极难排查。
    """
    while True:
        await asyncio.sleep(settings.tick_interval_ms / 1000)
        try:
            engine.tick()
        except Exception:  # noqa: BLE001 - 仿真循环必须活下去
            _TICK_STATE["tick_errors"] += 1
            logger.exception("仿真 tick 执行失败（累计 %d 次）", _TICK_STATE["tick_errors"])
            if _TICK_STATE["tick_errors"] % 50 == 0:
                await asyncio.sleep(1.0)
        else:
            _TICK_STATE["last_tick_at"] = time.time()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """应用生命周期钩子：启动仿真循环与推送循环，关闭时取消任务。"""
    logger.info(
        "仿真系统启动：tick=%dms, 低电量阈值=%.0f%%, 过热阈值=%.0f℃",
        settings.tick_interval_ms,
        settings.low_battery_threshold,
        settings.overheat_threshold,
    )
    bind_engine_events(engine)
    tick_task = asyncio.create_task(_run_simulation_loop())
    push_task = asyncio.create_task(push_state_loop(engine, settings.tick_interval_ms))
    try:
        yield
    finally:
        tick_task.cancel()
        push_task.cancel()
        logger.info("仿真系统已关闭")


# ---------- 应用装配 ----------

app = FastAPI(
    title="智能巡检机器人二维仿真系统",
    description="基于 FastAPI 的二维栅格机器人仿真后端：A* 寻路、虚拟传感器、规则异常检测、"
    "一键路线规划、自动清障与地图编辑（V2.1.1）",
    version="V2.1.1",
    lifespan=lifespan,
)

# CORS：允许本地前端开发服务器跨域联调；"*" 时不能同时开启 credentials。
CORS_ORIGINS = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:4173"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局唯一仿真引擎。
engine = SimulationEngine()

# 挂载 REST 与 WebSocket 路由。
app.include_router(create_rest_router(engine))
app.include_router(create_ws_router(engine))


@app.get("/api/v1/health", summary="健康检查")
async def health() -> dict:
    """容器/负载均衡健康探针，附带仿真循环健康状况。"""
    last = _TICK_STATE["last_tick_at"]
    age = None if last is None else round(time.time() - last, 1)
    return {
        "status": "ok",
        "version": "V2.1.1",
        "tick_errors": _TICK_STATE["tick_errors"],
        "last_tick_age_s": age,
        "tick_alive": age is not None and age < max(5.0, settings.tick_interval_ms / 1000 * 10),
    }


# ---------- 前端静态资源托管（单容器部署） ----------

DIST_DIR = Path(os.getenv("DIST_DIR", "static/dist")).resolve()

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """
        前端单页应用回退路由：非 API 请求返回静态文件或 index.html。

        :param full_path: 请求的相对路径。
        :return: 静态文件或 index.html。
        """
        candidate = (DIST_DIR / full_path).resolve()
        # 防目录穿越：解析后的路径必须仍位于 dist 目录内。
        if full_path and candidate.is_file() and str(candidate).startswith(str(DIST_DIR)):
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")

    logger.info("前端静态资源托管已启用: %s", DIST_DIR)
else:
    logger.warning("未找到前端构建目录 %s，仅提供 API 服务", DIST_DIR)
