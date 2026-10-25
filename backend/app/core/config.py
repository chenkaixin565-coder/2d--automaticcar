"""
配置模块。

模块功能：集中管理应用运行所需的可配置参数（仿真步长、电池消耗、
传感器量程、温度阈值等）。所有配置项均通过环境变量提供默认值，
禁止在代码中硬编码密钥或内网地址。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """应用全局配置。"""

    # 仿真循环推送间隔（毫秒），与公共契约保持一致。
    tick_interval_ms: int = int(os.getenv("TICK_INTERVAL_MS", "200"))

    # 电池消耗：移动一格消耗百分比 / 静止每个 tick 消耗百分比。
    battery_move_cost: float = float(os.getenv("BATTERY_MOVE_COST", "0.2"))
    battery_idle_cost: float = float(os.getenv("BATTERY_IDLE_COST", "0.02"))

    # 低电量告警阈值（百分比），低于该值自动返航充电。
    low_battery_threshold: float = float(os.getenv("LOW_BATTERY_THRESHOLD", "20.0"))

    # 手动/按规划清除一处障碍消耗的电量百分比。
    clear_obstacle_cost: float = float(os.getenv("CLEAR_OBSTACLE_COST", "5.0"))

    # 充电每 tick 恢复的电量百分比。
    charge_rate: float = float(os.getenv("CHARGE_RATE", "1.0"))

    # 传感器：每格代表的真实距离（米）与最大量程（米）。
    cell_distance_m: float = float(os.getenv("CELL_DISTANCE_M", "0.5"))
    sensor_range_m: float = float(os.getenv("SENSOR_RANGE_M", "5.0"))

    # 温度基线（摄氏度）与运动温升、噪声幅度。
    base_temperature: float = float(os.getenv("BASE_TEMPERATURE", "35.0"))
    temperature_rise_per_move: float = float(os.getenv("TEMP_RISE_PER_MOVE", "0.05"))
    temperature_noise: float = float(os.getenv("TEMPERATURE_NOISE", "0.5"))

    # 过热告警阈值（摄氏度）。
    overheat_threshold: float = float(os.getenv("OVERHEAT_THRESHOLD", "60.0"))

    # 传感器突变判定阈值（米），相邻读数变化超过该值视为故障。
    sensor_fault_delta: float = float(os.getenv("SENSOR_FAULT_DELTA", "3.0"))

    # 异常检测策略：rule（默认，规则基线）/ ml（IsolationForest 在线检测）。
    anomaly_strategy: str = os.getenv("ANOMALY_STRATEGY", "rule")

    # 传感器故障注入概率（0 = 关闭）。开启后每 tick 以该概率制造离群/卡死读数。
    sensor_fault_prob: float = float(os.getenv("SENSOR_FAULT_PROB", "0.0"))

    # IsolationForest 在线检测参数。
    ml_coldstart_ticks: int = int(os.getenv("ML_COLDSTART_TICKS", "500"))
    ml_window_size: int = int(os.getenv("ML_WINDOW_SIZE", "120"))
    ml_retrain_seconds: int = int(os.getenv("ML_RETRAIN_SECONDS", "60"))
    # 阈值校准：默认取正常段分数的低分位（百分数），把误报率压到该水平；
    # 也可用 ML_SCORE_THRESHOLD 指定固定分数阈值覆盖自动校准。
    ml_score_percentile: float = float(os.getenv("ML_SCORE_PERCENTILE", "2.0"))
    ml_score_threshold: str = os.getenv("ML_SCORE_THRESHOLD", "")
    # 污染率：'auto' 或 0–0.5 之间的浮点数。
    ml_contamination: str = os.getenv("ML_CONTAMINATION", "auto")

    # 默认地图尺寸与初始充电点。
    default_width: int = int(os.getenv("DEFAULT_WIDTH", "16"))
    default_height: int = int(os.getenv("DEFAULT_HEIGHT", "12"))
    default_start: tuple = (0, 0)
    default_charge_point: tuple = (0, 0)


# 全局唯一配置实例，供各模块直接引用。
settings = Settings()
