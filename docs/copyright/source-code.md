# 智能巡检机器人二维仿真系统 V1.0 源代码

软件名称：智能巡检机器人二维仿真系统
版本号：V1.0
源程序总行数：7311 行
本文档节选：前 30 页 + 后 30 页，每页 50 行

---

<!-- 第 1 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | # ===== 文件：backend/app/main.py =====
  2 | """
  3 | FastAPI 应用入口模块。
  4 | 
  5 | 模块功能：创建 FastAPI 应用，装配日志、CORS、REST 路由、WebSocket 通道，
  6 | 并托管前端构建产物（dist），实现单容器部署。启动方式：
  7 | uvicorn app.main:app --host 0.0.0.0 --port 8000
  8 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
  9 | 日期：2026-10-24
 10 | 版本：V1.0
 11 | """
 12 | 
 13 | import asyncio
 14 | import logging
 15 | import os
 16 | from contextlib import asynccontextmanager
 17 | from pathlib import Path
 18 | 
 19 | from fastapi import FastAPI
 20 | from fastapi.middleware.cors import CORSMiddleware
 21 | from fastapi.responses import FileResponse
 22 | from fastapi.staticfiles import StaticFiles
 23 | 
 24 | from app.api.rest import create_rest_router
 25 | from app.api.websocket import create_ws_router
 26 | from app.core.config import settings
 27 | from app.services.simulation_engine import SimulationEngine
 28 | 
 29 | # ---------- 日志配置（要求：系统各环节均留日志） ----------
 30 | 
 31 | LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
 32 | LOG_FILE = os.getenv("LOG_FILE", "logs/simulation.log")
 33 | 
 34 | def setup_logging() -> None:
 35 |     """配置根日志：同时输出到控制台与滚动日志文件。"""
 36 |     log_dir = Path(LOG_FILE).parent
 37 |     log_dir.mkdir(parents=True, exist_ok=True)
 38 |     formatter = logging.Formatter(
 39 |         "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
 40 |     )
 41 |     console_handler = logging.StreamHandler()
 42 |     console_handler.setFormatter(formatter)
 43 |     file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
 44 |     file_handler.setFormatter(formatter)
 45 |     root = logging.getLogger()
 46 |     root.setLevel(LOG_LEVEL)
 47 |     root.addHandler(console_handler)
 48 |     root.addHandler(file_handler)
 49 |     # 降低 uvicorn 内部访问日志噪音，保留启动信息。
 50 |     logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

第 1 页 / 共 60 页

---

<!-- 第 2 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 | setup_logging()
  3 | logger = logging.getLogger("app.main")
  4 | 
  5 | async def _run_simulation_loop() -> None:
  6 |     """仿真主循环：独立于 WebSocket 连接，按 tick 间隔推进引擎。"""
  7 |     while True:
  8 |         await asyncio.sleep(settings.tick_interval_ms / 1000)
  9 |         engine.tick()
 10 | 
 11 | @asynccontextmanager
 12 | async def lifespan(app_instance: FastAPI):
 13 |     """应用生命周期钩子：启动/关闭时记录关键配置，便于运维排查。"""
 14 |     logger.info(
 15 |         "仿真系统启动：tick=%dms, 低电量阈值=%.0f%%, 过热阈值=%.0f℃",
 16 |         settings.tick_interval_ms,
 17 |         settings.low_battery_threshold,
 18 |         settings.overheat_threshold,
 19 |     )
 20 |     tick_task = asyncio.create_task(_run_simulation_loop())
 21 |     try:
 22 |         yield
 23 |     finally:
 24 |         tick_task.cancel()
 25 |         logger.info("仿真系统已关闭")
 26 | 
 27 | # ---------- 应用装配 ----------
 28 | 
 29 | app = FastAPI(
 30 |     title="智能巡检机器人二维仿真系统",
 31 |     description="基于 FastAPI 的二维栅格机器人仿真后端：A* 寻路、虚拟传感器、规则异常检测",
 32 |     version="V1.0",
 33 |     lifespan=lifespan,
 34 | )
 35 | 
 36 | # CORS：允许本地前端开发服务器跨域联调。
 37 | app.add_middleware(
 38 |     CORSMiddleware,
 39 |     allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(","),
 40 |     allow_credentials=True,
 41 |     allow_methods=["*"],
 42 |     allow_headers=["*"],
 43 | )
 44 | 
 45 | # 全局唯一仿真引擎。
 46 | engine = SimulationEngine()
 47 | 
 48 | # 挂载 REST 与 WebSocket 路由。
 49 | app.include_router(create_rest_router(engine))
 50 | app.include_router(create_ws_router(engine, settings.tick_interval_ms))
```

第 2 页 / 共 60 页

---

<!-- 第 3 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 | @app.get("/api/v1/health", summary="健康检查")
  3 | async def health() -> dict:
  4 |     """容器/负载均衡健康探针。"""
  5 |     return {"status": "ok", "version": "V1.0"}
  6 | 
  7 | # ---------- 前端静态资源托管（单容器部署） ----------
  8 | 
  9 | DIST_DIR = Path(os.getenv("DIST_DIR", "static/dist"))
 10 | 
 11 | if DIST_DIR.exists():
 12 |     app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")
 13 | 
 14 |     @app.get("/{full_path:path}", include_in_schema=False)
 15 |     async def serve_spa(full_path: str) -> FileResponse:
 16 |         """
 17 |         前端单页应用回退路由：非 API 请求一律返回 index.html。
 18 | 
 19 |         :param full_path: 请求的相对路径。
 20 |         :return: 静态文件或 index.html。
 21 |         """
 22 |         candidate = DIST_DIR / full_path
 23 |         if full_path and candidate.is_file():
 24 |             return FileResponse(candidate)
 25 |         return FileResponse(DIST_DIR / "index.html")
 26 | 
 27 |     logger.info("前端静态资源托管已启用: %s", DIST_DIR)
 28 | else:
 29 |     logger.warning("未找到前端构建目录 %s，仅提供 API 服务", DIST_DIR)
 30 | # ===== 文件：backend/app/core/config.py =====
 31 | """
 32 | 配置模块。
 33 | 
 34 | 模块功能：集中管理应用运行所需的可配置参数（仿真步长、电池消耗、
 35 | 传感器量程、温度阈值等）。所有配置项均通过环境变量提供默认值，
 36 | 禁止在代码中硬编码密钥或内网地址。
 37 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 38 | 日期：2026-10-24
 39 | 版本：V1.0
 40 | """
 41 | 
 42 | import os
 43 | from dataclasses import dataclass
 44 | 
 45 | @dataclass
 46 | class Settings:
 47 |     """应用全局配置。"""
 48 | 
 49 |     # 仿真循环推送间隔（毫秒），与公共契约保持一致。
 50 |     tick_interval_ms: int = int(os.getenv("TICK_INTERVAL_MS", "200"))
```

第 3 页 / 共 60 页

---

<!-- 第 4 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 |     # 电池消耗：移动一格消耗百分比 / 静止每个 tick 消耗百分比。
  3 |     battery_move_cost: float = float(os.getenv("BATTERY_MOVE_COST", "0.2"))
  4 |     battery_idle_cost: float = float(os.getenv("BATTERY_IDLE_COST", "0.02"))
  5 | 
  6 |     # 低电量告警阈值（百分比），低于该值自动返航充电。
  7 |     low_battery_threshold: float = float(os.getenv("LOW_BATTERY_THRESHOLD", "20.0"))
  8 | 
  9 |     # 充电每 tick 恢复的电量百分比。
 10 |     charge_rate: float = float(os.getenv("CHARGE_RATE", "1.0"))
 11 | 
 12 |     # 传感器：每格代表的真实距离（米）与最大量程（米）。
 13 |     cell_distance_m: float = float(os.getenv("CELL_DISTANCE_M", "0.5"))
 14 |     sensor_range_m: float = float(os.getenv("SENSOR_RANGE_M", "5.0"))
 15 | 
 16 |     # 温度基线（摄氏度）与运动温升、噪声幅度。
 17 |     base_temperature: float = float(os.getenv("BASE_TEMPERATURE", "35.0"))
 18 |     temperature_rise_per_move: float = float(os.getenv("TEMP_RISE_PER_MOVE", "0.05"))
 19 |     temperature_noise: float = float(os.getenv("TEMPERATURE_NOISE", "0.5"))
 20 | 
 21 |     # 过热告警阈值（摄氏度）。
 22 |     overheat_threshold: float = float(os.getenv("OVERHEAT_THRESHOLD", "60.0"))
 23 | 
 24 |     # 传感器突变判定阈值（米），相邻读数变化超过该值视为故障。
 25 |     sensor_fault_delta: float = float(os.getenv("SENSOR_FAULT_DELTA", "3.0"))
 26 | 
 27 |     # 异常检测策略：rule（默认，规则基线）/ ml（IsolationForest 在线检测）。
 28 |     anomaly_strategy: str = os.getenv("ANOMALY_STRATEGY", "rule")
 29 | 
 30 |     # 传感器故障注入概率（0 = 关闭）。开启后每 tick 以该概率制造离群/卡死读数。
 31 |     sensor_fault_prob: float = float(os.getenv("SENSOR_FAULT_PROB", "0.0"))
 32 | 
 33 |     # IsolationForest 在线检测参数。
 34 |     ml_coldstart_ticks: int = int(os.getenv("ML_COLDSTART_TICKS", "500"))
 35 |     ml_window_size: int = int(os.getenv("ML_WINDOW_SIZE", "120"))
 36 |     ml_retrain_seconds: int = int(os.getenv("ML_RETRAIN_SECONDS", "60"))
 37 |     # 阈值校准：默认取正常段分数的低分位（百分数），把误报率压到该水平；
 38 |     # 也可用 ML_SCORE_THRESHOLD 指定固定分数阈值覆盖自动校准。
 39 |     ml_score_percentile: float = float(os.getenv("ML_SCORE_PERCENTILE", "2.0"))
 40 |     ml_score_threshold: str = os.getenv("ML_SCORE_THRESHOLD", "")
 41 |     # 污染率：'auto' 或 0–0.5 之间的浮点数。
 42 |     ml_contamination: str = os.getenv("ML_CONTAMINATION", "auto")
 43 | 
 44 |     # 默认地图尺寸与初始充电点。
 45 |     default_width: int = int(os.getenv("DEFAULT_WIDTH", "16"))
 46 |     default_height: int = int(os.getenv("DEFAULT_HEIGHT", "12"))
 47 |     default_start: tuple = (0, 0)
 48 |     default_charge_point: tuple = (0, 0)
 49 | 
 50 | # 全局唯一配置实例，供各模块直接引用。
```

第 4 页 / 共 60 页

---

<!-- 第 5 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | settings = Settings()
  2 | # ===== 文件：backend/app/core/constants.py =====
  3 | """
  4 | 常量模块。
  5 | 
  6 | 模块功能：定义地图格子语义、机器人运行模式、异常类型等枚举常量，
  7 | 供仿真引擎、接口层统一引用，避免魔法字符串散落各处。
  8 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
  9 | 日期：2026-10-24
 10 | 版本：V1.0
 11 | """
 12 | 
 13 | # 地图格子取值：0 = 可通行，1 = 障碍物。
 14 | CELL_FREE = 0
 15 | CELL_OBSTACLE = 1
 16 | 
 17 | # 机器人运行模式。
 18 | MODE_MANUAL = "manual"      # 手动控制
 19 | MODE_PATROL = "patrol"      # 自动巡检
 20 | MODE_CHARGING = "charging"  # 充电返航
 21 | MODE_BLOCKED = "blocked"    # 碰撞受阻
 22 | 
 23 | # 异常类型。
 24 | ANOMALY_LOW_BATTERY = "low_battery"      # 低电量
 25 | ANOMALY_OBSTACLE = "obstacle"            # 障碍物/寻路失败
 26 | ANOMALY_SENSOR_FAULT = "sensor_fault"    # 传感器故障
 27 | ANOMALY_OVERHEAT = "overheat"            # 过热
 28 | ANOMALY_ML = "ml_anomaly"                # 机器学习综合工况异常
 29 | 
 30 | # 四邻域移动方向（dx, dy），保持与前端坐标约定一致。
 31 | DIRECTION_DELTAS = {
 32 |     "up": (0, -1),
 33 |     "down": (0, 1),
 34 |     "left": (-1, 0),
 35 |     "right": (1, 0),
 36 | }
 37 | # ===== 文件：backend/app/models/map.py =====
 38 | """
 39 | 地图数据模型模块。
 40 | 
 41 | 模块功能：定义二维栅格地图的 Pydantic 数据模型。地图由二维数组 grid
 42 | 表示（0 = 可通行，1 = 障碍物），并包含起点、巡检点集合与充电点。
 43 | 所有字段命名严格遵循项目公共接口契约，不得改动。
 44 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 45 | 日期：2026-10-24
 46 | 版本：V1.0
 47 | """
 48 | 
 49 | from pydantic import BaseModel, Field, field_validator
 50 | 
```

第 5 页 / 共 60 页

---

<!-- 第 6 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | class GridMap(BaseModel):
  2 |     """二维栅格地图模型。"""
  3 | 
  4 |     width: int = Field(..., description="地图宽度（列数）", ge=1)
  5 |     height: int = Field(..., description="地图高度（行数）", ge=1)
  6 |     grid: list[list[int]] = Field(..., description="二维栅格数组，0=通行 1=障碍")
  7 |     start: tuple[int, int] = Field(..., description="机器人初始起点坐标 (x, y)")
  8 |     goals: list[tuple[int, int]] = Field(default_factory=list, description="巡检点集合")
  9 |     charge_point: tuple[int, int] = Field(..., description="充电点坐标 (x, y)")
 10 | 
 11 |     @field_validator("grid")
 12 |     @classmethod
 13 |     def validate_grid(cls, value: list[list[int]]) -> list[list[int]]:
 14 |         """
 15 |         校验栅格数组维度与取值合法性。
 16 | 
 17 |         :param value: 待校验的二维数组。
 18 |         :return: 校验通过的二维数组。
 19 |         :raises ValueError: 当行长度不一致或取值非 0/1 时抛出。
 20 |         """
 21 |         if not value:
 22 |             raise ValueError("栅格数组不能为空")
 23 |         row_len = len(value[0])
 24 |         for row in value:
 25 |             if len(row) != row_len:
 26 |                 raise ValueError("栅格数组各行长度必须一致")
 27 |             for cell in row:
 28 |                 if cell not in (0, 1):
 29 |                     raise ValueError("栅格取值只能为 0 或 1")
 30 |         return value
 31 | 
 32 |     def in_bounds(self, x: int, y: int) -> bool:
 33 |         """
 34 |         判断坐标是否越界。
 35 | 
 36 |         :param x: 列坐标。
 37 |         :param y: 行坐标。
 38 |         :return: 在地图范围内返回 True，否则 False。
 39 |         """
 40 |         return 0 <= x < self.width and 0 <= y < self.height
 41 | 
 42 |     def is_free(self, x: int, y: int) -> bool:
 43 |         """
 44 |         判断格子是否可通行。
 45 | 
 46 |         :param x: 列坐标。
 47 |         :param y: 行坐标。
 48 |         :return: 可通行返回 True，障碍或越界返回 False。
 49 |         """
 50 |         return self.in_bounds(x, y) and self.grid[y][x] == 0
```

第 6 页 / 共 60 页

---

<!-- 第 7 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | # ===== 文件：backend/app/models/robot.py =====
  2 | """
  3 | 机器人与传感器数据模型模块。
  4 | 
  5 | 模块功能：定义机器人状态帧、传感器读数、手动移动指令、巡检控制指令
  6 | 等 Pydantic 模型。字段命名与公共接口契约及 WebSocket 协议逐字段一致。
  7 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
  8 | 日期：2026-10-24
  9 | 版本：V1.0
 10 | """
 11 | 
 12 | from typing import Optional
 13 | 
 14 | from pydantic import BaseModel, Field
 15 | 
 16 | class Sensors(BaseModel):
 17 |     """三向测距传感器与温度传感器读数。"""
 18 | 
 19 |     front: Optional[float] = Field(None, description="正前方测距（米），超量程为 null")
 20 |     left: Optional[float] = Field(None, description="左侧测距（米），超量程为 null")
 21 |     right: Optional[float] = Field(None, description="右侧测距（米），超量程为 null")
 22 |     temperature: float = Field(..., description="机身温度（摄氏度）")
 23 | 
 24 | class RobotState(BaseModel):
 25 |     """机器人状态帧，对应 WebSocket state 帧的 data 字段。"""
 26 | 
 27 |     x: int = Field(..., description="机器人所在列坐标")
 28 |     y: int = Field(..., description="机器人所在行坐标")
 29 |     theta: float = Field(..., description="机器人朝向角（弧度）")
 30 |     battery: float = Field(..., description="剩余电量百分比")
 31 |     speed: float = Field(..., description="当前速度（格/step）")
 32 |     mode: str = Field(..., description="运行模式 manual|patrol|charging|blocked")
 33 |     path: list[list[int]] = Field(default_factory=list, description="当前规划路径")
 34 |     sensors: Sensors = Field(..., description="传感器读数")
 35 | 
 36 | class MoveCommand(BaseModel):
 37 |     """手动移动指令。"""
 38 | 
 39 |     dx: int = Field(..., description="水平方向步长 -1/0/1", ge=-1, le=1)
 40 |     dy: int = Field(..., description="垂直方向步长 -1/0/1", ge=-1, le=1)
 41 | 
 42 | class PatrolStartCommand(BaseModel):
 43 |     """开始自动巡检指令，goals 缺省时使用地图巡检点。"""
 44 | 
 45 |     goals: Optional[list[tuple[int, int]]] = Field(None, description="巡检点列表")
 46 | # ===== 文件：backend/app/models/events.py =====
 47 | """
 48 | 事件数据模型模块。
 49 | 
 50 | 模块功能：定义异常事件、巡检状态、WebSocket 推送帧等模型。事件字段
```

