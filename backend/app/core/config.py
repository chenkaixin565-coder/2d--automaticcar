"""
配置模块。

模块功能：集中管理应用运行所需的可配置参数。所有默认值来自
`shared/simulation-rules.json`（与前端共用同一份口径），环境变量只做覆盖；
禁止在代码中硬编码密钥或内网地址。

作者：智能巡检机器人二维仿真系统 V2.2.0 开发组
日期：2026-10-26
版本：V2.2.0
"""

import os
from dataclasses import dataclass

from app.core.shared import load_rules

# 共享规则：后端与前端唯一的数值来源。
RULES = load_rules()


def _env_float(name: str, default: float) -> float:
    """读取浮点型环境变量，非法值回退默认值，避免启动即崩。"""
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    """读取整型环境变量，非法值回退默认值。"""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return int(default)


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔型环境变量（1/true/yes/on 视为真）。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """应用全局配置。"""

    # ---------- 仿真节奏与电量 ----------
    tick_interval_ms: int = _env_int("TICK_INTERVAL_MS", RULES["tick_interval_ms"])
    battery_move_cost: float = _env_float("BATTERY_MOVE_COST", RULES["battery"]["move_cost"])
    battery_idle_cost: float = _env_float("BATTERY_IDLE_COST", RULES["battery"]["idle_cost"])
    low_battery_threshold: float = _env_float("LOW_BATTERY_THRESHOLD", RULES["battery"]["low_threshold"])
    clear_obstacle_cost: float = _env_float("CLEAR_OBSTACLE_COST", RULES["battery"]["clear_cost"])
    charge_rate: float = _env_float("CHARGE_RATE", RULES["battery"]["charge_rate"])

    # ---------- 传感器 ----------
    cell_distance_m: float = _env_float("CELL_DISTANCE_M", RULES["sensor"]["cell_meters"])
    sensor_range_m: float = _env_float("SENSOR_RANGE_M", RULES["sensor"]["range_meters"])
    sensor_fault_delta: float = _env_float("SENSOR_FAULT_DELTA", RULES["sensor"]["fault_delta"])
    sensor_fault_cooldown_s: float = _env_float(
        "SENSOR_FAULT_COOLDOWN_S", RULES["sensor"]["fault_cooldown_s"]
    )
    sensor_fault_prob: float = _env_float("SENSOR_FAULT_PROB", RULES["sensor"]["fault_prob"])

    # ---------- 温度 ----------
    base_temperature: float = _env_float("BASE_TEMPERATURE", RULES["temperature"]["base"])
    temperature_rise_per_move: float = _env_float(
        "TEMP_RISE_PER_MOVE", RULES["temperature"]["rise_per_move"]
    )
    temperature_cool_rate: float = _env_float(
        "TEMP_COOL_RATE", RULES["temperature"]["cool_per_tick"]
    )
    temperature_max: float = _env_float("TEMPERATURE_MAX", RULES["temperature"]["max"])
    temperature_noise: float = _env_float("TEMPERATURE_NOISE", RULES["temperature"]["noise"])
    overheat_threshold: float = _env_float(
        "OVERHEAT_THRESHOLD", RULES["temperature"]["overheat_threshold"]
    )

    # ---------- 异常检测 ----------
    anomaly_strategy: str = os.getenv("ANOMALY_STRATEGY", "rule")
    anomaly_history_max: int = _env_int(
        "ANOMALY_HISTORY_MAX", RULES["maps"]["anomaly_history_max"]
    )
    ml_coldstart_ticks: int = _env_int("ML_COLDSTART_TICKS", 500)
    ml_window_size: int = _env_int("ML_WINDOW_SIZE", 120)
    ml_retrain_seconds: int = _env_int("ML_RETRAIN_SECONDS", 60)
    ml_score_percentile: float = _env_float("ML_SCORE_PERCENTILE", 2.0)
    ml_score_threshold: str = os.getenv("ML_SCORE_THRESHOLD", "")
    ml_contamination: str = os.getenv("ML_CONTAMINATION", "auto")

    # ---------- 地图 ----------
    default_width: int = _env_int("DEFAULT_WIDTH", RULES["maps"]["default_width"])
    default_height: int = _env_int("DEFAULT_HEIGHT", RULES["maps"]["default_height"])
    default_start: tuple = (1, 1)
    default_charge_point: tuple = (1, 1)
    min_map_size: int = _env_int("MIN_MAP_SIZE", RULES["maps"]["min_size"])
    max_map_size: int = _env_int("MAX_MAP_SIZE", RULES["maps"]["max_size"])
    pending_limit: int = _env_int("PENDING_LIMIT", RULES["maps"]["pending_limit"])

    # ---------- 访问控制（V2.2.0） ----------
    # 操作密钥：留空 = 开放演示模式（写操作放行，启动日志会警告）。
    # 设置后，所有写接口（POST/PUT/PATCH/DELETE）与 WebSocket 指令都需要
    # X-API-Key 请求头（WebSocket 用 ?api_key= 查询参数）。
    operator_key: str = os.getenv("OPERATOR_KEY", "")
    # 每个客户端每分钟允许的请求数；0 表示关闭限流。
    rate_limit_per_minute: int = _env_int("RATE_LIMIT_PER_MINUTE", 240)
    # 允许的瞬时突发量。
    rate_limit_burst: int = _env_int("RATE_LIMIT_BURST", 80)
    # 部署在反向代理后面时，从 X-Forwarded-For 取真实客户端 IP。
    trust_proxy_headers: bool = _env_bool("TRUST_PROXY_HEADERS", True)
    # 只读展示模式：开启后即使没有密钥也禁止一切写操作（适合公网演示）。
    readonly_mode: bool = _env_bool("READONLY_MODE", False)

    @property
    def auth_mode(self) -> str:
        """返回当前访问控制模式，供 /health 与启动日志展示。"""
        if self.operator_key:
            return "operator-key"
        return "readonly" if self.readonly_mode else "open-demo"


# 全局唯一配置实例，供各模块直接引用。
settings = Settings()
