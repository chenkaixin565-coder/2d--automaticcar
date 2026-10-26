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
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api.rest import create_rest_router
from app.api.websocket import bind_engine_events, create_ws_router, manager, push_state_loop
from app.core.config import settings
from app.core.metrics import metrics
from app.core.ratelimit import limiter
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
    logger.info(
        "访问控制: mode=%s, 限流=%d/min (burst=%d)",
        settings.auth_mode,
        settings.rate_limit_per_minute,
        settings.rate_limit_burst,
    )
    if settings.auth_mode == "open-demo":
        logger.warning("未配置 OPERATOR_KEY：当前为开放演示模式，任何访问者都能修改状态")
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
    "一键路线规划、自动清障与地图编辑（V2.2.1）",
    version="V2.2.1",
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

# ---------- 访问控制、限流与指标（V2.2.0） ----------

# 这些路径不参与限流，也不需要密钥：健康探针与指标抓取。
EXEMPT_PATHS = {"/api/v1/health", "/metrics"}

# 会改变系统状态的 HTTP 方法，需要操作密钥。
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def client_ip(request: Request) -> str:
    """
    取客户端 IP：反向代理后优先用 X-Forwarded-For 的第一段。

    :param request: 当前请求。
    :return: 用于限流的客户端标识。
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def has_operator_permission(request: Request) -> bool:
    """
    校验写操作权限。

    - 未配置 OPERATOR_KEY：开放演示模式，放行（启动日志会警告）。
    - READONLY_MODE=true：一律拒绝写操作。
    - 配置了 OPERATOR_KEY：必须提供匹配的 X-API-Key（或 ?api_key=）。

    :param request: 当前请求。
    :return: 是否允许执行写操作。
    """
    if settings.readonly_mode:
        return False
    if not settings.operator_key:
        return True
    supplied = request.headers.get("x-api-key") or request.query_params.get("api_key") or ""
    return bool(supplied) and secrets.compare_digest(supplied, settings.operator_key)


@app.middleware("http")
async def guard_requests(request: Request, call_next):
    """
    统一入口守卫：限流 → 鉴权 → 计数。

    :param request: 当前请求。
    :param call_next: 下游处理函数。
    :return: 响应。
    """
    path = request.url.path
    if path.startswith("/api/v1") or path == "/metrics":
        if path not in EXEMPT_PATHS:
            allowed, wait = limiter.allow(
                client_ip(request),
                settings.rate_limit_per_minute,
                settings.rate_limit_burst,
            )
            if not allowed:
                metrics.inc("rate_limited_total")
                return JSONResponse(
                    {"detail": "请求过于频繁，请稍后再试"},
                    status_code=429,
                    headers={"Retry-After": str(max(1, int(wait + 0.999)))},
                )
        if request.method in WRITE_METHODS and not has_operator_permission(request):
            metrics.inc("auth_rejected_total")
            detail = "只读模式：当前部署不允许修改状态" if settings.readonly_mode else "需要操作密钥"
            return JSONResponse(
                {"detail": detail},
                status_code=403 if settings.readonly_mode else 401,
                headers={"WWW-Authenticate": "ApiKey"},
            )

    response = await call_next(request)
    if path.startswith("/api/v1") or path == "/metrics":
        metrics.inc(f'http_requests_total{{method="{request.method}",status="{response.status_code}"}}')
    return response


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
        "version": "V2.2.1",
        "tick_errors": _TICK_STATE["tick_errors"],
        "last_tick_age_s": age,
        "tick_alive": age is not None and age < max(5.0, settings.tick_interval_ms / 1000 * 10),
        "auth_mode": settings.auth_mode,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "ws_clients": len(manager.active_connections),
    }


@app.get("/metrics", summary="Prometheus 指标", include_in_schema=False)
async def prometheus_metrics() -> PlainTextResponse:
    """以 Prometheus 文本格式暴露运行指标（不含任何业务敏感数据）。"""
    engine_state = engine.state_dict()["data"]
    extra = [
        "# HELP irm_ws_clients 当前 WebSocket 连接数",
        "# TYPE irm_ws_clients gauge",
        f"irm_ws_clients {len(manager.active_connections)}",
        "# HELP irm_engine_battery_percent 机器人剩余电量",
        "# TYPE irm_engine_battery_percent gauge",
        f"irm_engine_battery_percent {engine_state['battery']}",
        "# HELP irm_engine_position 机器人坐标",
        "# TYPE irm_engine_position gauge",
        f'irm_engine_position{{axis="x"}} {engine_state["x"]}',
        f'irm_engine_position{{axis="y"}} {engine_state["y"]}',
        "# HELP irm_patrol_running 是否正在巡检（1=是）",
        "# TYPE irm_patrol_running gauge",
        f"irm_patrol_running {1 if engine_state.get('patrol', {}).get('running') else 0}",
        "# HELP irm_tick_errors_total 仿真 tick 累计异常次数",
        "# TYPE irm_tick_errors_total counter",
        f"irm_tick_errors_total {_TICK_STATE['tick_errors']}",
    ]
    return PlainTextResponse(metrics.render(extra), media_type="text/plain; version=0.0.4")


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