第 7 页 / 共 60 页

---

<!-- 第 8 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 与公共契约的 anomaly 帧、notice 帧逐字段一致。
  2 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
  3 | 日期：2026-10-24
  4 | 版本：V1.0
  5 | """
  6 | 
  7 | from typing import Optional
  8 | 
  9 | from pydantic import BaseModel, Field
 10 | 
 11 | class AnomalyEvent(BaseModel):
 12 |     """异常事件模型，对应 anomaly 帧的 data 字段。"""
 13 | 
 14 |     time: str = Field(..., description="事件时间（ISO 8601 字符串）")
 15 |     type: str = Field(..., description="异常类型 low_battery|obstacle|sensor_fault|overheat")
 16 |     message: str = Field(..., description="异常描述信息")
 17 |     position: list[int] = Field(..., description="发生位置 [x, y]")
 18 | 
 19 | class PatrolStatus(BaseModel):
 20 |     """巡检状态模型。"""
 21 | 
 22 |     running: bool = Field(..., description="巡检是否在运行")
 23 |     current_goal: Optional[list[int]] = Field(None, description="当前目标巡检点")
 24 |     progress: float = Field(..., description="巡检完成进度 0~1")
 25 |     path_remain: int = Field(..., description="当前段剩余路径长度")
 26 | 
 27 | class StateFrame(BaseModel):
 28 |     """WebSocket state 推送帧。"""
 29 | 
 30 |     type: str = "state"
 31 |     data: dict = Field(..., description="RobotState 序列化后的字典")
 32 | 
 33 | class AnomalyFrame(BaseModel):
 34 |     """WebSocket anomaly 推送帧。"""
 35 | 
 36 |     type: str = "anomaly"
 37 |     data: AnomalyEvent
 38 | 
 39 | class NoticeFrame(BaseModel):
 40 |     """WebSocket notice 推送帧。"""
 41 | 
 42 |     type: str = "notice"
 43 |     data: dict = Field(..., description="{'message': '...'}")
 44 | # ===== 文件：backend/app/algorithms/astar.py =====
 45 | """
 46 | A* 路径规划算法模块（Python 实现）。
 47 | 
 48 | 模块功能：在二维栅格地图上，使用 A* 算法从起点搜索到目标点的最短
 49 | 无障碍路径。采用曼哈顿距离作为启发函数，四邻域移动，避免对角穿墙。
 50 | 函数签名与返回结构与前端临时实现（src/services/astar.js）保持一致，
```

第 8 页 / 共 60 页

---

<!-- 第 9 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 便于下一阶段平滑迁移、前后端互验。
  2 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
  3 | 日期：2026-10-24
  4 | 版本：V1.0
  5 | """
  6 | 
  7 | import heapq
  8 | 
  9 | # 四邻域移动方向（dx, dy）。禁止对角移动，避免“斜穿障碍缝隙”的几何问题。
 10 | _NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
 11 | 
 12 | def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
 13 |     """
 14 |     曼哈顿距离启发函数。
 15 | 
 16 |     :param a: 起点坐标 (x, y)。
 17 |     :param b: 目标坐标 (x, y)。
 18 |     :return: 两坐标的曼哈顿距离。
 19 |     """
 20 |     return abs(a[0] - b[0]) + abs(a[1] - b[1])
 21 | 
 22 | def _reconstruct_path(
 23 |     came_from: dict,
 24 |     current: tuple[int, int],
 25 |     start: tuple[int, int],
 26 | ) -> list[list[int]]:
 27 |     """
 28 |     从搜索结果回溯出完整路径。
 29 | 
 30 |     :param came_from: 节点前驱映射表。
 31 |     :param current: 终点坐标。
 32 |     :param start: 起点坐标。
 33 |     :return: 从起点到终点的坐标列表 [[x, y], ...]。
 34 |     """
 35 |     path = [list(current)]
 36 |     while current in came_from:
 37 |         current = came_from[current]
 38 |         path.append(list(current))
 39 |     path.reverse()  # 回溯得到的是终点→起点，反转成起点→终点。
 40 |     return path
 41 | 
 42 | def astar(
 43 |     grid: list[list[int]],
 44 |     start: tuple[int, int],
 45 |     goal: tuple[int, int],
 46 | ) -> dict:
 47 |     """
 48 |     A* 路径搜索主函数。
 49 | 
 50 |     参数与返回结构刻意与前端 astar.js 保持一致：
```

第 9 页 / 共 60 页

---

<!-- 第 10 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     返回 {path: [[x,y],...], visited_count: int, cost: int}。
  2 | 
  3 |     :param grid: 二维栅格数组，0=可通行，1=障碍物。
  4 |     :param start: 起点坐标 (x, y)。
  5 |     :param goal: 目标坐标 (x, y)。
  6 |     :return: 包含路径、访问节点数与路径代价的字典。
  7 |     """
  8 |     height = len(grid)
  9 |     if height == 0:
 10 |         return {"path": [], "visited_count": 0, "cost": 0}
 11 |     width = len(grid[0])
 12 | 
 13 |     # 边界与障碍校验：起点、终点必须可通行。
 14 |     def is_free(x: int, y: int) -> bool:
 15 |         return 0 <= x < width and 0 <= y < height and grid[y][x] == 0
 16 | 
 17 |     if not is_free(*start) or not is_free(*goal):
 18 |         return {"path": [], "visited_count": 0, "cost": 0}
 19 | 
 20 |     # open_set 用最小堆维护 (f_score, 计数, 节点)，计数用于稳定排序避免 tie-breaking 报错。
 21 |     open_heap: list = []
 22 |     counter = 0
 23 |     heapq.heappush(open_heap, (0, counter, start))
 24 | 
 25 |     came_from: dict = {}
 26 |     g_score: dict = {start: 0}
 27 |     visited_count = 0
 28 | 
 29 |     while open_heap:
 30 |         _f, _c, current = heapq.heappop(open_heap)
 31 |         visited_count += 1
 32 | 
 33 |         # 到达目标，回溯路径。
 34 |         if current == goal:
 35 |             return {
 36 |                 "path": _reconstruct_path(came_from, current, start),
 37 |                 "visited_count": visited_count,
 38 |                 "cost": g_score[current],
 39 |             }
 40 | 
 41 |         for dx, dy in _NEIGHBORS:
 42 |             neighbor = (current[0] + dx, current[1] + dy)
 43 |             if not is_free(*neighbor):
 44 |                 continue
 45 |             tentative_g = g_score[current] + 1
 46 |             if neighbor not in g_score or tentative_g < g_score[neighbor]:
 47 |                 came_from[neighbor] = current
 48 |                 g_score[neighbor] = tentative_g
 49 |                 f_score = tentative_g + _manhattan(neighbor, goal)
 50 |                 counter += 1
```

第 10 页 / 共 60 页

---

<!-- 第 11 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |                 heapq.heappush(open_heap, (f_score, counter, neighbor))
  2 | 
  3 |     # 堆耗尽仍未到达目标，说明目标不可达。
  4 |     return {"path": [], "visited_count": visited_count, "cost": 0}
  5 | # ===== 文件：backend/app/services/simulation_engine.py =====
  6 | """
  7 | 仿真引擎模块。
  8 | 
  9 | 模块功能：系统核心。持有地图与机器人状态，按固定周期（默认 200ms）
 10 | 推进仿真：电量消耗、巡检路径跟随、传感器刷新、规则异常检测。对外提供
 11 | 与 REST/WebSocket 契约一致的操作方法，并通过回调把 state/anomaly 帧
 12 | 推送给接口层。业务规则与前端 SimulatedService 逐条对应。
 13 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 14 | 日期：2026-10-24
 15 | 版本：V1.0
 16 | """
 17 | 
 18 | import logging
 19 | import math
 20 | from datetime import datetime, timezone
 21 | 
 22 | from app.algorithms.astar import astar
 23 | from app.core import config
 24 | from app.core.constants import (
 25 |     ANOMALY_OBSTACLE,
 26 |     CELL_OBSTACLE,
 27 |     MODE_BLOCKED,
 28 |     MODE_CHARGING,
 29 |     MODE_MANUAL,
 30 |     MODE_PATROL,
 31 | )
 32 | from app.models.map import GridMap
 33 | from app.services.anomaly import create_detector
 34 | from app.services.patrol import PatrolManager, find_min_obstacle_to_remove, order_goals_by_nearest
 35 | from app.services.sensors import SensorSimulator
 36 | 
 37 | logger = logging.getLogger("simulation.engine")
 38 | 
 39 | def _default_map(width: int, height: int) -> GridMap:
 40 |     """
 41 |     生成默认地图：空旷场地 + 少量固定障碍，用于开箱即用的演示。
 42 | 
 43 |     :param width: 地图宽度。
 44 |     :param height: 地图高度。
 45 |     :return: GridMap 实例。
 46 |     """
 47 |     grid = [[0] * width for _ in range(height)]
 48 |     # 预置几段障碍墙体，保证默认地图就有寻路与避障的演示效果。
 49 |     walls = [
 50 |         (3, 2), (3, 3), (3, 4),
```

第 11 页 / 共 60 页

---

<!-- 第 12 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         (8, 5), (9, 5), (10, 5), (11, 5),
  2 |         (5, 8), (6, 8), (7, 8), (8, 8),
  3 |         (12, 2), (12, 3), (13, 7),
  4 |     ]
  5 |     for x, y in walls:
  6 |         if 0 <= x < width and 0 <= y < height:
  7 |             grid[y][x] = CELL_OBSTACLE
  8 |     return GridMap(
  9 |         width=width,
 10 |         height=height,
 11 |         grid=grid,
 12 |         start=(0, 0),
 13 |         goals=[[width - 1, height - 1], [width // 2, height // 2]],
 14 |         charge_point=(0, 0),
 15 |     )
 16 | 
 17 | class SimulationEngine:
 18 |     """机器人二维仿真引擎（单例，由应用生命周期持有）。"""
 19 | 
 20 |     def __init__(self) -> None:
 21 |         """初始化引擎：默认地图、初始状态、各服务组件。"""
 22 |         self.map = _default_map(config.settings.default_width, config.settings.default_height)
 23 |         self.sensor_sim = SensorSimulator(self.map.grid)
 24 |         self.anomaly_detector = create_detector()
 25 |         self.patrol = PatrolManager()
 26 | 
 27 |         # 机器人运动状态。
 28 |         self.x, self.y = self.map.start
 29 |         self.theta = 0.0
 30 |         self.battery = 100.0
 31 |         self.speed = 1.0
 32 |         self.mode = MODE_MANUAL
 33 |         self.path: list[list[int]] = []
 34 |         self.visited_trail: list[list[int]] = [[self.x, self.y]]
 35 | 
 36 |         # 传感器最新读数缓存。
 37 |         self.sensors: dict = {
 38 |             "front": None,
 39 |             "left": None,
 40 |             "right": None,
 41 |             "temperature": config.settings.base_temperature,
 42 |         }
 43 |         # 事件回调集合（WebSocket 广播器注册进来）。
 44 |         self._event_listeners: list = []
 45 |         logger.info("仿真引擎初始化完成：地图 %dx%d，起点 %s", self.map.width, self.map.height, self.map.start)
 46 | 
 47 |     # ---------- 事件推送 ----------
 48 | 
 49 |     def add_event_listener(self, callback) -> None:
 50 |         """
```

第 12 页 / 共 60 页

---

<!-- 第 13 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         注册事件监听器（接口层的 WebSocket 广播函数）。
  2 | 
  3 |         :param callback: 接收帧字典的回调函数。
  4 |         """
  5 |         self._event_listeners.append(callback)
  6 | 
  7 |     def _emit(self, frame: dict) -> None:
  8 |         """
  9 |         向所有监听器广播一帧数据。
 10 | 
 11 |         :param frame: 与 WebSocket 协议一致的帧字典。
 12 |         """
 13 |         for callback in self._event_listeners:
 14 |             try:
 15 |                 callback(frame)
 16 |             except Exception:  # noqa: BLE001 - 单个客户端异常不能影响仿真循环。
 17 |                 logger.exception("事件监听器执行失败")
 18 | 
 19 |     def _emit_anomaly(self, event: dict) -> None:
 20 |         """广播异常事件帧并写入日志。"""
 21 |         logger.warning("异常事件: %s - %s @ %s", event["type"], event["message"], event["position"])
 22 |         self._emit({"type": "anomaly", "data": event})
 23 | 
 24 |     def _emit_notice(self, message: str) -> None:
 25 |         """广播通知帧并写入日志。"""
 26 |         logger.info("通知: %s", message)
 27 |         self._emit({"type": "notice", "data": {"message": message}})
 28 | 
 29 |     # ---------- 地图 ----------
 30 | 
 31 |     def get_map(self) -> dict:
 32 |         """
 33 |         获取当前地图（REST GET /map 响应体）。
 34 | 
 35 |         :return: 与契约字段一致的地图字典。
 36 |         """
 37 |         return self.map.model_dump()
 38 | 
 39 |     def update_map(self, new_map: GridMap | dict) -> dict:
 40 |         """
 41 |         更新地图（REST PUT /map 请求体）。
 42 | 
 43 |         机器人位置非法时自动回退到起点。
 44 | 
 45 |         :param new_map: 新地图模型或可校验的字典。
 46 |         :return: 保存后的地图字典。
 47 |         """
 48 |         if isinstance(new_map, dict):
 49 |             new_map = GridMap.model_validate(new_map)
 50 |         self.map = new_map
```

第 13 页 / 共 60 页

---

<!-- 第 14 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         self.sensor_sim.set_grid(new_map.grid)
  2 |         if not new_map.is_free(self.x, self.y):
  3 |             logger.warning("机器人当前位置 (%d, %d) 变为障碍，回退起点", self.x, self.y)
  4 |             self.x, self.y = new_map.start
  5 |             self.visited_trail.append([self.x, self.y])
  6 |         logger.info("地图已更新: %dx%d", new_map.width, new_map.height)
  7 |         return self.map.model_dump()
  8 | 
  9 |     # ---------- 手动控制 ----------
 10 | 
 11 |     def move(self, dx: int, dy: int) -> dict:
 12 |         """
 13 |         手动单步移动（REST POST /robot/move）。
 14 | 
 15 |         碰撞障碍或越界时不动并将 mode 置为 blocked。
 16 | 
 17 |         :param dx: 水平步长 -1/0/1。
 18 |         :param dy: 垂直步长 -1/0/1。
 19 |         :return: 移动后的状态字典。
 20 |         """
 21 |         if dx == 0 and dy == 0:
 22 |             return self.state_dict()["data"]
 23 |         target = (self.x + dx, self.y + dy)
 24 |         if self.map.is_free(*target):
 25 |             self.x, self.y = target
 26 |             self.theta = math.atan2(dy, dx)
 27 |             self.visited_trail.append([self.x, self.y])
 28 |             # 移动一格即时扣除电量（与契约一致：移动 0.2%/格）。
 29 |             self.battery = max(0.0, self.battery - config.settings.battery_move_cost)
 30 |             if self.mode not in (MODE_PATROL, MODE_CHARGING):
 31 |                 self.mode = MODE_MANUAL
 32 |             logger.debug("移动到 (%d, %d)", self.x, self.y)
 33 |         else:
 34 |             self.mode = MODE_BLOCKED
 35 |             logger.info("移动被阻挡于 (%d, %d)", *target)
 36 |         return self.state_dict()["data"]
 37 | 
 38 |     def reset(self) -> None:
 39 |         """复位机器人到起点并停止巡检（REST POST /robot/reset）。"""
 40 |         self.patrol.stop()
 41 |         self.x, self.y = self.map.start
 42 |         self.theta = 0.0
 43 |         self.battery = 100.0
 44 |         self.mode = MODE_MANUAL
 45 |         self.path = []
 46 |         self.visited_trail = [[self.x, self.y]]
 47 |         logger.info("机器人已复位到起点 %s", self.map.start)
 48 |         self._emit_notice("机器人已复位到起点")
 49 | 
 50 |     # ---------- 路径规划 ----------
