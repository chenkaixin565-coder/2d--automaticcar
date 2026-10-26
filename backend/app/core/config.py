"""
配置模块。

模块功能：集中管理应用运行所需的可配置参数（仿真步长、电池消耗、
传感器量程、温度阈值等）。所有配置项均通过环境变量提供默认值，
禁止在代码中硬编码密钥或内网地址。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

import os
from dataclasses import dataclass


def _env_float(name: str, default: str) -> float:
    """读取浮点型环境变量，非法值回退默认值，避免启动即崩。"""
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: str) -> int:
    """读取整型环境变量，非法值回退默认值。"""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


@dataclass
class Settings:
    """应用全局配置。"""

    # 仿真循环推送间隔（毫秒），与公共契约保持一致。
    tick_interval_ms: int = _env_int("TICK_INTERVAL_MS", "200")

    # 电池消耗：移动一格消耗百分比 / 静止每个 tick 消耗百分比。
    battery_move_cost: float = _env_float("BATTERY_MOVE_COST", "0.2")
    # V2.0：待机自放电默认关闭（原 0.02%/tick ≈ 6%/分钟，演示时会静默掉电）。
    battery_idle_cost: float = _env_float("BATTERY_IDLE_COST", "0.0")

    # 低电量告警阈值（百分比），低于该值自动返航充电。
    low_battery_threshold: float = _env_float("LOW_BATTERY_THRESHOLD", "20.0")

    # 手动/按规划清除一处障碍消耗的电量百分比。
    clear_obstacle_cost: float = _env_float("CLEAR_OBSTACLE_COST", "5.0")

    # 充电每 tick 恢复的电量百分比。
    charge_rate: float = _env_float("CHARGE_RATE", "1.0")

    # 传感器：每格代表的真实距离（米）与最大量程（米）。
    cell_distance_m: float = _env_float("CELL_DISTANCE_M", "0.5")
    sensor_range_m: float = _env_float("SENSOR_RANGE_M", "5.0")

    # 温度模型（V2.0）：基线 + 运动累积温升 - 静止散热，clamp 到上限。
    base_temperature: float = _env_float("BASE_TEMPERATURE", "35.0")
    temperature_rise_per_move: float = _env_float("TEMP_RISE_PER_MOVE", "0.08")
    temperature_cool_rate: float = _env_float("TEMP_COOL_RATE", "0.03")
    temperature_max: float = _env_float("TEMPERATURE_MAX", "70.0")
    temperature_noise: float = _env_float("TEMPERATURE_NOISE", "0.5")

    # 过热告警阈值（摄氏度）。配合累积温度模型，约连续巡检 250 格可触发。
    overheat_threshold: float = _env_float("OVERHEAT_THRESHOLD", "55.0")

    # 传感器单通道相邻帧突变判定阈值（米）。
    sensor_fault_delta: float = _env_float("SENSOR_FAULT_DELTA", "2.5")
    # 同一通道两次告警的最小间隔（秒），避免贴墙时刷屏。
    sensor_fault_cooldown_s: float = _env_float("SENSOR_FAULT_COOLDOWN_S", "10.0")

    # 异常检测策略：rule（默认，规则基线）/ ml（IsolationForest 在线检测）。
    anomaly_strategy: str = os.getenv("ANOMALY_STRATEGY", "rule")

    # 异常历史最多保留条数（V2.0：原实现无上限，长跑会持续膨胀）。
    anomaly_history_max: int = _env_int("ANOMALY_HISTORY_MAX", "200")

    # 传感器故障注入概率（0 = 关闭）。开启后每 tick 以该概率制造离群/卡死读数。
    sensor_fault_prob: float = _env_float("SENSOR_FAULT_PROB", "0.015")

    # IsolationForest 在线检测参数。
    ml_coldstart_ticks: int = _env_int("ML_COLDSTART_TICKS", "500")
    ml_window_size: int = _env_int("ML_WINDOW_SIZE", "120")
    ml_retrain_seconds: int = _env_int("ML_RETRAIN_SECONDS", "60")
    # 阈值校准：默认取正常段分数的低分位（百分数），把误报率压到该水平；
    # 也可用 ML_SCORE_THRESHOLD 指定固定分数阈值覆盖自动校准。
    ml_score_percentile: float = _env_float("ML_SCORE_PERCENTILE", "2.0")
    ml_score_threshold: str = os.getenv("ML_SCORE_THRESHOLD", "")
    # 污染率：'auto' 或 0–0.5 之间的浮点数。
    ml_contamination: str = os.getenv("ML_CONTAMINATION", "auto")

    # 默认地图尺寸（V2.0 与前端"默认厂房"预设统一为 30x20）。
    default_width: int = _env_int("DEFAULT_WIDTH", "30")
    default_height: int = _env_int("DEFAULT_HEIGHT", "20")
    default_start: tuple = (1, 1)
    default_charge_point: tuple = (1, 1)

    # 新建地图允许的尺寸范围（与前端 mapIO 校验保持一致）。
    min_map_size: int = _env_int("MIN_MAP_SIZE", "10")
    max_map_size: int = _env_int("MAX_MAP_SIZE", "60")

    # 待清障记录上限。
    pending_limit: int = _env_int("PENDING_LIMIT", "50")


# 全局唯一配置实例，供各模块直接引用。
settings = Settings()
