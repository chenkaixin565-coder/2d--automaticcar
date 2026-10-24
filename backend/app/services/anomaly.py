"""
异常检测模块。

模块功能：基于规则引擎对机器人状态进行实时监测，识别低电量、过热、
传感器读数突变三类异常，并维护历史异常事件列表。异常阈值均来自配置
模块，便于答辩演示时调整。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from datetime import datetime, timezone

from app.core import config
from app.core.constants import (
    ANOMALY_LOW_BATTERY,
    ANOMALY_OVERHEAT,
    ANOMALY_SENSOR_FAULT,
)


class AnomalyDetector:
    """规则异常检测器。"""

    def __init__(self) -> None:
        """初始化检测器并创建空的历史事件列表。"""
        self._history: list[dict] = []
        # 记录已触发的持续型异常，避免同一异常每个 tick 重复推送。
        self._active: set[str] = set()

    @staticmethod
    def _now_iso() -> str:
        """返回当前时间的 ISO 8601 字符串。"""
        return datetime.now(timezone.utc).isoformat()

    def _record(self, anomaly_type: str, message: str, position: list[int]) -> dict:
        """
        记录并返回一条异常事件。

        :param anomaly_type: 异常类型字符串。
        :param message: 中文描述信息。
        :param position: 发生位置 [x, y]。
        :return: 与公共契约 anomaly 帧 data 字段一致的字典。
        """
        event = {
            "time": self._now_iso(),
            "type": anomaly_type,
            "message": message,
            "position": position,
        }
        self._history.append(event)
        return event

    def check(
        self,
        battery: float,
        temperature: float,
        sensors: dict,
        position: list[int],
        mode: str,
    ) -> list[dict]:
        """
        执行一轮规则检测。

        :param battery: 当前电量百分比。
        :param temperature: 当前温度（摄氏度）。
        :param sensors: 三向测距读数字典。
        :param position: 当前位置 [x, y]。
        :param mode: 当前运行模式。
        :return: 本轮新触发的异常事件列表。
        """
        triggered: list[dict] = []

        # 规则 1：低电量（持续型，恢复到阈值以上后重置）。
        if battery < config.settings.low_battery_threshold:
            if "low_battery" not in self._active:
                self._active.add("low_battery")
                triggered.append(
                    self._record(
                        ANOMALY_LOW_BATTERY,
                        f"电量不足 {battery:.0f}%，即将自动返航充电",
                        position,
                    )
                )
        else:
            self._active.discard("low_battery")

        # 规则 2：过热（持续型）。
        if temperature > config.settings.overheat_threshold:
            if "overheat" not in self._active:
                self._active.add("overheat")
                triggered.append(
                    self._record(
                        ANOMALY_OVERHEAT,
                        f"机身温度 {temperature:.1f}℃ 超过安全阈值",
                        position,
                    )
                )
        else:
            self._active.discard("overheat")

        # 规则 3：传感器读数突变（瞬时型，每次突变都上报）。
        readings = [sensors.get(key) for key in ("front", "left", "right")]
        valid = [value for value in readings if value is not None]
        for i in range(1, len(valid)):
            delta = abs(valid[i] - valid[i - 1])
            if delta > config.settings.sensor_fault_delta:
                triggered.append(
                    self._record(
                        ANOMALY_SENSOR_FAULT,
                        f"传感器读数突变 {delta:.1f}m，疑似故障",
                        position,
                    )
                )
                break  # 同一 tick 只报一次，避免刷屏。

        return triggered

    def get_history(self) -> list[dict]:
        """
        获取全部历史异常事件。

        :return: 事件列表（按时间升序）。
        """
        return list(self._history)

    def clear(self) -> None:
        """清空历史异常事件。"""
        self._history.clear()
        self._active.clear()