```

第 14 页 / 共 60 页

---

<!-- 第 15 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 |     def compute_path(self, start: list[int], goal: list[int]) -> dict:
  3 |         """
  4 |         A* 调试接口（REST GET /path）。
  5 | 
  6 |         :param start: 起点坐标 [x, y]。
  7 |         :param goal: 目标坐标 [x, y]。
  8 |         :return: {'path', 'visited_count', 'cost'} 与前端 astar.js 一致。
  9 |         """
 10 |         result = astar(self.map.grid, tuple(start), tuple(goal))
 11 |         logger.info("寻路 %s -> %s：路径长 %d，访问 %d 节点", start, goal, len(result["path"]), result["visited_count"])
 12 |         return result
 13 | 
 14 |     def find_min_obstacle(self, goal: list[int]) -> dict:
 15 |         """
 16 |         一键排障：寻找使目标可达的最小代价障碍格（配合前端功能 11）。
 17 | 
 18 |         :param goal: 目标巡检点坐标 [x, y]。
 19 |         :return: {'remove': [x, y] | None, 'message': str}
 20 |         """
 21 |         cell = find_min_obstacle_to_remove(self.map.grid, (self.x, self.y), tuple(goal))
 22 |         if cell is None:
 23 |             logger.info("一键排障：无单格拆除方案可使 %s 可达", goal)
 24 |             return {"remove": None, "message": "拆除单个障碍无法到达目标"}
 25 |         logger.info("一键排障：建议拆除障碍 %s", cell)
 26 |         return {"remove": list(cell), "message": f"建议拆除障碍 [{cell[0]}, {cell[1]}]"}
 27 | 
 28 |     def remove_obstacle(self, cell: list[int]) -> dict:
 29 |         """
 30 |         拆除指定障碍格并重算当前巡检路径。
 31 | 
 32 |         :param cell: 障碍坐标 [x, y]。
 33 |         :return: 更新后的地图字典。
 34 |         """
 35 |         cell_x, cell_y = cell
 36 |         if self.map.in_bounds(cell_x, cell_y):
 37 |             self.map.grid[cell_y][cell_x] = 0
 38 |             logger.info("障碍 (%d, %d) 已拆除", cell_x, cell_y)
 39 |         return self.map.model_dump()
 40 | 
 41 |     def resolve_fault(self) -> dict:
 42 |         """
 43 |         一键排障：机器人被障碍卡住（mode=blocked）时，清除正前方障碍格
 44 |         并恢复正常控制；无阻塞时仅返回提示。正前方朝向由 theta 近似为
 45 |         四方向步长（与前端 SimulatedService._thetaToDirection 一致）。
 46 | 
 47 |         :return: 通知帧 {'type': 'notice', 'data': {'message': str}}。
 48 |         """
 49 |         if self.mode != MODE_BLOCKED:
 50 |             message = "当前无阻塞故障，无需排障"
```

第 15 页 / 共 60 页

---

<!-- 第 16 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |             logger.info("一键排障：%s", message)
  2 |             self._emit_notice(message)
  3 |             return {"type": "notice", "data": {"message": message}}
  4 | 
  5 |         dx, dy = self._theta_to_step(self.theta)
  6 |         target = (self.x + dx, self.y + dy)
  7 |         if self.map.in_bounds(*target) and self.map.grid[target[1]][target[0]] == CELL_OBSTACLE:
  8 |             self.map.grid[target[1]][target[0]] = 0
  9 |             logger.info("一键排障：拆除前方障碍 (%d, %d)", *target)
 10 |         self.mode = MODE_MANUAL
 11 |         self.path = []
 12 |         message = "已排除前方障碍，恢复正常控制"
 13 |         self._emit_notice(message)
 14 |         return {"type": "notice", "data": {"message": message}}
 15 | 
 16 |     @staticmethod
 17 |     def _theta_to_step(theta: float) -> tuple[int, int]:
 18 |         """
 19 |         把朝向角近似为四方向步长。
 20 | 
 21 |         :param theta: 朝向角（弧度）。
 22 |         :return: (dx, dy) 单位步长。
 23 |         """
 24 |         normalized = (theta % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
 25 |         half = math.pi / 4
 26 |         if normalized < half or normalized >= 7 * half:
 27 |             return (1, 0)
 28 |         if normalized < 3 * half:
 29 |             return (0, 1)
 30 |         if normalized < 5 * half:
 31 |             return (-1, 0)
 32 |         return (0, -1)
 33 | 
 34 |     # ---------- 巡检 ----------
 35 | 
 36 |     def start_patrol(self, goals: list[list[int]] | None = None) -> dict:
 37 |         """
 38 |         启动自动巡检（REST POST /patrol/start）。
 39 | 
 40 |         goals 缺省时使用地图巡检点；先最近邻贪心排序，再逐段 A*。
 41 | 
 42 |         :param goals: 巡检点列表（可选）。
 43 |         :return: 与契约一致的巡检状态字典。
 44 |         """
 45 |         goal_list = [tuple(g) for g in (goals if goals else self.map.goals)]
 46 |         ordered = order_goals_by_nearest((self.x, self.y), goal_list)
 47 |         self.patrol.start(ordered)
 48 |         self.mode = MODE_PATROL
 49 |         self._plan_current_segment()
 50 |         logger.info("巡检启动，共 %d 个巡检点：%s", len(ordered), ordered)
```

第 16 页 / 共 60 页

---

<!-- 第 17 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         self._emit_notice(f"自动巡检已启动，共 {len(ordered)} 个巡检点")
  2 |         return self.patrol.status_dict()
  3 | 
  4 |     def stop_patrol(self) -> dict:
  5 |         """停止巡检（REST POST /patrol/stop）。"""
  6 |         self.patrol.stop()
  7 |         self.mode = MODE_MANUAL
  8 |         self.path = []
  9 |         logger.info("巡检已停止")
 10 |         self._emit_notice("自动巡检已停止")
 11 |         return self.patrol.status_dict()
 12 | 
 13 |     def get_patrol_status(self) -> dict:
 14 |         """获取巡检状态（REST GET /patrol/status）。"""
 15 |         return self.patrol.status_dict()
 16 | 
 17 |     def _plan_current_segment(self) -> None:
 18 |         """为当前巡检点规划路径；不可达时告警并跳过。"""
 19 |         goal = self.patrol.current_goal()
 20 |         if goal is None:
 21 |             return
 22 |         result = astar(self.map.grid, (self.x, self.y), goal)
 23 |         if result["path"]:
 24 |             self.path = result["path"]
 25 |             self.patrol.path_remain = max(0, len(result["path"]) - 1)
 26 |         else:
 27 |             self._emit_anomaly(
 28 |                 {
 29 |                     "time": datetime.now(timezone.utc).isoformat(),
 30 |                     "type": ANOMALY_OBSTACLE,
 31 |                     "message": f"无法到达巡检点 [{goal[0]}, {goal[1]}]，已跳过",
 32 |                     "position": [self.x, self.y],
 33 |                 }
 34 |             )
 35 |             self.patrol.advance()
 36 | 
 37 |     # ---------- 传感器与异常 ----------
 38 | 
 39 |     def get_sensors(self) -> dict:
 40 |         """获取最新传感器读数（REST GET /sensors/latest）。"""
 41 |         return dict(self.sensors)
 42 | 
 43 |     def get_anomalies(self) -> list[dict]:
 44 |         """获取历史异常事件（REST GET /events/anomalies）。"""
 45 |         return self.anomaly_detector.get_history()
 46 | 
 47 |     def clear_anomalies(self) -> None:
 48 |         """清空历史异常事件。"""
 49 |         self.anomaly_detector.clear()
 50 |         logger.info("异常事件列表已清空")
```

第 17 页 / 共 60 页

---

<!-- 第 18 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 |     # ---------- 仿真主循环 ----------
  3 | 
  4 |     def state_dict(self) -> dict:
  5 |         """
  6 |         导出与 WebSocket state 帧完全一致的帧字典。
  7 | 
  8 |         :return: {'type': 'state', 'data': {...}}
  9 |         """
 10 |         data = {
 11 |             "x": self.x,
 12 |             "y": self.y,
 13 |             "theta": round(self.theta, 3),
 14 |             "battery": round(self.battery, 1),
 15 |             "speed": self.speed,
 16 |             "mode": self.mode,
 17 |             "path": self.path,
 18 |             "sensors": dict(self.sensors),
 19 |             "patrol": self.patrol.status_dict(),
 20 |         }
 21 |         return {"type": "state", "data": data}
 22 | 
 23 |     def tick(self) -> None:
 24 |         """
 25 |         仿真主循环单步：由后台定时任务每 tick_interval_ms 调用一次。
 26 | 
 27 |         步骤：巡检路径跟随 → 电量消耗 → 传感器刷新 → 异常检测 → 低电量返航。
 28 |         """
 29 |         moving = False
 30 | 
 31 |         # 步骤 1：巡检模式按路径前进。
 32 |         if self.mode == MODE_PATROL and len(self.path) > 1:
 33 |             next_cell = self.path[1]
 34 |             self.x, self.y = next_cell
 35 |             self.theta = math.atan2(next_cell[1] - self.path[0][1], next_cell[0] - self.path[0][0])
 36 |             self.visited_trail.append([self.x, self.y])
 37 |             self.path = self.path[1:]
 38 |             self.patrol.path_remain = max(0, len(self.path) - 1)
 39 |             moving = True
 40 |             # 到达当前巡检点，推进任务。
 41 |             if len(self.path) <= 1:
 42 |                 goal = self.patrol.current_goal()
 43 |                 if goal and (self.x, self.y) == goal:
 44 |                     logger.info("到达巡检点 (%d, %d)，进度 %d/%d", self.x, self.y, self.patrol.completed + 1, len(self.patrol.goals))
 45 |                     self.patrol.advance()
 46 |                     self._plan_current_segment()
 47 |                     if self.patrol.current_goal() is None:
 48 |                         self.mode = MODE_MANUAL
 49 |                         self.patrol.stop()
 50 |                         self._emit_notice("巡检任务全部完成")
```

第 18 页 / 共 60 页

---

<!-- 第 19 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         # 步骤 1b：充电模式沿路径返航。
  2 |         elif self.mode == MODE_CHARGING and len(self.path) > 1:
  3 |             next_cell = self.path[1]
  4 |             self.x, self.y = next_cell
  5 |             self.visited_trail.append([self.x, self.y])
  6 |             self.path = self.path[1:]
  7 |             moving = True
  8 |             if len(self.path) <= 1:
  9 |                 logger.info("已到达充电点，开始充电")
 10 |                 self._emit_notice("已到达充电点，开始充电")
 11 | 
 12 |         # 步骤 2：电量结算（移动/静止/充电三种速率）。
 13 |         if self.mode == MODE_CHARGING and not moving:
 14 |             self.battery = min(100.0, self.battery + config.settings.charge_rate)
 15 |             if self.battery >= 100.0:
 16 |                 self.mode = MODE_MANUAL
 17 |                 self._emit_notice("充电完成，电量 100%")
 18 |         else:
 19 |             cost = config.settings.battery_move_cost if moving else config.settings.battery_idle_cost
 20 |             self.battery = max(0.0, self.battery - cost)
 21 | 
 22 |         # 步骤 3：刷新传感器读数（整合电量/位置，统一喂给异常检测器）。
 23 |         reading = self.sensor_sim.read_all(self.x, self.y, self.theta, self.battery, moving)
 24 |         self.sensors = {
 25 |             "front": reading["front"],
 26 |             "left": reading["left"],
 27 |             "right": reading["right"],
 28 |             "temperature": reading["temperature"],
 29 |         }
 30 |         reading["mode"] = self.mode
 31 | 
 32 |         # 步骤 4：异常检测（规则基线 / 机器学习，按 ANOMALY_STRATEGY 切换）。
 33 |         events = self.anomaly_detector.update(reading)
 34 |         for event in events:
 35 |             self._emit_anomaly(event)
 36 | 
 37 |         # 步骤 5：低电量自动返航（一次性触发）。
 38 |         if (
 39 |             self.battery < config.settings.low_battery_threshold
 40 |             and self.mode not in (MODE_CHARGING,)
 41 |         ):
 42 |             self.mode = MODE_CHARGING
 43 |             charge = tuple(self.map.charge_point)
 44 |             result = astar(self.map.grid, (self.x, self.y), charge)
 45 |             self.path = result["path"]
 46 |             logger.warning("低电量触发自动返航充电")
 47 | 
 48 |     def get_trail(self) -> list[list[int]]:
 49 |         """
 50 |         获取已访问轨迹（供前端绘制与回放）。
```

第 19 页 / 共 60 页

---

<!-- 第 20 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 |         :return: 轨迹坐标列表。
  3 |         """
  4 |         return list(self.visited_trail)
  5 | # ===== 文件：backend/app/services/sensors.py =====
  6 | """
  7 | 虚拟传感器模块。
  8 | 
  9 | 模块功能：在无实体硬件的前提下，基于栅格地图模拟三向测距雷达与温度
 10 | 传感器读数。前/左/右三个方向各发射一条射线，计算到障碍物的距离（米）；
 11 | 温度在基线之上叠加运动温升与高斯噪声。所有逻辑与前端 SimulatedService
 12 | 保持一致，便于前后端行为互验。
 13 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 14 | 日期：2026-10-24
 15 | 版本：V1.0
 16 | """
 17 | 
 18 | import math
 19 | import random
 20 | 
 21 | from app.core import config
 22 | from app.core.constants import CELL_OBSTACLE
 23 | 
 24 | class SensorSimulator:
 25 |     """虚拟传感器模拟器。"""
 26 | 
 27 |     def __init__(self, grid: list[list[int]]) -> None:
 28 |         """
 29 |         初始化传感器。
 30 | 
 31 |         :param grid: 当前栅格地图，用于射线碰撞判定。
 32 |         """
 33 |         self.grid = grid
 34 |         # 故障注入开关：每 tick 以该概率制造离群/卡死读数，用于异常检测演示。
 35 |         self.fault_prob: float = config.settings.sensor_fault_prob
 36 | 
 37 |     def set_grid(self, grid: list[list[int]]) -> None:
 38 |         """更新地图引用（地图被编辑后调用）。"""
 39 |         self.grid = grid
 40 | 
 41 |     def _cast_ray(self, x: int, y: int, dx: int, dy: int) -> float | None:
 42 |         """
 43 |         沿指定方向发射射线，返回到障碍物的距离（米）。
 44 | 
 45 |         :param x: 起点列坐标。
 46 |         :param y: 起点行坐标。
 47 |         :param dx: 射线方向 x 分量（单位向量）。
 48 |         :param dy: 射线方向 y 分量（单位向量）。
 49 |         :return: 距离（米）；超出量程返回 None。
 50 |         """
```

第 20 页 / 共 60 页

---

<!-- 第 21 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         step = 0
  2 |         max_steps = int(config.settings.sensor_range_m / config.settings.cell_distance_m)
  3 |         current_x, current_y = x, y
  4 |         # 逐格推进，命中障碍物或越界即停止。
  5 |         while step < max_steps:
  6 |             step += 1
  7 |             current_x += dx
  8 |             current_y += dy
  9 |             if not self._in_bounds(current_x, current_y):
 10 |                 return round(step * config.settings.cell_distance_m, 2)
 11 |             if self.grid[current_y][current_x] == CELL_OBSTACLE:
 12 |                 return round(step * config.settings.cell_distance_m, 2)
 13 |         # 走满量程仍未命中，视为超程。
 14 |         return None
 15 | 
 16 |     def _in_bounds(self, x: int, y: int) -> bool:
 17 |         """判断坐标是否在地图范围内。"""
 18 |         height = len(self.grid)
 19 |         width = len(self.grid[0]) if height else 0
 20 |         return 0 <= x < width and 0 <= y < height
 21 | 
 22 |     def read_distances(self, x: int, y: int, theta: float) -> dict:
 23 |         """
 24 |         读取三向测距数据。
 25 | 
 26 |         根据机器人朝向 theta 计算前/左/右三个方向向量后分别测距。
 27 | 
 28 |         :param x: 机器人列坐标。
 29 |         :param y: 机器人行坐标。
 30 |         :param theta: 机器人朝向角（弧度）。
 31 |         :return: {'front': float|None, 'left': float|None, 'right': float|None}
 32 |         """
 33 |         # 朝向向量与左右法向量。
 34 |         forward = (round(math.cos(theta)), round(math.sin(theta)))
 35 |         left = (round(math.cos(theta - math.pi / 2)), round(math.sin(theta - math.pi / 2)))
 36 |         right = (round(math.cos(theta + math.pi / 2)), round(math.sin(theta + math.pi / 2)))
 37 |         return {
 38 |             "front": self._cast_ray(x, y, *forward),
 39 |             "left": self._cast_ray(x, y, *left),
 40 |             "right": self._cast_ray(x, y, *right),
 41 |         }
 42 | 
 43 |     def read_temperature(self, is_moving: bool) -> float:
 44 |         """
 45 |         读取机身温度：基线温度 + 运动温升 + 高斯噪声。
 46 | 
 47 |         :param is_moving: 机器人当前是否在移动。
 48 |         :return: 温度读数（摄氏度，保留一位小数）。
 49 |         """
 50 |         rise = config.settings.temperature_rise_per_move if is_moving else 0.0
```

第 21 页 / 共 60 页

---

<!-- 第 22 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         noise = random.gauss(0, config.settings.temperature_noise * 0.3)
  2 |         value = config.settings.base_temperature + rise + noise
  3 |         return round(value, 1)
  4 | 
  5 |     def _inject_fault(self, readings: dict) -> None:
  6 |         """
  7 |         按概率对某一方向测距注入故障，模拟探头失效。
  8 | 
  9 |         离群值：在真实读数上叠加大幅偏移；卡死值：随机钉死在某读数。
 10 |         注入后该通道读数偏离正常分布，供规则/机器学习检测捕获。
 11 | 
 12 |         :param readings: 待注入的测距字典（原地修改 front/left/right）。
 13 |         """
 14 |         if self.fault_prob <= 0 or random.random() >= self.fault_prob:
 15 |             return
 16 |         channel = random.choice(("front", "left", "right"))
 17 |         base = readings[channel]
 18 |         if base is None:
 19 |             base = config.settings.sensor_range_m
 20 |         if random.random() < 0.5:
 21 |             # 离群值：大幅跳变。
 22 |             readings[channel] = round(max(0.0, base + random.uniform(2.5, 4.0)), 2)
 23 |         else:
 24 |             # 卡死值：随机钉死。
 25 |             readings[channel] = round(random.uniform(0.0, config.settings.sensor_range_m), 2)
 26 | 
 27 |     def read_all(self, x: int, y: int, theta: float, battery: float, is_moving: bool) -> dict:
 28 |         """
 29 |         采集本 tick 的完整传感读数。
 30 | 
 31 |         整合三向测距、温度与电量，并按需注入故障。返回的字典同时作为
 32 |         异常检测器的统一输入（含 position 便于事件定位）。
 33 | 
 34 |         :param x: 机器人列坐标。
 35 |         :param y: 机器人行坐标。
 36 |         :param theta: 机器人朝向角（弧度）。
 37 |         :param battery: 当前电量百分比。
 38 |         :param is_moving: 机器人当前是否在移动。
 39 |         :return: {'battery', 'temperature', 'front', 'left', 'right', 'position'}
 40 |         """
 41 |         distances = self.read_distances(x, y, theta)
 42 |         self._inject_fault(distances)
 43 |         return {
 44 |             "battery": battery,
 45 |             "temperature": self.read_temperature(is_moving),
 46 |             "front": distances["front"],
 47 |             "left": distances["left"],
 48 |             "right": distances["right"],
 49 |             "position": [x, y],
 50 |         }
```

第 22 页 / 共 60 页

---

<!-- 第 23 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | # ===== 文件：backend/app/services/anomaly.py =====
  2 | """
  3 | 异常检测模块。
  4 | 
  5 | 模块功能：对机器人每个 tick 的传感读数做实时异常判断。采用双策略并行、
  6 | 配置切换的设计：
  7 |   - 规则基线（默认）：阈值法，覆盖低电量 / 过热 / 传感器突变三类已知故障，
  8 |     逻辑直观、零冷启动，作为兜底与对照。
  9 |   - 机器学习（IsolationForest）：对滑动窗口内的多维传感数据做在线异常打分，
 10 |     能发现规则难以覆盖的组合型异常。
 11 | 
 12 | 两条策略都输出结构一致的 anomaly 事件，通过 WebSocket 的 anomaly 帧即时推送。
 13 | 机器学习重依赖（numpy / scikit-learn）仅在 ml 策略下按需惰性导入，保证默认
 14 | rule 策略在仅安装基础依赖的环境下也能正常运行。
 15 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 16 | 日期：2026-10-24
 17 | 版本：V1.0
 18 | """
 19 | 
 20 | import logging
 21 | import threading
 22 | import time
 23 | from datetime import datetime, timezone
 24 | from typing import Optional
 25 | 
 26 | from app.core import config
 27 | from app.core.constants import (
 28 |     ANOMALY_LOW_BATTERY,
 29 |     ANOMALY_ML,
 30 |     ANOMALY_OVERHEAT,
 31 |     ANOMALY_SENSOR_FAULT,
 32 | )
 33 | 
 34 | logger = logging.getLogger("simulation.anomaly")
 35 | 
 36 | class BaseAnomalyDetector:
 37 |     """异常检测器公共接口。"""
 38 | 
 39 |     def update(self, reading: dict) -> list[dict]:
 40 |         """
 41 |         根据一帧传感读数返回本轮新触发的异常事件。
 42 | 
 43 |         :param reading: 含 battery/temperature/front/left/right/position/mode 的字典。
 44 |         :return: 异常事件列表（与公共契约 anomaly 帧 data 字段一致）。
 45 |         """
 46 |         raise NotImplementedError
 47 | 
 48 |     def get_history(self) -> list[dict]:
 49 |         """获取全部历史异常事件。"""
 50 |         raise NotImplementedError
```

第 23 页 / 共 60 页

---

<!-- 第 24 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 |     def clear(self) -> None:
  3 |         """清空历史异常事件。"""
  4 |         raise NotImplementedError
  5 | 
  6 |     @staticmethod
  7 |     def _now_iso() -> str:
  8 |         """返回当前时间的 ISO 8601 字符串。"""
  9 |         return datetime.now(timezone.utc).isoformat()
 10 | 
 11 |     def _record(self, anomaly_type: str, message: str, position: list[int]) -> dict:
 12 |         """构造并登记一条异常事件。"""
 13 |         event = {
 14 |             "time": self._now_iso(),
 15 |             "type": anomaly_type,
 16 |             "message": message,
 17 |             "position": position,
 18 |         }
 19 |         self._history.append(event)
 20 |         return event
 21 | 
 22 | class RuleAnomalyDetector(BaseAnomalyDetector):
 23 |     """规则异常检测器（阈值法）。"""
 24 | 
 25 |     def __init__(self) -> None:
 26 |         """初始化检测器并创建空的历史事件列表。"""
 27 |         self._history: list[dict] = []
 28 |         # 已触发的持续型异常，避免同一异常每个 tick 重复推送。
 29 |         self._active: set[str] = set()
 30 | 
 31 |     def update(self, reading: dict) -> list[dict]:
 32 |         """
 33 |         执行一轮规则检测。
 34 | 
 35 |         :param reading: 含 battery/temperature/front/left/right/position/mode 的字典。
 36 |         :return: 本轮新触发的异常事件列表。
 37 |         """
 38 |         battery = reading.get("battery", 100.0)
 39 |         temperature = reading.get("temperature", 0.0)
 40 |         position = reading.get("position", [0, 0])
 41 |         sensors = reading
 42 |         triggered: list[dict] = []
 43 | 
 44 |         # 规则 1：低电量（持续型，恢复到阈值以上后重置）。
 45 |         if battery < config.settings.low_battery_threshold:
 46 |             if "low_battery" not in self._active:
 47 |                 self._active.add("low_battery")
 48 |                 triggered.append(
 49 |                     self._record(
 50 |                         ANOMALY_LOW_BATTERY,
```

第 24 页 / 共 60 页

---

<!-- 第 25 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |                         f"电量不足 {battery:.0f}%，即将自动返航充电",
  2 |                         position,
  3 |                     )
  4 |                 )
  5 |         else:
  6 |             self._active.discard("low_battery")
  7 | 
  8 |         # 规则 2：过热（持续型）。
  9 |         if temperature > config.settings.overheat_threshold:
 10 |             if "overheat" not in self._active:
 11 |                 self._active.add("overheat")
 12 |                 triggered.append(
 13 |                     self._record(
 14 |                         ANOMALY_OVERHEAT,
 15 |                         f"机身温度 {temperature:.1f}℃ 超过安全阈值",
 16 |                         position,
 17 |                     )
 18 |                 )
 19 |         else:
 20 |             self._active.discard("overheat")
 21 | 
 22 |         # 规则 3：传感器读数突变（瞬时型，每次突变都上报）。
 23 |         readings = [sensors.get(key) for key in ("front", "left", "right")]
 24 |         valid = [value for value in readings if value is not None]
 25 |         for i in range(1, len(valid)):
 26 |             delta = abs(valid[i] - valid[i - 1])
 27 |             if delta > config.settings.sensor_fault_delta:
 28 |                 triggered.append(
 29 |                     self._record(
 30 |                         ANOMALY_SENSOR_FAULT,
 31 |                         f"传感器读数突变 {delta:.1f}m，疑似故障",
 32 |                         position,
 33 |                     )
 34 |                 )
 35 |                 break  # 同一 tick 只报一次，避免刷屏。
 36 | 
 37 |         return triggered
 38 | 
 39 |     def get_history(self) -> list[dict]:
 40 |         """获取全部历史异常事件。"""
 41 |         return list(self._history)
 42 | 
 43 |     def clear(self) -> None:
 44 |         """清空历史异常事件。"""
 45 |         self._history.clear()
 46 |         self._active.clear()
 47 | 
 48 | class MLAnomalyDetector(BaseAnomalyDetector):
 49 |     """
 50 |     IsolationForest 在线异常检测器。
```

第 25 页 / 共 60 页

---

<!-- 第 26 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 |     冷启动阶段（默认 500 tick）以正常模式采集样本，训练首个模型；之后每个
  3 |     tick 把最新特征追加到长度为 120 的滑动窗口并打分。每 60 秒用窗口内最近
  4 |     数据在后台线程增量重训，适应温度基线等缓慢漂移。
  5 | 
  6 |     两个关键设计：
  7 |       1. 特征标准化——电量（跨度约 40）与温度/距离（跨度约 5）量纲差异大，
  8 |          直接喂模型会被电量主导；用训练段均值/方差做 z-score 标准化，
  9 |          让各维贡献均衡。
 10 |       2. 阈值自动校准——取正常段异常分数的低分位作为阈值，把误报率控制在
 11 |          ml_score_percentile 水平；也可用 ML_SCORE_THRESHOLD 指定固定阈值覆盖。
 12 |     标准化使 IsolationForest 擅长捕捉"分布内的组合型异常"（如多向探头同时
 13 |     失效、温度与距离背离）；对单维超范围外推故障，由规则基线兜底更稳。
 14 | 
 15 |     重依赖 numpy / scikit-learn 在首次训练时惰性导入，未安装时调用抛 ImportError。
 16 |     """
 17 | 
 18 |     def __init__(
 19 |         self,
 20 |         coldstart_ticks: Optional[int] = None,
 21 |         window_size: Optional[int] = None,
 22 |         retrain_seconds: Optional[int] = None,
 23 |         score_percentile: Optional[float] = None,
 24 |         score_threshold: Optional[str] = None,
 25 |         contamination: Optional[str] = None,
 26 |     ) -> None:
 27 |         """初始化检测器（参数缺省时取自全局配置）。"""
 28 |         self.coldstart_ticks = coldstart_ticks or config.settings.ml_coldstart_ticks
 29 |         self.window_size = window_size or config.settings.ml_window_size
 30 |         self.retrain_seconds = retrain_seconds or config.settings.ml_retrain_seconds
 31 |         self.score_percentile = (
 32 |             score_percentile if score_percentile is not None else config.settings.ml_score_percentile
 33 |         )
 34 |         # 固定阈值覆盖：配置了具体数值则用它，否则按正常分数分位自动校准。
 35 |         raw = score_threshold if score_threshold is not None else config.settings.ml_score_threshold
 36 |         try:
 37 |             self._threshold_override: Optional[float] = float(raw) if str(raw).strip() else None
 38 |         except (TypeError, ValueError):
 39 |             self._threshold_override = None
 40 |         self.contamination = contamination or config.settings.ml_contamination
 41 | 
 42 |         self._history: list[dict] = []
 43 |         self._active: set[str] = set()
 44 |         self._buffer: list[list[float]] = []          # 冷启动采集缓冲。
 45 |         self._window: list[list[float]] = []          # 在线打分滑动窗口。
 46 |         self._model = None                            # IsolationForest 实例。
 47 |         self._mean = None                             # 各维均值（标准化用）。
 48 |         self._std = None                              # 各维标准差（标准化用）。
 49 |         self._threshold: Optional[float] = None       # 校准后的异常阈值。
 50 |         self._tick = 0
```

第 26 页 / 共 60 页

---

<!-- 第 27 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         self._last_retrain = time.time()
  2 |         self._training = False
  3 |         self._lock = threading.Lock()
  4 | 
  5 |     # ---------- 特征 ----------
  6 | 
  7 |     @staticmethod
  8 |     def _to_feature(reading: dict) -> list[float]:
  9 |         """
 10 |         把一帧读数映射成 5 维特征向量。
 11 | 
 12 |         缺失读数（射线超程）用量程上限填充，保证维度恒定、输入稳定。
 13 | 
 14 |         :param reading: 含 battery/temperature/front/left/right 的字典。
 15 |         :return: [battery, temperature, front, left, right]
 16 |         """
 17 |         range_m = config.settings.sensor_range_m
 18 |         fill = lambda v: range_m if v is None else v  # noqa: E731 - 单行填充辅助。
 19 |         return [
 20 |             float(reading.get("battery", 100.0)),
 21 |             float(reading.get("temperature", 0.0)),
 22 |             float(fill(reading.get("front"))),
 23 |             float(fill(reading.get("left"))),
 24 |             float(fill(reading.get("right"))),
 25 |         ]
 26 | 
 27 |     # ---------- 模型训练（惰性导入重依赖） ----------
 28 | 
 29 |     def _fit(self, X: list) -> None:
 30 |         """标准化后训练 IsolationForest，并校准阈值；线程安全地整体替换状态。"""
 31 |         import numpy as np
 32 |         from sklearn.ensemble import IsolationForest  # 惰性导入，基础环境可无此依赖。
 33 | 
 34 |         arr = np.asarray(X, dtype=float)
 35 |         mean = arr.mean(axis=0)
 36 |         std = arr.std(axis=0)
 37 |         std[std == 0] = 1.0  # 某维无波动时避免除零。
 38 |         standardized = (arr - mean) / std
 39 | 
 40 |         contamination = self.contamination if self.contamination == "auto" else float(self.contamination)
 41 |         model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
 42 |         model.fit(standardized)
 43 | 
 44 |         # 用训练段（视为正常段）分数分布校准阈值，控制误报率。
 45 |         calibrated = float(np.percentile(model.score_samples(standardized), self.score_percentile))
 46 |         threshold = self._threshold_override if self._threshold_override is not None else calibrated
 47 | 
 48 |         with self._lock:
 49 |             self._model = model
 50 |             self._mean = mean
```

第 27 页 / 共 60 页

---

<!-- 第 28 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |             self._std = std
  2 |             self._threshold = threshold
  3 | 
  4 |     def _retrain_worker(self, snapshot: list) -> None:
  5 |         """后台增量重训：训练完成后复位训练标志。"""
  6 |         try:
  7 |             self._fit(snapshot)
  8 |             logger.info("ML 模型增量重训完成，样本数 %d", len(snapshot))
  9 |         except Exception:  # noqa: BLE001 - 重训失败不应影响仿真主循环。
 10 |             logger.exception("ML 模型增量重训失败")
 11 |         finally:
 12 |             self._training = False
 13 | 
 14 |     # ---------- 推理接口 ----------
 15 | 
 16 |     def decision_score(self, reading: dict) -> float:
 17 |         """
 18 |         返回单条读数的异常分数（score_samples，越低越异常）。
 19 | 
 20 |         模型未就绪时返回 0.0（视为正常）。
 21 | 
 22 |         :param reading: 传感读数字典。
 23 |         :return: 异常分数。
 24 |         """
 25 |         import numpy as np  # 惰性导入。
 26 | 
 27 |         with self._lock:
 28 |             model, mean, std = self._model, self._mean, self._std
 29 |         if model is None or mean is None:
 30 |             return 0.0
 31 |         feature = (np.asarray([self._to_feature(reading)], dtype=float) - mean) / std
 32 |         return float(model.score_samples(feature)[0])
 33 | 
 34 |     def is_anomaly(self, reading: dict) -> bool:
 35 |         """判断单条读数是否为异常（供测试与离线评估使用）。"""
 36 |         with self._lock:
 37 |             threshold = self._threshold
 38 |         if threshold is None:
 39 |             return False
 40 |         return self.decision_score(reading) < threshold
 41 | 
 42 |     def update(self, reading: dict) -> list[dict]:
 43 |         """
 44 |         推进一帧：冷启动采集 / 在线打分，返回本轮新触发的异常事件。
 45 | 
 46 |         :param reading: 含 battery/temperature/front/left/right/position/mode 的字典。
 47 |         :return: 异常事件列表。
 48 |         """
 49 |         feature = self._to_feature(reading)
 50 |         self._tick += 1
```

第 28 页 / 共 60 页

---

<!-- 第 29 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         position = reading.get("position", [0, 0])
  2 |         events: list[dict] = []
  3 | 
  4 |         # 冷启动：采集足够样本后训练首个模型。
  5 |         if self._model is None:
  6 |             if not self._training:
  7 |                 self._buffer.append(feature)
  8 |                 if len(self._buffer) >= self.coldstart_ticks:
  9 |                     self._training = True
 10 |                     self._fit([list(v) for v in self._buffer])
 11 |                     self._window.extend(self._buffer)
 12 |                     self._training = False
 13 |                     logger.info("ML 模型冷启动完成，样本数 %d", len(self._buffer))
 14 |             return events
 15 | 
 16 |         # 在线打分：追加窗口并对最新样本评分。
 17 |         self._window.append(feature)
 18 |         score = self.decision_score(reading)
 19 |         with self._lock:
 20 |             threshold = self._threshold
 21 |         if threshold is not None and score < threshold:
 22 |             if "ml_anomaly" not in self._active:
 23 |                 self._active.add("ml_anomaly")
 24 |                 events.append(
 25 |                     self._record(
 26 |                         ANOMALY_ML,
 27 |                         f"机器学习检测到异常工况（评分 {score:.2f}）",
 28 |                         position,
 29 |                     )
 30 |                 )
 31 |         else:
 32 |             self._active.discard("ml_anomaly")
 33 | 
 34 |         # 周期性后台增量重训。
 35 |         now = time.time()
 36 |         if now - self._last_retrain >= self.retrain_seconds and not self._training:
 37 |             self._last_retrain = now
 38 |             snapshot = [list(v) for v in self._window]
 39 |             if len(snapshot) >= self.window_size:
 40 |                 self._training = True
 41 |                 worker = threading.Thread(target=self._retrain_worker, args=(snapshot,), daemon=True)
 42 |                 worker.start()
 43 | 
 44 |         return events
 45 | 
 46 |     def get_history(self) -> list[dict]:
 47 |         """获取全部历史异常事件。"""
 48 |         return list(self._history)
 49 | 
 50 |     def clear(self) -> None:
```

第 29 页 / 共 60 页

---

<!-- 第 30 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         """清空历史异常事件与在线状态。"""
  2 |         self._history.clear()
  3 |         self._active.clear()
  4 |         self._buffer.clear()
  5 |         self._window.clear()
  6 |         self._model = None
  7 |         self._mean = None
  8 |         self._std = None
  9 |         self._threshold = None
 10 |         self._tick = 0
 11 |         self._last_retrain = time.time()
 12 |         self._training = False
 13 | 
 14 | def create_detector(strategy: Optional[str] = None) -> BaseAnomalyDetector:
 15 |     """
 16 |     按策略创建异常检测器，对调用方透明。
 17 | 
 18 |     :param strategy: 'rule'（默认）或 'ml'。
 19 |     :return: 对应策略的检测器实例。
 20 |     """
 21 |     strategy = strategy or config.settings.anomaly_strategy
 22 |     if strategy == "ml":
 23 |         return MLAnomalyDetector()
 24 |     if strategy != "rule":
 25 |         logger.warning("未知异常检测策略 %r，回退到规则基线", strategy)
 26 |     return RuleAnomalyDetector()
 27 | # ===== 文件：backend/app/services/patrol.py =====
 28 | """
 29 | 巡检任务管理模块。
 30 | 
 31 | 模块功能：管理多巡检点自动巡检任务。采用最近邻贪心算法对巡检点排序，
 32 | 逐段调用 A* 生成路径；当某个巡检点不可达时记录告警并跳过，同时支持
 33 | "排除最小障碍"重试策略（配合前端的一键排障功能）。
 34 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 35 | 日期：2026-10-24
 36 | 版本：V1.0
 37 | """
 38 | 
 39 | from app.algorithms.astar import astar
 40 | from app.core.constants import CELL_OBSTACLE
 41 | 
 42 | def order_goals_by_nearest(
 43 |     start: tuple[int, int],
 44 |     goals: list[tuple[int, int]],
 45 | ) -> list[tuple[int, int]]:
 46 |     """
 47 |     最近邻贪心排序：每次从剩余巡检点中选取离当前位置最近的点。
 48 | 
 49 |     :param start: 起始位置 (x, y)。
 50 |     :param goals: 巡检点列表。
```

第 30 页 / 共 60 页

---

<!-- 第 31 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |       <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
  2 |         <span class="text-gray-500 dark:text-gray-400">坐标</span>
  3 |         <div class="font-mono text-gray-900 dark:text-gray-100">{{ robot.x }}, {{ robot.y }}</div>
  4 |       </div>
  5 |       <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
  6 |         <span class="text-gray-500 dark:text-gray-400">朝向</span>
  7 |         <div class="font-mono text-gray-900 dark:text-gray-100">{{ thetaDegrees }}°</div>
  8 |       </div>
  9 |       <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
 10 |         <span class="text-gray-500 dark:text-gray-400">速度</span>
 11 |         <div class="font-mono text-gray-900 dark:text-gray-100">{{ robot.speed.toFixed(2) }} m/s</div>
 12 |       </div>
 13 |       <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
 14 |         <span class="text-gray-500 dark:text-gray-400">模式</span>
 15 |         <div class="font-medium text-gray-900 dark:text-gray-100">{{ robot.mode }}</div>
 16 |       </div>
 17 |     </div>
 18 | 
 19 |     <!-- 电量 -->
 20 |     <div class="space-y-1">
 21 |       <div class="flex justify-between text-xs">
 22 |         <span class="text-gray-600 dark:text-gray-300">电量</span>
 23 |         <span :class="batteryClass">{{ robot.battery.toFixed(1) }}%</span>
 24 |       </div>
 25 |       <div class="h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
 26 |         <div
 27 |           class="h-full rounded-full transition-all"
 28 |           :class="batteryBarClass"
 29 |           :style="{ width: `${Math.max(0, Math.min(100, robot.battery))}%` }"
 30 |         />
 31 |       </div>
 32 |     </div>
 33 | 
 34 |     <!-- 三向距离 -->
 35 |     <div class="grid grid-cols-3 gap-2">
 36 |       <div
 37 |         v-for="name in sensorNames"
 38 |         :key="name.key"
 39 |         class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 text-center"
 40 |       >
 41 |         <div class="text-xs text-gray-500 dark:text-gray-400">{{ name.label }}</div>
 42 |         <div class="font-mono text-sm font-medium text-gray-900 dark:text-gray-100">
 43 |           {{ formatDistance(robot.sensors[name.key]) }}
 44 |         </div>
 45 |         <div class="h-1.5 mt-1 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
 46 |           <div
 47 |             class="h-full bg-primary-500 rounded-full"
 48 |             :style="{ width: `${sensorPercent(robot.sensors[name.key])}%` }"
 49 |           />
 50 |         </div>
```

第 31 页 / 共 60 页

---

<!-- 第 32 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |       </div>
  2 |     </div>
  3 | 
  4 |     <!-- 温度曲线 -->
  5 |     <div>
  6 |       <div class="flex justify-between text-xs mb-1">
  7 |         <span class="text-gray-600 dark:text-gray-300">温度趋势（最近 60 秒）</span>
  8 |         <span class="font-mono" :class="tempClass">{{ robot.sensors.temperature.toFixed(1) }}℃</span>
  9 |       </div>
 10 |       <canvas
 11 |         ref="chartRef"
 12 |         class="w-full h-24 rounded-lg bg-gray-50 dark:bg-gray-800"
 13 |       />
 14 |     </div>
 15 |   </div>
 16 | </template>
 17 | 
 18 | <script setup>
 19 | /**
 20 |  * 组件功能：状态仪表盘
 21 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 22 |  * 日期：2026-10-23
 23 |  * 版本：V1.0
 24 |  *
 25 |  * 展示机器人坐标、电量、模式、三向传感器距离以及最近 60 秒温度折线图。
 26 |  */
 27 | 
 28 | import { computed, watch, ref, onMounted } from 'vue'
 29 | 
 30 | const props = defineProps({
 31 |   robot: {
 32 |     type: Object,
 33 |     required: true,
 34 |   },
 35 |   temperatureHistory: {
 36 |     type: Array,
 37 |     default: () => [],
 38 |   },
 39 | })
 40 | 
 41 | const chartRef = ref(null)
 42 | 
 43 | const sensorNames = [
 44 |   { key: 'front', label: '前向' },
 45 |   { key: 'left', label: '左侧' },
 46 |   { key: 'right', label: '右侧' },
 47 | ]
 48 | 
 49 | const thetaDegrees = computed(() => {
 50 |   let deg = (props.robot.theta * 180) / Math.PI
```

第 32 页 / 共 60 页

---

<!-- 第 33 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |   deg = ((deg % 360) + 360) % 360
  2 |   return Math.round(deg)
  3 | })
  4 | 
  5 | const batteryClass = computed(() => {
  6 |   return props.robot.battery < 20 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-700 dark:text-gray-200'
  7 | })
  8 | 
  9 | const batteryBarClass = computed(() => {
 10 |   if (props.robot.battery < 20) return 'bg-red-500'
 11 |   if (props.robot.battery < 50) return 'bg-yellow-500'
 12 |   return 'bg-green-500'
 13 | })
 14 | 
 15 | const tempClass = computed(() => {
 16 |   return props.robot.sensors.temperature > 60 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-700 dark:text-gray-200'
 17 | })
 18 | 
 19 | function formatDistance(value) {
 20 |   if (value === null || value === undefined) return '>5m'
 21 |   return `${value.toFixed(2)}m`
 22 | }
 23 | 
 24 | function sensorPercent(value) {
 25 |   if (value === null || value === undefined) return 100
 26 |   return Math.min(100, (value / 5) * 100)
 27 | }
 28 | 
 29 | onMounted(() => drawChart())
 30 | watch(() => [props.temperatureHistory, props.robot.sensors.temperature], () => drawChart(), { deep: true })
 31 | 
 32 | function drawChart() {
 33 |   const canvas = chartRef.value
 34 |   if (!canvas) return
 35 |   const rect = canvas.getBoundingClientRect()
 36 |   const dpr = window.devicePixelRatio || 1
 37 |   canvas.width = Math.max(1, Math.floor(rect.width * dpr))
 38 |   canvas.height = Math.max(1, Math.floor(rect.height * dpr))
 39 | 
 40 |   const ctx = canvas.getContext('2d')
 41 |   ctx.clearRect(0, 0, canvas.width, canvas.height)
 42 |   ctx.save()
 43 |   ctx.scale(dpr, dpr)
 44 | 
 45 |   const width = rect.width
 46 |   const height = rect.height
 47 |   const padding = { top: 8, right: 8, bottom: 16, left: 28 }
 48 |   const chartW = width - padding.left - padding.right
 49 |   const chartH = height - padding.top - padding.bottom
 50 | 
```

第 33 页 / 共 60 页

---

<!-- 第 34 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |   const data = props.temperatureHistory.length > 0 ? props.temperatureHistory : [35]
  2 |   const minTemp = 30
  3 |   const maxTemp = 70
  4 | 
  5 |   // 坐标轴
  6 |   ctx.strokeStyle = '#9ca3af'
  7 |   ctx.lineWidth = 1
  8 |   ctx.beginPath()
  9 |   ctx.moveTo(padding.left, padding.top)
 10 |   ctx.lineTo(padding.left, height - padding.bottom)
 11 |   ctx.lineTo(width - padding.right, height - padding.bottom)
 12 |   ctx.stroke()
 13 | 
 14 |   // Y 轴刻度
 15 |   ctx.fillStyle = '#6b7280'
 16 |   ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
 17 |   ctx.textAlign = 'right'
 18 |   ctx.textBaseline = 'middle'
 19 |   for (const t of [30, 40, 50, 60, 70]) {
 20 |     const y = height - padding.bottom - ((t - minTemp) / (maxTemp - minTemp)) * chartH
 21 |     ctx.fillText(String(t), padding.left - 4, y)
 22 |   }
 23 | 
 24 |   // 温度折线
 25 |   ctx.strokeStyle = '#ef4444'
 26 |   ctx.lineWidth = 2
 27 |   ctx.lineJoin = 'round'
 28 |   ctx.beginPath()
 29 |   data.forEach((value, index) => {
 30 |     const x = padding.left + (index / (Math.max(1, data.length - 1))) * chartW
 31 |     const y = height - padding.bottom - ((value - minTemp) / (maxTemp - minTemp)) * chartH
 32 |     if (index === 0) {
 33 |       ctx.moveTo(x, y)
 34 |     } else {
 35 |       ctx.lineTo(x, y)
 36 |     }
 37 |   })
 38 |   ctx.stroke()
 39 | 
 40 |   // 60℃ 警示线
 41 |   const warnY = height - padding.bottom - ((60 - minTemp) / (maxTemp - minTemp)) * chartH
 42 |   ctx.strokeStyle = '#f87171'
 43 |   ctx.setLineDash([4, 4])
 44 |   ctx.beginPath()
 45 |   ctx.moveTo(padding.left, warnY)
 46 |   ctx.lineTo(width - padding.right, warnY)
 47 |   ctx.stroke()
 48 |   ctx.setLineDash([])
 49 | 
 50 |   ctx.restore()
```

第 34 页 / 共 60 页

---

<!-- 第 35 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | }
  2 | </script>
  3 | # ===== 文件：frontend/src/components/AlertList.vue =====
  4 | <template>
  5 |   <div class="flex flex-col gap-3 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 h-96">
  6 |     <div class="flex items-center justify-between">
  7 |       <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">告警列表</h2>
  8 |       <div class="flex gap-2">
  9 |         <button
 10 |           type="button"
 11 |           class="text-xs px-2 py-1 rounded-md border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
 12 |           @click="$emit('export')"
 13 |         >
 14 |           导出 JSON
 15 |         </button>
 16 |         <button
 17 |           type="button"
 18 |           class="text-xs px-2 py-1 rounded-md text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
 19 |           @click="$emit('clear')"
 20 |         >
 21 |           清空
 22 |         </button>
 23 |       </div>
 24 |     </div>
 25 | 
 26 |     <div class="flex-1 overflow-y-auto pr-1 space-y-2">
 27 |       <div v-if="anomalies.length === 0" class="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
 28 |         暂无异常事件
 29 |       </div>
 30 |       <div
 31 |         v-for="(item, index) in anomalies"
 32 |         :key="index"
 33 |         class="flex gap-3 p-3 rounded-lg border-l-4 text-sm"
 34 |         :class="typeClass(item.type)"
 35 |       >
 36 |         <div class="flex-1 min-w-0">
 37 |           <div class="flex items-center gap-2">
 38 |             <span class="font-medium">{{ typeLabel(item.type) }}</span>
 39 |             <span class="text-xs text-gray-500 dark:text-gray-400">{{ formatTime(item.time) }}</span>
 40 |           </div>
 41 |           <p class="text-gray-700 dark:text-gray-300 mt-0.5">{{ item.message }}</p>
 42 |           <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
 43 |             位置：[{{ item.position[0] }}, {{ item.position[1] }}]
 44 |           </p>
 45 |         </div>
 46 |       </div>
 47 |     </div>
 48 |   </div>
 49 | </template>
 50 | 
```

第 35 页 / 共 60 页

---

<!-- 第 36 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | <script setup>
  2 | /**
  3 |  * 组件功能：告警列表
  4 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
  5 |  * 日期：2026-10-23
  6 |  * 版本：V1.0
  7 |  *
  8 |  * 以时间线方式展示异常事件，支持清空与导出 JSON。
  9 |  */
 10 | 
 11 | defineProps({
 12 |   anomalies: {
 13 |     type: Array,
 14 |     default: () => [],
 15 |   },
 16 | })
 17 | 
 18 | defineEmits(['clear', 'export'])
 19 | 
 20 | const typeLabels = {
 21 |   low_battery: '低电量',
 22 |   obstacle: '障碍物',
 23 |   sensor_fault: '传感器异常',
 24 |   overheat: '过热',
 25 | }
 26 | 
 27 | const typeClasses = {
 28 |   low_battery: 'border-orange-500 bg-orange-50 dark:bg-orange-900/20',
 29 |   obstacle: 'border-red-500 bg-red-50 dark:bg-red-900/20',
 30 |   sensor_fault: 'border-purple-500 bg-purple-50 dark:bg-purple-900/20',
 31 |   overheat: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
 32 | }
 33 | 
 34 | function typeLabel(type) {
 35 |   return typeLabels[type] || type
 36 | }
 37 | 
 38 | function typeClass(type) {
 39 |   return typeClasses[type] || 'border-gray-500 bg-gray-50 dark:bg-gray-800'
 40 | }
 41 | 
 42 | function formatTime(isoString) {
 43 |   const date = new Date(isoString)
 44 |   return date.toLocaleTimeString('zh-CN', { hour12: false })
 45 | }
 46 | </script>
 47 | # ===== 文件：frontend/src/components/PlaybackBar.vue =====
 48 | <template>
 49 |   <div v-if="snapshots.length > 0" class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-3">
 50 |     <div class="flex items-center justify-between">
```

第 36 页 / 共 60 页

---

<!-- 第 37 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |       <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">路径回放</h2>
  2 |       <span class="text-xs text-gray-500 dark:text-gray-400">{{ currentIndex + 1 }} / {{ snapshots.length }}</span>
  3 |     </div>
  4 |     <div class="flex items-center gap-3">
  5 |       <button
  6 |         type="button"
  7 |         class="play-pause-button flex items-center justify-center w-9 h-9 rounded-full bg-primary-600 text-white hover:bg-primary-700"
  8 |         :aria-label="isPlaying ? '暂停' : '播放'"
  9 |         @click="togglePlay"
 10 |       >
 11 |         <svg v-if="isPlaying" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg>
 12 |         <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
 13 |       </button>
 14 |       <input
 15 |         type="range"
 16 |         min="0"
 17 |         :max="snapshots.length - 1"
 18 |         :value="currentIndex"
 19 |         class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-600"
 20 |         @input="handleInput"
 21 |       >
 22 |       <span class="text-xs font-mono text-gray-600 dark:text-gray-300 w-16 text-right">{{ formatTime(currentTime) }}</span>
 23 |     </div>
 24 |   </div>
 25 | </template>
 26 | 
 27 | <script setup>
 28 | /**
 29 |  * 组件功能：路径回放控制条
 30 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 31 |  * 日期：2026-10-23
 32 |  * 版本：V1.0
 33 |  *
 34 |  * 在巡检结束后提供时间轴拖动与播放 / 暂停，用于回放机器人轨迹。
 35 |  */
 36 | 
 37 | import { computed } from 'vue'
 38 | 
 39 | const props = defineProps({
 40 |   snapshots: {
 41 |     type: Array,
 42 |     default: () => [],
 43 |   },
 44 |   currentIndex: {
 45 |     type: Number,
 46 |     default: 0,
 47 |   },
 48 |   isPlaying: {
 49 |     type: Boolean,
 50 |     default: false,
```

第 37 页 / 共 60 页

---

<!-- 第 38 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |   },
  2 | })
  3 | 
  4 | const emit = defineEmits(['seek', 'play', 'pause'])
  5 | 
  6 | const currentTime = computed(() => {
  7 |   const snapshot = props.snapshots[props.currentIndex]
  8 |   return snapshot ? snapshot.time : 0
  9 | })
 10 | 
 11 | function togglePlay() {
 12 |   emit(props.isPlaying ? 'pause' : 'play')
 13 | }
 14 | 
 15 | function handleInput(event) {
 16 |   emit('seek', Number(event.target.value))
 17 | }
 18 | 
 19 | function formatTime(timestamp) {
 20 |   const date = new Date(timestamp)
 21 |   return date.toLocaleTimeString('zh-CN', { hour12: false })
 22 | }
 23 | </script>
 24 | # ===== 文件：frontend/src/components/Joystick.vue =====
 25 | <template>
 26 |   <div class="flex flex-col items-center gap-2">
 27 |     <div
 28 |       ref="baseRef"
 29 |       class="relative w-32 h-32 rounded-full border-2 border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 touch-none select-none"
 30 |       @pointerdown="handlePointerDown"
 31 |       @pointermove="handlePointerMove"
 32 |       @pointerup="handlePointerUp"
 33 |       @pointerleave="handlePointerUp"
 34 |     >
 35 |       <div
 36 |         class="absolute top-1/2 left-1/2 w-12 h-12 -mt-6 -ml-6 rounded-full bg-primary-500 shadow-md transition-transform"
 37 |         :style="knobStyle"
 38 |       />
 39 |     </div>
 40 |     <span class="text-xs text-gray-500 dark:text-gray-400">虚拟摇杆</span>
 41 |   </div>
 42 | </template>
 43 | 
 44 | <script setup>
 45 | /**
 46 |  * 组件功能：移动端虚拟摇杆
 47 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 48 |  * 日期：2026-10-23
 49 |  * 版本：V1.0
 50 |  *
```

第 38 页 / 共 60 页

---

<!-- 第 39 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |  * 在触摸屏上提供方向控制，持续按住时会以固定间隔向父组件发送方向指令。
  2 |  */
  3 | 
  4 | import { ref, computed, onUnmounted } from 'vue'
  5 | 
  6 | const emit = defineEmits(['move'])
  7 | 
  8 | const baseRef = ref(null)
  9 | const active = ref(false)
 10 | const dx = ref(0)
 11 | const dy = ref(0)
 12 | let emitInterval = null
 13 | 
 14 | const knobStyle = computed(() => ({
 15 |   transform: `translate(${dx.value * 30}px, ${dy.value * 30}px)`,
 16 | }))
 17 | 
 18 | function handlePointerDown(event) {
 19 |   event.preventDefault()
 20 |   active.value = true
 21 |   updateDirection(event)
 22 |   emitMove()
 23 |   emitInterval = setInterval(emitMove, 200)
 24 | }
 25 | 
 26 | function handlePointerMove(event) {
 27 |   if (!active.value) return
 28 |   event.preventDefault()
 29 |   updateDirection(event)
 30 | }
 31 | 
 32 | function handlePointerUp(event) {
 33 |   if (!active.value) return
 34 |   event.preventDefault()
 35 |   active.value = false
 36 |   dx.value = 0
 37 |   dy.value = 0
 38 |   if (emitInterval) {
 39 |     clearInterval(emitInterval)
 40 |     emitInterval = null
 41 |   }
 42 | }
 43 | 
 44 | function updateDirection(event) {
 45 |   const rect = baseRef.value.getBoundingClientRect()
 46 |   const centerX = rect.left + rect.width / 2
 47 |   const centerY = rect.top + rect.height / 2
 48 |   const rawDx = event.clientX - centerX
 49 |   const rawDy = event.clientY - centerY
 50 |   const distance = Math.sqrt(rawDx * rawDx + rawDy * rawDy)
```

第 39 页 / 共 60 页

---

<!-- 第 40 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |   const maxDistance = rect.width / 2
  2 | 
  3 |   if (distance > maxDistance) {
  4 |     const ratio = maxDistance / distance
  5 |     dx.value = rawDx * ratio / maxDistance
  6 |     dy.value = rawDy * ratio / maxDistance
  7 |   } else {
  8 |     dx.value = rawDx / maxDistance
  9 |     dy.value = rawDy / maxDistance
 10 |   }
 11 | }
 12 | 
 13 | function emitMove() {
 14 |   const threshold = 0.3
 15 |   let moveDx = 0
 16 |   let moveDy = 0
 17 |   if (Math.abs(dx.value) > threshold) {
 18 |     moveDx = dx.value > 0 ? 1 : -1
 19 |   }
 20 |   if (Math.abs(dy.value) > threshold) {
 21 |     moveDy = dy.value > 0 ? 1 : -1
 22 |   }
 23 |   if (moveDx !== 0 || moveDy !== 0) {
 24 |     emit('move', { dx: moveDx, dy: moveDy })
 25 |   }
 26 | }
 27 | 
 28 | onUnmounted(() => {
 29 |   if (emitInterval) {
 30 |     clearInterval(emitInterval)
 31 |   }
 32 | })
 33 | </script>
 34 | # ===== 文件：frontend/src/components/MobileControls.vue =====
 35 | <template>
 36 |   <div class="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3 safe-area-pb">
 37 |     <div class="flex items-center justify-between gap-3">
 38 |       <!-- 方向键 -->
 39 |       <div class="grid grid-cols-3 gap-1.5 shrink-0">
 40 |         <div />
 41 |         <button
 42 |           type="button"
 43 |           class="mctrl-btn"
 44 |           aria-label="前进"
 45 |           @click="emitMove(0, -1)"
 46 |         >
 47 |           <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
 48 |         </button>
 49 |         <div />
 50 |         <button
```

第 40 页 / 共 60 页

---

<!-- 第 41 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |           type="button"
  2 |           class="mctrl-btn"
  3 |           aria-label="左转"
  4 |           @click="emitMove(-1, 0)"
  5 |         >
  6 |           <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
  7 |         </button>
  8 |         <button
  9 |           type="button"
 10 |           class="mctrl-btn bg-gray-100 dark:bg-gray-800"
 11 |           aria-label="复位"
 12 |           @click="$emit('reset')"
 13 |         >
 14 |           <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></svg>
 15 |         </button>
 16 |         <button
 17 |           type="button"
 18 |           class="mctrl-btn"
 19 |           aria-label="右转"
 20 |           @click="emitMove(1, 0)"
 21 |         >
 22 |           <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
 23 |         </button>
 24 |         <div />
 25 |         <button
 26 |           type="button"
 27 |           class="mctrl-btn"
 28 |           aria-label="后退"
 29 |           @click="emitMove(0, 1)"
 30 |         >
 31 |           <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7" /></svg>
 32 |         </button>
 33 |         <div />
 34 |       </div>
 35 | 
 36 |       <!-- 编辑模式 + 巡检 -->
 37 |       <div class="flex-1 min-w-0 flex flex-col gap-2">
 38 |         <div class="flex gap-1 overflow-x-auto no-scrollbar">
 39 |           <button
 40 |             v-for="mode in editModes"
 41 |             :key="mode.key"
 42 |             type="button"
 43 |             class="shrink-0 px-2.5 py-1.5 text-[10px] rounded-md border transition-colors"
 44 |             :class="editMode === mode.key ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300'"
 45 |             @click="$emit('set-edit-mode', mode.key)"
 46 |           >
 47 |             {{ mode.label }}
 48 |           </button>
 49 |         </div>
 50 |         <div class="flex gap-2">
```

第 41 页 / 共 60 页

---

<!-- 第 42 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |           <button
  2 |             type="button"
  3 |             class="flex-1 px-2 py-2 text-xs font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
  4 |             :disabled="patrolStatus.running"
  5 |             @click="$emit('start-patrol')"
  6 |           >
  7 |             开始巡检
  8 |           </button>
  9 |           <button
 10 |             type="button"
 11 |             class="flex-1 px-2 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 text-gray-700 dark:text-gray-200"
 12 |             :disabled="!patrolStatus.running"
 13 |             @click="$emit('stop-patrol')"
 14 |           >
 15 |             停止
 16 |           </button>
 17 |         </div>
 18 |         <div class="flex gap-2">
 19 |           <button
 20 |             type="button"
 21 |             class="flex-1 px-2 py-1.5 text-xs rounded-lg border transition-colors"
 22 |             :class="robot.mode === 'blocked'
 23 |               ? 'border-red-500 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
 24 |               : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300'"
 25 |             @click="$emit('resolve-fault')"
 26 |           >
 27 |             一键排障
 28 |           </button>
 29 |           <button
 30 |             type="button"
 31 |             class="flex-1 px-2 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
 32 |             @click="$emit('fit-map')"
 33 |           >
 34 |             适配地图
 35 |           </button>
 36 |           <button
 37 |             type="button"
 38 |             class="flex-1 px-2 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
 39 |             @click="$emit('toggle-detail')"
 40 |           >
 41 |             {{ detailOpen ? '收起详情' : '更多详情' }}
 42 |           </button>
 43 |         </div>
 44 |       </div>
 45 |     </div>
 46 |   </div>
 47 | </template>
 48 | 
 49 | <script setup>
 50 | /**
```

第 42 页 / 共 60 页

---

<!-- 第 43 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |  * 组件功能：移动端底部快捷控制条
  2 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
  3 |  * 日期：2026-10-23
  4 |  * 版本：V1.0
  5 |  */
  6 | 
  7 | defineProps({
  8 |   robot: { type: Object, required: true },
  9 |   patrolStatus: { type: Object, required: true },
 10 |   editMode: { type: String, default: 'pan' },
 11 |   detailOpen: { type: Boolean, default: false },
 12 | })
 13 | 
 14 | const emit = defineEmits([
 15 |   'move',
 16 |   'reset',
 17 |   'resolve-fault',
 18 |   'start-patrol',
 19 |   'stop-patrol',
 20 |   'set-edit-mode',
 21 |   'fit-map',
 22 |   'toggle-detail',
 23 | ])
 24 | 
 25 | const editModes = [
 26 |   { key: 'pan', label: '平移' },
 27 |   { key: 'obstacle', label: '障碍' },
 28 |   { key: 'goal', label: '巡检点' },
 29 |   { key: 'start', label: '起点' },
 30 |   { key: 'charge', label: '充电' },
 31 | ]
 32 | 
 33 | function emitMove(dx, dy) {
 34 |   emit('move', { dx, dy })
 35 | }
 36 | </script>
 37 | 
 38 | <style scoped>
 39 | .mctrl-btn {
 40 |   @apply flex items-center justify-center w-9 h-9 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200 active:bg-gray-100 dark:active:bg-gray-800 transition-colors;
 41 | }
 42 | .safe-area-pb {
 43 |   padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
 44 | }
 45 | .no-scrollbar::-webkit-scrollbar {
 46 |   display: none;
 47 | }
 48 | .no-scrollbar {
 49 |   -ms-overflow-style: none;
 50 |   scrollbar-width: none;
```

第 43 页 / 共 60 页

---

<!-- 第 44 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | }
  2 | </style>
  3 | # ===== 文件：frontend/src/components/ThemeToggle.vue =====
  4 | <template>
  5 |   <button
  6 |     type="button"
  7 |     class="flex items-center justify-center w-9 h-9 rounded-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
  8 |     :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'"
  9 |     @click="toggle"
 10 |   >
 11 |     <svg v-if="isDark" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
 12 |       <circle cx="12" cy="12" r="5" />
 13 |       <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
 14 |     </svg>
 15 |     <svg v-else class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
 16 |       <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
 17 |     </svg>
 18 |   </button>
 19 | </template>
 20 | 
 21 | <script setup>
 22 | /**
 23 |  * 组件功能：深色 / 浅色模式切换按钮
 24 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 25 |  * 日期：2026-10-23
 26 |  * 版本：V1.0
 27 |  */
 28 | 
 29 | defineProps({
 30 |   isDark: {
 31 |     type: Boolean,
 32 |     required: true,
 33 |   },
 34 | })
 35 | 
 36 | const emit = defineEmits(['toggle'])
 37 | 
 38 | function toggle() {
 39 |   emit('toggle')
 40 | }
 41 | </script>
 42 | # ===== 文件：backend/tests/test_simulation_engine.py =====
 43 | """
 44 | 仿真引擎单元测试模块。
 45 | 
 46 | 模块功能：验证移动碰撞、电量消耗、巡检推进、异常检测等核心规则。
 47 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 48 | 日期：2026-10-24
 49 | 版本：V1.0
 50 | """
```

第 44 页 / 共 60 页

---

<!-- 第 45 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 
  2 | from app.core.constants import MODE_BLOCKED, MODE_MANUAL, MODE_PATROL
  3 | from app.services.simulation_engine import SimulationEngine
  4 | 
  5 | def make_engine() -> SimulationEngine:
  6 |     """构造带小型自定义地图的引擎，便于确定性断言。"""
  7 |     engine = SimulationEngine()
  8 |     engine.update_map(
  9 |         {
 10 |             "width": 5,
 11 |             "height": 5,
 12 |             "grid": [
 13 |                 [0, 0, 0, 0, 0],
 14 |                 [0, 1, 1, 1, 0],
 15 |                 [0, 0, 0, 0, 0],
 16 |                 [0, 1, 0, 1, 0],
 17 |                 [0, 0, 0, 0, 0],
 18 |             ],
 19 |             "start": [0, 0],
 20 |             "goals": [[4, 4]],
 21 |             "charge_point": [0, 0],
 22 |         }
 23 |     )
 24 |     return engine
 25 | 
 26 | def test_move_free_cell():
 27 |     """向空格移动应更新坐标。"""
 28 |     engine = make_engine()
 29 |     engine.move(1, 0)
 30 |     assert engine.x == 1 and engine.y == 0
 31 | 
 32 | def test_move_into_obstacle_sets_blocked():
 33 |     """撞上障碍物应保持原位且 mode 置为 blocked。"""
 34 |     engine = make_engine()
 35 |     engine.move(0, 1)  # 先下移到 (0,1)
 36 |     engine.move(1, 0)  # 撞向 (1,1) 的障碍
 37 |     assert engine.x == 0 and engine.y == 1
 38 |     assert engine.mode == MODE_BLOCKED
 39 | 
 40 | def test_battery_consumption():
 41 |     """移动每格消耗 0.2%，静止每 tick 消耗 0.02%。"""
 42 |     engine = make_engine()
 43 |     battery_before = engine.battery
 44 |     engine.move(1, 0)
 45 |     assert engine.battery == battery_before - 0.2
 46 |     battery_after_move = engine.battery
 47 |     engine.tick()
 48 |     assert abs(engine.battery - (battery_after_move - 0.02)) < 1e-6
 49 | 
 50 | def test_patrol_reaches_goal():
```

第 45 页 / 共 60 页

---

<!-- 第 46 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     """巡检应沿 A* 路径推进并最终到达目标。"""
  2 |     engine = make_engine()
  3 |     engine.start_patrol([[4, 4]])
  4 |     assert engine.patrol.running
  5 |     assert engine.mode == MODE_PATROL
  6 |     # 路径长度最多 8 步，推进 20 个 tick 必然完成。
  7 |     for _ in range(20):
  8 |         if not engine.patrol.running:
  9 |             break
 10 |         engine.tick()
 11 |     assert (engine.x, engine.y) == (4, 4)
 12 |     assert not engine.patrol.running
 13 | 
 14 | def test_low_battery_triggers_return_to_charge():
 15 |     """电量低于阈值应进入 charging 模式并规划回充电点路径。"""
 16 |     engine = make_engine()
 17 |     engine.battery = 5.0
 18 |     engine.tick()
 19 |     assert engine.mode == "charging"
 20 |     assert engine.path, "应规划出返航路径"
 21 | 
 22 | def test_anomaly_history_recorded():
 23 |     """异常检测应把事件写入历史列表。"""
 24 |     engine = make_engine()
 25 |     engine.battery = 10.0
 26 |     engine.tick()
 27 |     history = engine.get_anomalies()
 28 |     assert any(event["type"] == "low_battery" for event in history)
 29 | 
 30 | def test_reset_restores_state():
 31 |     """复位应回到起点、满电、手动模式。"""
 32 |     engine = make_engine()
 33 |     engine.move(1, 0)
 34 |     engine.reset()
 35 |     assert (engine.x, engine.y) == (0, 0)
 36 |     assert engine.battery == 100.0
 37 |     assert engine.mode == MODE_MANUAL
 38 | # ===== 文件：backend/tests/test_api.py =====
 39 | """
 40 | REST 接口集成测试模块。
 41 | 
 42 | 模块功能：使用 FastAPI TestClient 验证全部契约接口的请求/响应结构。
 43 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
 44 | 日期：2026-10-24
 45 | 版本：V1.0
 46 | """
 47 | 
 48 | import os
 49 | import tempfile
 50 | 
```

第 46 页 / 共 60 页

---

<!-- 第 47 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | # 使用临时日志文件，避免测试污染项目目录。
  2 | _tempdir = tempfile.mkdtemp()
  3 | os.environ["LOG_FILE"] = os.path.join(_tempdir, "test.log")
  4 | 
  5 | from fastapi.testclient import TestClient  # noqa: E402
  6 | 
  7 | from app.main import app  # noqa: E402
  8 | 
  9 | client = TestClient(app)
 10 | 
 11 | def test_health_endpoint():
 12 |     """健康检查接口应返回 ok。"""
 13 |     response = client.get("/api/v1/health")
 14 |     assert response.status_code == 200
 15 |     assert response.json()["status"] == "ok"
 16 | 
 17 | def test_get_map_contract():
 18 |     """GET /map 应返回契约要求的全部字段。"""
 19 |     response = client.get("/api/v1/map")
 20 |     assert response.status_code == 200
 21 |     data = response.json()
 22 |     assert set(data.keys()) == {"width", "height", "grid", "start", "goals", "charge_point"}
 23 | 
 24 | def test_put_map_roundtrip():
 25 |     """PUT /map 提交后应能 GET 到相同数据。"""
 26 |     new_map = {
 27 |         "width": 4,
 28 |         "height": 4,
 29 |         "grid": [[0] * 4 for _ in range(4)],
 30 |         "start": [0, 0],
 31 |         "goals": [[3, 3]],
 32 |         "charge_point": [0, 0],
 33 |     }
 34 |     put = client.put("/api/v1/map", json=new_map)
 35 |     assert put.status_code == 200
 36 |     got = client.get("/api/v1/map").json()
 37 |     assert got["width"] == 4
 38 |     assert got["grid"] == new_map["grid"]
 39 | 
 40 | def test_move_endpoint():
 41 |     """POST /robot/move 应返回 state 帧结构。"""
 42 |     response = client.post("/api/v1/robot/move", json={"dx": 1, "dy": 0})
 43 |     assert response.status_code == 200
 44 |     data = response.json()
 45 |     assert set(data.keys()) >= {"x", "y", "theta", "battery", "speed", "mode", "path", "sensors"}
 46 |     assert set(data["sensors"].keys()) == {"front", "left", "right", "temperature"}
 47 | 
 48 | def test_path_endpoint():
 49 |     """GET /path 应返回 A* 结果三元组。"""
 50 |     response = client.get("/api/v1/path", params={"start": "0,0", "goal": "3,3"})
```

第 47 页 / 共 60 页

---

<!-- 第 48 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     assert response.status_code == 200
  2 |     data = response.json()
  3 |     assert set(data.keys()) == {"path", "visited_count", "cost"}
  4 |     assert data["path"][0] == [0, 0]
  5 |     assert data["path"][-1] == [3, 3]
  6 | 
  7 | def test_patrol_lifecycle():
  8 |     """巡检启动/查询/停止全流程。"""
  9 |     start = client.post("/api/v1/patrol/start", json={"goals": [[3, 3]]})
 10 |     assert start.status_code == 200
 11 |     assert start.json()["running"] is True
 12 | 
 13 |     status = client.get("/api/v1/patrol/status").json()
 14 |     assert status["running"] is True
 15 |     assert status["current_goal"] == [3, 3]
 16 | 
 17 |     stop = client.post("/api/v1/patrol/stop")
 18 |     assert stop.status_code == 200
 19 |     assert stop.json()["running"] is False
 20 | 
 21 | def test_sensors_and_anomalies():
 22 |     """传感器与异常接口应可访问。"""
 23 |     sensors = client.get("/api/v1/sensors/latest")
 24 |     assert sensors.status_code == 200
 25 |     anomalies = client.get("/api/v1/events/anomalies")
 26 |     assert anomalies.status_code == 200
 27 |     assert isinstance(anomalies.json(), list)
 28 | 
 29 | def test_remove_obstacle_endpoint():
 30 |     """一键排障接口应能找到建议拆除的障碍。"""
 31 |     # 构造被单格障碍阻断的地图。
 32 |     grid = [[0] * 3 for _ in range(3)]
 33 |     grid[0][1] = 1
 34 |     grid[1][1] = 1
 35 |     grid[2][1] = 1
 36 |     client.put(
 37 |         "/api/v1/map",
 38 |         json={"width": 3, "height": 3, "grid": grid, "start": [0, 0], "goals": [], "charge_point": [0, 0]},
 39 |     )
 40 |     response = client.post("/api/v1/map/remove-obstacle", json=[2, 0])
 41 |     assert response.status_code == 200
 42 |     data = response.json()
 43 |     assert data["remove"] is not None
 44 |     assert data["remove"][0] == 1  # 应建议拆除中间那列障碍之一。
 45 | # ===== 文件：backend/tests/test_astar.py =====
 46 | """
 47 | A* 算法单元测试模块。
 48 | 
 49 | 模块功能：验证 Python 版 A* 的路径正确性、避障性与返回结构一致性。
 50 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
```

第 48 页 / 共 60 页

---

<!-- 第 49 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | 日期：2026-10-24
  2 | 版本：V1.0
  3 | """
  4 | 
  5 | from app.algorithms.astar import astar
  6 | 
  7 | def test_straight_line_path():
  8 |     """空旷地图上应返回直线路径，代价等于曼哈顿距离。"""
  9 |     grid = [[0] * 5 for _ in range(5)]
 10 |     result = astar(grid, (0, 0), (4, 0))
 11 |     assert result["path"][0] == [0, 0]
 12 |     assert result["path"][-1] == [4, 0]
 13 |     assert result["cost"] == 4
 14 |     assert len(result["path"]) == 5
 15 | 
 16 | def test_obstacle_avoidance():
 17 |     """中间有墙时应绕行且不穿过障碍。"""
 18 |     grid = [[0] * 3 for _ in range(3)]
 19 |     grid[0][1] = 1  # 在 (1,0) 放障碍，迫使绕行。
 20 |     result = astar(grid, (0, 0), (2, 0))
 21 |     assert result["path"], "应能找到绕行路径"
 22 |     for x, y in result["path"]:
 23 |         assert grid[y][x] == 0, "路径不得穿过障碍物"
 24 | 
 25 | def test_unreachable_returns_empty():
 26 |     """目标被墙完全包围时应返回空路径。"""
 27 |     grid = [[0] * 5 for _ in range(5)]
 28 |     grid[1][1] = 1
 29 |     grid[1][2] = 1
 30 |     grid[1][3] = 1
 31 |     grid[2][1] = 1
 32 |     grid[2][3] = 1
 33 |     grid[3][1] = 1
 34 |     grid[3][2] = 1
 35 |     grid[3][3] = 1
 36 |     result = astar(grid, (0, 0), (2, 2))
 37 |     assert result["path"] == []
 38 | 
 39 | def test_start_or_goal_blocked():
 40 |     """起点或目标是障碍时应返回空路径。"""
 41 |     grid = [[0, 1], [0, 0]]
 42 |     assert astar(grid, (1, 0), (0, 0))["path"] == []
 43 |     assert astar(grid, (0, 0), (1, 0))["path"] == []
 44 | 
 45 | def test_result_structure_matches_contract():
 46 |     """返回结构必须包含 path/visited_count/cost 三个字段。"""
 47 |     grid = [[0] * 4 for _ in range(4)]
 48 |     result = astar(grid, (0, 0), (3, 3))
 49 |     assert set(result.keys()) == {"path", "visited_count", "cost"}
 50 | # ===== 文件：backend/tests/test_anomaly_ml.py =====
```

第 49 页 / 共 60 页

---

<!-- 第 50 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 | """
  2 | 机器学习异常检测测试模块。
  3 | 
  4 | 模块功能：在合成数据上评估 IsolationForest 检测器的冷启动、误报率、
  5 | 召回率与推理速度，并验证规则基线、工厂切换与传感器故障注入。实测数字
  6 | 用于回填 docs/ai.md §8。依赖 scikit-learn，未安装时自动跳过（基础部署
  7 | 可不装 ML 重依赖，默认走规则基线）。
  8 | 作者：智能巡检机器人二维仿真系统 V1.0 开发组
  9 | 日期：2026-10-24
 10 | 版本：V1.0
 11 | """
 12 | 
 13 | import random
 14 | import time
 15 | 
 16 | import pytest
 17 | 
 18 | np = pytest.importorskip("numpy")
 19 | pytest.importorskip("sklearn")
 20 | 
 21 | from app.core.constants import ANOMALY_ML, ANOMALY_OVERHEAT, ANOMALY_SENSOR_FAULT  # noqa: E402
 22 | from app.services.anomaly import MLAnomalyDetector, RuleAnomalyDetector, create_detector  # noqa: E402
 23 | from app.services.sensors import SensorSimulator  # noqa: E402
 24 | 
 25 | def _normal_reading(rng: random.Random, battery: float, moving: bool = True) -> dict:
 26 |     """生成一条正常工况读数：电量缓降、温度基线、三向距离平滑。"""
 27 |     return {
 28 |         "battery": round(battery, 2),
 29 |         "temperature": round(35.0 + rng.uniform(0, 4) + (1.0 if moving else 0.0), 2),
 30 |         "front": round(rng.uniform(1.5, 4.0), 2),
 31 |         "left": round(rng.uniform(1.5, 4.0), 2),
 32 |         "right": round(rng.uniform(1.5, 4.0), 2),
 33 |         "position": [3, 3],
 34 |         "mode": "patrol",
 35 |     }
 36 | 
 37 | def _combo_fault(rng: random.Random, battery: float, kind: str) -> dict:
 38 |     """
 39 |     生成一条组合型异常读数（分布内的罕见组合，IsolationForest 的靶子）。
 40 | 
 41 |     与单维超范围故障不同，组合型故障每一维都还在合理量程内，但组合本身
 42 |     在正常工况下几乎不出现，正适合孤立森林捕捉。
 43 |     """
 44 |     reading = _normal_reading(rng, battery)
 45 |     if kind == "blind":  # 三向探头集体失灵（同时贴低）
 46 |         reading["front"] = round(rng.uniform(0.1, 0.6), 2)
 47 |         reading["left"] = round(rng.uniform(0.1, 0.6), 2)
 48 |         reading["right"] = round(rng.uniform(0.1, 0.6), 2)
 49 |     elif kind == "temp_dist":  # 温度偏高 + 前向贴障
 50 |         reading["temperature"] = round(rng.uniform(43, 47), 2)
```

第 50 页 / 共 60 页

---

<!-- 第 51 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         reading["front"] = round(rng.uniform(0.2, 0.8), 2)
  2 |     elif kind == "hot_lowbat":  # 温度偏高 + 电量偏低 同时发生
  3 |         reading["temperature"] = round(rng.uniform(42, 46), 2)
  4 |         reading["battery"] = round(rng.uniform(55, 62), 2)
  5 |     return reading
  6 | 
  7 | def _train(n_normal: int = 400) -> tuple[MLAnomalyDetector, random.Random]:
  8 |     """用正常数据完成冷启动，返回就绪的检测器。"""
  9 |     rng = random.Random(7)
 10 |     det = MLAnomalyDetector(coldstart_ticks=n_normal)
 11 |     battery = 100.0
 12 |     for _ in range(n_normal):
 13 |         det.update(_normal_reading(rng, battery))
 14 |         battery = max(60.0, battery - 0.1)
 15 |     assert det._model is not None, "冷启动后应完成训练"
 16 |     return det, rng
 17 | 
 18 | # ---------- 规则基线 ----------
 19 | 
 20 | def test_rule_low_battery():
 21 |     det = RuleAnomalyDetector()
 22 |     events = det.update(_normal_reading(random.Random(1), 10.0))
 23 |     assert any(e["type"] == ANOMALY_OVERHEAT for e in events) is False
 24 |     assert any("电量" in e["message"] for e in events)
 25 | 
 26 | def test_rule_overheat():
 27 |     det = RuleAnomalyDetector()
 28 |     reading = _normal_reading(random.Random(1), 80.0)
 29 |     reading["temperature"] = 70.0
 30 |     events = det.update(reading)
 31 |     assert any(e["type"] == ANOMALY_OVERHEAT for e in events)
 32 | 
 33 | def test_rule_sensor_fault():
 34 |     det = RuleAnomalyDetector()
 35 |     reading = _normal_reading(random.Random(1), 80.0)
 36 |     reading["front"] = 0.2
 37 |     reading["left"] = 3.8  # 相邻读数差 > 3m 触发突变。
 38 |     events = det.update(reading)
 39 |     assert any(e["type"] == ANOMALY_SENSOR_FAULT for e in events)
 40 | 
 41 | def test_factory_switches_strategy():
 42 |     assert isinstance(create_detector("rule"), RuleAnomalyDetector)
 43 |     assert isinstance(create_detector("ml"), MLAnomalyDetector)
 44 |     assert isinstance(create_detector("bogus"), RuleAnomalyDetector)  # 未知值回退规则。
 45 | 
 46 | # ---------- 机器学习 ----------
 47 | 
 48 | def test_ml_coldstart_trains_model():
 49 |     det, _ = _train(200)
 50 |     assert det._model is not None
```

第 51 页 / 共 60 页

---

<!-- 第 52 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     assert det._threshold is not None  # 阈值已自动校准。
  2 | 
  3 | def test_ml_false_alarm_rate():
  4 |     det, rng = _train(400)
  5 |     battery = 100.0
  6 |     hits = 0
  7 |     total = 400
  8 |     for _ in range(total):
  9 |         if det.is_anomaly(_normal_reading(rng, battery)):
 10 |             hits += 1
 11 |         battery = max(60.0, battery - 0.05)
 12 |     rate = hits / total
 13 |     assert rate < 0.05, f"正常段误报率应 < 5%，实测 {rate:.1%}"
 14 | 
 15 | def test_ml_recall_on_combo_faults():
 16 |     det, rng = _train(400)
 17 |     # "blind"（三向探头集体失灵）是最典型的分布内组合型异常，孤立森林应稳定捕获。
 18 |     detected = sum(1 for _ in range(100) if det.is_anomaly(_combo_fault(rng, 90.0, "blind")))
 19 |     recall = detected / 100
 20 |     assert recall > 0.90, f"组合型故障（blind）召回率应 > 90%，实测 {recall:.0%}"
 21 | 
 22 | def test_ml_inference_speed():
 23 |     det, rng = _train(200)
 24 |     reading = _normal_reading(rng, 80.0)
 25 |     det.decision_score(reading)  # 预热。
 26 |     start = time.perf_counter()
 27 |     for _ in range(200):
 28 |         det.decision_score(reading)
 29 |     per_call = (time.perf_counter() - start) / 200
 30 |     assert per_call < 0.005, f"单次推理应 < 5ms，实测 {per_call * 1000:.2f}ms"
 31 | 
 32 | def test_ml_update_emits_event_once():
 33 |     det, rng = _train(200)
 34 |     battery = 90.0
 35 |     events: list[dict] = []
 36 |     for _ in range(10):  # 正常段（电量递减，落在训练分布内）不报警。
 37 |         events += det.update(_normal_reading(rng, battery))
 38 |         battery = max(60.0, battery - 1.0)
 39 |     assert not any(e["type"] == ANOMALY_ML for e in events)
 40 |     events += det.update(_combo_fault(rng, battery, "blind"))  # 强组合故障触发一次。
 41 |     assert any(e["type"] == ANOMALY_ML for e in events)
 42 |     assert det.get_history()[-1]["type"] == ANOMALY_ML
 43 | 
 44 | # ---------- 传感器故障注入 ----------
 45 | 
 46 | def test_sensor_fault_injection():
 47 |     grid = [[0] * 10 for _ in range(10)]
 48 |     sim = SensorSimulator(grid)
 49 |     random.seed(3)
 50 |     clean = sim.read_all(5, 5, 0.0, 80.0, True)  # 关闭时的干净基线。
```

第 52 页 / 共 60 页

---

<!-- 第 53 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     sim.fault_prob = 1.0  # 强制每次注入。
  2 |     changed = 0
  3 |     for _ in range(100):
  4 |         r = sim.read_all(5, 5, 0.0, 80.0, True)
  5 |         if (r["front"], r["left"], r["right"]) != (clean["front"], clean["left"], clean["right"]):
  6 |             changed += 1
  7 |     assert changed >= 95, f"fault_prob=1.0 时几乎每次读数都应被扰动，实测 {changed}/100"
  8 | # ===== 文件：frontend/src/services/__tests__/astar.test.js =====
  9 | /**
 10 |  * 模块功能：A* 算法单元测试
 11 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 12 |  * 日期：2026-10-23
 13 |  * 版本：V1.0
 14 |  */
 15 | 
 16 | import { describe, it, expect } from 'vitest'
 17 | import { astar } from '../astar.js'
 18 | 
 19 | describe('astar', () => {
 20 |   it('应在无障碍地图中返回直线最短路径', () => {
 21 |     const grid = [
 22 |       [0, 0, 0],
 23 |       [0, 0, 0],
 24 |       [0, 0, 0],
 25 |     ]
 26 |     const result = astar(grid, [0, 0], [2, 2])
 27 |     expect(result.path).toEqual([
 28 |       [0, 0],
 29 |       [1, 0],
 30 |       [2, 0],
 31 |       [2, 1],
 32 |       [2, 2],
 33 |     ])
 34 |     expect(result.cost).toBe(4)
 35 |     expect(result.visited_count).toBeGreaterThan(0)
 36 |   })
 37 | 
 38 |   it('应能绕过障碍物到达目标', () => {
 39 |     const grid = [
 40 |       [0, 0, 0],
 41 |       [1, 1, 0],
 42 |       [0, 0, 0],
 43 |     ]
 44 |     const result = astar(grid, [0, 0], [2, 2])
 45 |     expect(result.path.length).toBeGreaterThan(0)
 46 |     expect(result.path[result.path.length - 1]).toEqual([2, 2])
 47 |   })
 48 | 
 49 |   it('当目标不可达时应返回空路径', () => {
 50 |     const grid = [
```

第 53 页 / 共 60 页

---

<!-- 第 54 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |       [0, 1, 0],
  2 |       [0, 1, 0],
  3 |       [0, 1, 0],
  4 |     ]
  5 |     const result = astar(grid, [0, 0], [2, 2])
  6 |     expect(result.path).toEqual([])
  7 |     expect(result.cost).toBe(0)
  8 |   })
  9 | 
 10 |   it('当起点或终点为障碍物时应返回空路径', () => {
 11 |     const grid = [
 12 |       [1, 0],
 13 |       [0, 0],
 14 |     ]
 15 |     expect(astar(grid, [0, 0], [1, 1]).path).toEqual([])
 16 |     expect(astar(grid, [1, 1], [0, 0]).path).toEqual([])
 17 |   })
 18 | })
 19 | # ===== 文件：frontend/src/services/__tests__/simulatedService.test.js =====
 20 | /**
 21 |  * 模块功能：本地仿真器服务单元测试
 22 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 23 |  * 日期：2026-10-23
 24 |  * 版本：V1.0
 25 |  */
 26 | 
 27 | import { describe, it, expect, beforeEach, afterEach } from 'vitest'
 28 | import { SimulatedService } from '../simulatedService.js'
 29 | 
 30 | describe('SimulatedService', () => {
 31 |   let service
 32 | 
 33 |   beforeEach(() => {
 34 |     service = new SimulatedService()
 35 |     service._stopLoop()
 36 |   })
 37 | 
 38 |   afterEach(() => {
 39 |     service._stopLoop()
 40 |   })
 41 | 
 42 |   it('应返回合法地图对象', () => {
 43 |     const map = service.getMap()
 44 |     expect(map.width).toBeGreaterThan(0)
 45 |     expect(map.height).toBeGreaterThan(0)
 46 |     expect(map.grid.length).toBe(map.height)
 47 |     expect(map.start).toHaveLength(2)
 48 |     expect(map.charge_point).toHaveLength(2)
 49 |   })
 50 | 
```

第 54 页 / 共 60 页

---

<!-- 第 55 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |   it('复位后机器人应位于起点且电量满格', () => {
  2 |     service.move(1, 0)
  3 |     service.reset()
  4 |     const map = service.getMap()
  5 |     expect(service._state.x).toBe(map.start[0])
  6 |     expect(service._state.y).toBe(map.start[1])
  7 |     expect(service._state.battery).toBe(100)
  8 |     expect(service._state.mode).toBe('manual')
  9 |   })
 10 | 
 11 |   it('computePath 应返回包含路径与访问节点数的对象', () => {
 12 |     const map = service.getMap()
 13 |     const result = service.computePath(map.start, map.goals[0])
 14 |     expect(result).toHaveProperty('path')
 15 |     expect(result).toHaveProperty('visited_count')
 16 |     expect(result).toHaveProperty('cost')
 17 |     if (result.path.length > 0) {
 18 |       expect(result.path[result.path.length - 1]).toEqual(map.goals[0])
 19 |     }
 20 |   })
 21 | 
 22 |   it('startPatrol 后巡检状态应为运行中', () => {
 23 |     service.startPatrol()
 24 |     const status = service.getPatrolStatus()
 25 |     expect(status.running).toBe(true)
 26 |     expect(service._patrol.totalGoals).toBeGreaterThan(0)
 27 |   })
 28 | 
 29 |   it('停止巡检后状态应恢复为 manual', () => {
 30 |     service.startPatrol()
 31 |     service.stopPatrol()
 32 |     expect(service.getPatrolStatus().running).toBe(false)
 33 |     expect(service._state.mode).toBe('manual')
 34 |   })
 35 | 
 36 |   it('onState 回调应接收到符合协议的状态帧', () => {
 37 |     return new Promise((resolve) => {
 38 |       let unsubscribe = null
 39 |       const callback = (frame) => {
 40 |         expect(frame.type).toBe('state')
 41 |         expect(frame.data).toHaveProperty('x')
 42 |         expect(frame.data).toHaveProperty('y')
 43 |         expect(frame.data).toHaveProperty('theta')
 44 |         expect(frame.data).toHaveProperty('battery')
 45 |         expect(frame.data).toHaveProperty('speed')
 46 |         expect(frame.data).toHaveProperty('mode')
 47 |         expect(frame.data).toHaveProperty('path')
 48 |         expect(frame.data).toHaveProperty('sensors')
 49 |         expect(frame.data.sensors).toHaveProperty('front')
 50 |         expect(frame.data.sensors).toHaveProperty('left')
```

第 55 页 / 共 60 页

---

<!-- 第 56 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |         expect(frame.data.sensors).toHaveProperty('right')
  2 |         expect(frame.data.sensors).toHaveProperty('temperature')
  3 |         if (unsubscribe) {
  4 |           unsubscribe()
  5 |         }
  6 |         resolve()
  7 |       }
  8 |       unsubscribe = service.onState(callback)
  9 |     })
 10 |   })
 11 | })
 12 | # ===== 文件：frontend/src/services/__tests__/features.test.js =====
 13 | /**
 14 |  * 模块功能：新增功能单元测试（一键排障 / 内置地图 / 地图导入导出 / 机器人形象）
 15 |  * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 16 |  * 日期：2026-10-24
 17 |  * 版本：V1.0
 18 |  */
 19 | 
 20 | import { describe, it, expect, beforeEach, afterEach } from 'vitest'
 21 | import { SimulatedService } from '../simulatedService.js'
 22 | import { MAP_PRESETS, getPreset } from '../mapPresets.js'
 23 | import { validateMap } from '../../utils/mapIO.js'
 24 | import { getAvatar, setAvatar, clearAvatar, readAvatarFile } from '../../utils/robotAvatar.js'
 25 | 
 26 | describe('一键排障 resolveFault', () => {
 27 |   let service
 28 |   let events
 29 | 
 30 |   beforeEach(() => {
 31 |     localStorage.clear()
 32 |     service = new SimulatedService()
 33 |     service._stopLoop()
 34 |     events = []
 35 |     service.onEvent((frame) => events.push(frame))
 36 |   })
 37 | 
 38 |   afterEach(() => {
 39 |     service._stopLoop()
 40 |     localStorage.clear()
 41 |   })
 42 | 
 43 |   it('机器人卡住时应清除正前方障碍并恢复手动模式', () => {
 44 |     // 起点 [1,1] 面向 +x（theta=0），在 [3,1] 放障碍后向右撞上去
 45 |     service.move(1, 0)
 46 |     expect(service._state.x).toBe(2)
 47 |     service._map.grid[1][3] = 1
 48 |     service.move(1, 0)
 49 |     expect(service._state.mode).toBe('blocked')
 50 | 
```

第 56 页 / 共 60 页

---

<!-- 第 57 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     service.resolveFault()
  2 | 
  3 |     expect(service._map.grid[1][3]).toBe(0)
  4 |     expect(service._state.mode).toBe('manual')
  5 |     const notices = events.filter((f) => f.type === 'notice')
  6 |     expect(notices[notices.length - 1].data.message).toContain('已排除前方障碍')
  7 |   })
  8 | 
  9 |   it('未卡住时调用只应推送提示且不改变地图', () => {
 10 |     const before = JSON.stringify(service._map.grid)
 11 |     service.resolveFault()
 12 |     const notices = events.filter((f) => f.type === 'notice')
 13 |     expect(notices[notices.length - 1].data.message).toContain('当前无阻塞故障')
 14 |     expect(JSON.stringify(service._map.grid)).toBe(before)
 15 |   })
 16 | 
 17 |   it('正前方是边界墙（无 obstacle 格可拆）时也应恢复手动模式', () => {
 18 |     // 直接撞地图上边界：theta 初始为 0 时先转身向上再撞
 19 |     service._state.theta = -Math.PI / 2
 20 |     service._state.x = 1
 21 |     service._state.y = 1
 22 |     service.move(0, -1) // 目标 [1,0] 是边界墙
 23 |     expect(service._state.mode).toBe('blocked')
 24 | 
 25 |     service.resolveFault()
 26 |     expect(service._state.mode).toBe('manual')
 27 |   })
 28 | })
 29 | 
 30 | describe('内置地图预设', () => {
 31 |   let service
 32 | 
 33 |   beforeEach(() => {
 34 |     localStorage.clear()
 35 |     service = new SimulatedService()
 36 |     service._stopLoop()
 37 |   })
 38 | 
 39 |   afterEach(() => {
 40 |     service._stopLoop()
 41 |     localStorage.clear()
 42 |   })
 43 | 
 44 |   it('应提供三张预设且关键点均不在障碍上', () => {
 45 |     expect(MAP_PRESETS).toHaveLength(3)
 46 |     for (const preset of MAP_PRESETS) {
 47 |       const map = getPreset(preset.key)
 48 |       expect(map).not.toBeNull()
 49 |       expect(map.grid).toHaveLength(map.height)
 50 |       expect(map.grid[0]).toHaveLength(map.width)
```

第 57 页 / 共 60 页

---

<!-- 第 58 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |       // 起点 / 充电点 / 巡检点必须可通行
  2 |       expect(map.grid[map.start[1]][map.start[0]]).toBe(0)
  3 |       expect(map.grid[map.charge_point[1]][map.charge_point[0]]).toBe(0)
  4 |       for (const goal of map.goals) {
  5 |         expect(map.grid[goal[1]][goal[0]]).toBe(0)
  6 |       }
  7 |     }
  8 |   })
  9 | 
 10 |   it('getPreset 应返回深拷贝，改写不影响预设本体', () => {
 11 |     const a = getPreset('factory')
 12 |     a.grid[1][1] = 1
 13 |     a.width = 999
 14 |     const b = getPreset('factory')
 15 |     expect(b.grid[1][1]).toBe(0)
 16 |     expect(b.width).toBe(30)
 17 |   })
 18 | 
 19 |   it('切换预设后地图尺寸、机器人位置与预设标识应同步更新', () => {
 20 |     service.loadPreset('warehouse')
 21 |     const map = service.getMap()
 22 |     expect(map.width).toBe(24)
 23 |     expect(map.height).toBe(16)
 24 |     expect(service.getPresetKey()).toBe('warehouse')
 25 |     // 机器人复位到新地图起点
 26 |     expect(service._state.x).toBe(map.start[0])
 27 |     expect(service._state.y).toBe(map.start[1])
 28 |     expect(service._state.mode).toBe('manual')
 29 | 
 30 |     service.loadPreset('dense')
 31 |     expect(service.getMap().width).toBe(28)
 32 |     expect(service.getPresetKey()).toBe('dense')
 33 |   })
 34 | 
 35 |   it('切换不存在预设时应推送提示且保持原地图', () => {
 36 |     const before = service.getMap().width
 37 |     service.loadPreset('not-exist')
 38 |     expect(service.getMap().width).toBe(before)
 39 |   })
 40 | 
 41 |   it('手动编辑地图后预设标识应清除', () => {
 42 |     service.loadPreset('factory')
 43 |     expect(service.getPresetKey()).toBe('factory')
 44 |     service.updateMap(service.getMap())
 45 |     expect(service.getPresetKey()).toBeNull()
 46 |   })
 47 | 
 48 |   it('预设应持久化到 localStorage，新建服务可恢复', () => {
 49 |     service.loadPreset('dense')
 50 |     const restored = new SimulatedService()
```

第 58 页 / 共 60 页

---

<!-- 第 59 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     restored._stopLoop()
  2 |     expect(restored.getPresetKey()).toBe('dense')
  3 |     expect(restored.getMap().width).toBe(28)
  4 |   })
  5 | })
  6 | 
  7 | describe('地图导入校验 validateMap', () => {
  8 |   /** 构造一张最小合法地图。 */
  9 |   function validMap() {
 10 |     const width = 8
 11 |     const height = 6
 12 |     const grid = Array.from({ length: height }, () => Array(width).fill(0))
 13 |     return {
 14 |       width,
 15 |       height,
 16 |       grid,
 17 |       start: [1, 1],
 18 |       goals: [[6, 4]],
 19 |       charge_point: [6, 1],
 20 |     }
 21 |   }
 22 | 
 23 |   it('合法地图应通过且剔除多余字段', () => {
 24 |     const map = validMap()
 25 |     map.extra = 'should be removed'
 26 |     const result = validateMap(map)
 27 |     expect(result.ok).toBe(true)
 28 |     expect(result.map).not.toHaveProperty('extra')
 29 |   })
 30 | 
 31 |   it('栅格行数不足应拒绝', () => {
 32 |     const map = validMap()
 33 |     map.grid = map.grid.slice(0, 3)
 34 |     expect(validateMap(map).ok).toBe(false)
 35 |   })
 36 | 
 37 |   it('栅格含非法值（2）应拒绝', () => {
 38 |     const map = validMap()
 39 |     map.grid[2][2] = 2
 40 |     expect(validateMap(map).ok).toBe(false)
 41 |   })
 42 | 
 43 |   it('起点位于障碍上应拒绝', () => {
 44 |     const map = validMap()
 45 |     map.grid[1][1] = 1
 46 |     expect(validateMap(map).ok).toBe(false)
 47 |   })
 48 | 
 49 |   it('巡检点越界应拒绝', () => {
 50 |     const map = validMap()
```

第 59 页 / 共 60 页

---

<!-- 第 60 页 / 共 60 页 -->

**智能巡检机器人二维仿真系统 V1.0 源代码**

```
  1 |     map.goals = [[99, 4]]
  2 |     expect(validateMap(map).ok).toBe(false)
  3 |   })
  4 | 
  5 |   it('充电点位于障碍上应拒绝', () => {
  6 |     const map = validMap()
  7 |     map.grid[1][6] = 1
  8 |     expect(validateMap(map).ok).toBe(false)
  9 |   })
 10 | 
 11 |   it('宽高非法应拒绝', () => {
 12 |     const map = validMap()
 13 |     map.width = 2
 14 |     expect(validateMap(map).ok).toBe(false)
 15 |   })
 16 | })
 17 | 
 18 | describe('机器人形象存储', () => {
 19 |   beforeEach(() => {
 20 |     localStorage.clear()
 21 |   })
 22 | 
 23 |   afterEach(() => {
 24 |     localStorage.clear()
 25 |   })
 26 | 
 27 |   it('保存 / 读取 / 清除应形成闭环', () => {
 28 |     expect(getAvatar()).toBeNull()
 29 |     setAvatar('data:image/png;base64,AAAA')
 30 |     expect(getAvatar()).toBe('data:image/png;base64,AAAA')
 31 |     clearAvatar()
 32 |     expect(getAvatar()).toBeNull()
 33 |   })
 34 | 
 35 |   it('readAvatarFile 应接受图片文件并返回 data URL', async () => {
 36 |     const file = new File(['fake-bytes'], 'robot.png', { type: 'image/png' })
 37 |     const dataUrl = await readAvatarFile(file)
 38 |     expect(dataUrl.startsWith('data:image/png;base64,')).toBe(true)
 39 |   })
 40 | 
 41 |   it('readAvatarFile 应拒绝非图片文件', async () => {
 42 |     const file = new File(['x'], 'map.json', { type: 'application/json' })
 43 |     await expect(readAvatarFile(file)).rejects.toThrow('图片文件')
 44 |   })
 45 | 
 46 |   it('readAvatarFile 应拒绝超过 2MB 的图片', async () => {
 47 |     const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'big.png', { type: 'image/png' })
 48 |     await expect(readAvatarFile(big)).rejects.toThrow('2MB')
 49 |   })
 50 | })
```

第 60 页 / 共 60 页

---
