"""
异常检测模块。

模块功能：对机器人每个 tick 的传感读数做实时异常判断。采用双策略并行、
配置切换的设计：
  - 规则基线（默认）：阈值法，覆盖低电量 / 过热 / 传感器突变三类已知故障，
    逻辑直观、零冷启动，作为兜底与对照。
  - 机器学习（IsolationForest）：对滑动窗口内的多维传感数据做在线异常打分，
    能发现规则难以覆盖的组合型异常。

两条策略都输出结构一致的 anomaly 事件，通过 WebSocket 的 anomaly 帧即时推送。
机器学习重依赖（numpy / scikit-learn）仅在 ml 策略下按需惰性导入，保证默认
rule 策略在仅安装基础依赖的环境下也能正常运行。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from app.core import config
from app.core.constants import (
    ANOMALY_LOW_BATTERY,
    ANOMALY_ML,
    ANOMALY_OVERHEAT,
    ANOMALY_SENSOR_FAULT,
)

logger = logging.getLogger("simulation.anomaly")


class BaseAnomalyDetector:
    """异常检测器公共接口。"""

    def update(self, reading: dict) -> list[dict]:
        """
        根据一帧传感读数返回本轮新触发的异常事件。

        :param reading: 含 battery/temperature/front/left/right/position/mode 的字典。
        :return: 异常事件列表（与公共契约 anomaly 帧 data 字段一致）。
        """
        raise NotImplementedError

    def get_history(self) -> list[dict]:
        """获取全部历史异常事件。"""
        raise NotImplementedError

    def clear(self) -> None:
        """清空历史异常事件。"""
        raise NotImplementedError

    @staticmethod
    def _now_iso() -> str:
        """返回当前时间的 ISO 8601 字符串。"""
        return datetime.now(timezone.utc).isoformat()

    def _record(self, anomaly_type: str, message: str, position: list[int]) -> dict:
        """构造并登记一条异常事件。"""
        event = {
            "time": self._now_iso(),
            "type": anomaly_type,
            "message": message,
            "position": position,
        }
        self._history.append(event)
        return event


class RuleAnomalyDetector(BaseAnomalyDetector):
    """规则异常检测器（阈值法）。"""

    def __init__(self) -> None:
        """初始化检测器并创建历史事件容器。"""
        # V2.0：历史事件改为有界队列，避免长时间运行内存与接口响应体膨胀。
        self._history: deque = deque(maxlen=config.settings.anomaly_history_max)
        # 已触发的持续型异常，避免同一异常每个 tick 重复推送。
        self._active: set[str] = set()
        # 上一帧三向读数，用于"同一通道跨帧"突变判定。
        self._prev_readings: dict[str, Optional[float]] = {}
        # 每个通道上次告警时间戳（秒），用于冷却去重。
        self._last_fault_at: dict[str, float] = {}

    def update(self, reading: dict) -> list[dict]:
        """
        执行一轮规则检测。

        :param reading: 含 battery/temperature/front/left/right/position/mode 的字典。
        :return: 本轮新触发的异常事件列表。
        """
        battery = reading.get("battery", 100.0)
        temperature = reading.get("temperature", 0.0)
        position = reading.get("position", [0, 0])
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

        # 规则 3：传感器读数突变（瞬时型）。
        # V2.0 修正：原实现把同一 tick 的 front/left/right 当作时间序列互相比，
        # 只要机器人靠近墙（前 5m、侧 0.5m）就会误报"读数突变"。正确语义是
        # "同一通道的这一帧 vs 上一帧"，与前端 simulatedService 保持一致。
        now = time.time()
        cooldown = config.settings.sensor_fault_cooldown_s
        for channel in ("front", "left", "right"):
            current = reading.get(channel)
            previous = self._prev_readings.get(channel)
            self._prev_readings[channel] = current
            if current is None or previous is None:
                continue
            delta = abs(current - previous)
            if delta <= config.settings.sensor_fault_delta:
                continue
            last = self._last_fault_at.get(channel, 0.0)
            if now - last < cooldown:
                continue
            self._last_fault_at[channel] = now
            label = {"front": "正前方", "left": "左侧", "right": "右侧"}[channel]
            triggered.append(
                self._record(
                    ANOMALY_SENSOR_FAULT,
                    f"{label}传感器读数突变 {delta:.1f}m，疑似故障",
                    position,
                )
            )
            break  # 同一 tick 只报一次，避免刷屏。

        return triggered

    def get_history(self) -> list[dict]:
        """获取全部历史异常事件。"""
        return list(self._history)

    def clear(self) -> None:
        """清空历史异常事件。"""
        self._history.clear()
        self._active.clear()
        self._prev_readings.clear()
        self._last_fault_at.clear()


class MLAnomalyDetector(BaseAnomalyDetector):
    """
    IsolationForest 在线异常检测器。

    冷启动阶段（默认 500 tick）以正常模式采集样本，训练首个模型；之后每个
    tick 把最新特征追加到长度为 120 的滑动窗口并打分。每 60 秒用窗口内最近
    数据在后台线程增量重训，适应温度基线等缓慢漂移。

    两个关键设计：
      1. 特征标准化——电量（跨度约 40）与温度/距离（跨度约 5）量纲差异大，
         直接喂模型会被电量主导；用训练段均值/方差做 z-score 标准化，
         让各维贡献均衡。
      2. 阈值自动校准——取正常段异常分数的低分位作为阈值，把误报率控制在
         ml_score_percentile 水平；也可用 ML_SCORE_THRESHOLD 指定固定阈值覆盖。
    标准化使 IsolationForest 擅长捕捉"分布内的组合型异常"（如多向探头同时
    失效、温度与距离背离）；对单维超范围外推故障，由规则基线兜底更稳。

    重依赖 numpy / scikit-learn 在首次训练时惰性导入，未安装时调用抛 ImportError。
    """

    def __init__(
        self,
        coldstart_ticks: Optional[int] = None,
        window_size: Optional[int] = None,
        retrain_seconds: Optional[int] = None,
        score_percentile: Optional[float] = None,
        score_threshold: Optional[str] = None,
        contamination: Optional[str] = None,
    ) -> None:
        """初始化检测器（参数缺省时取自全局配置）。"""
        self.coldstart_ticks = coldstart_ticks or config.settings.ml_coldstart_ticks
        self.window_size = window_size or config.settings.ml_window_size
        self.retrain_seconds = retrain_seconds or config.settings.ml_retrain_seconds
        self.score_percentile = (
            score_percentile if score_percentile is not None else config.settings.ml_score_percentile
        )
        # 固定阈值覆盖：配置了具体数值则用它，否则按正常分数分位自动校准。
        raw = score_threshold if score_threshold is not None else config.settings.ml_score_threshold
        try:
            self._threshold_override: Optional[float] = float(raw) if str(raw).strip() else None
        except (TypeError, ValueError):
            self._threshold_override = None
        self.contamination = contamination or config.settings.ml_contamination

        self._history: list[dict] = []
        self._active: set[str] = set()
        self._buffer: list[list[float]] = []          # 冷启动采集缓冲。
        self._window: list[list[float]] = []          # 在线打分滑动窗口。
        self._model = None                            # IsolationForest 实例。
        self._mean = None                             # 各维均值（标准化用）。
        self._std = None                              # 各维标准差（标准化用）。
        self._threshold: Optional[float] = None       # 校准后的异常阈值。
        self._tick = 0
        self._last_retrain = time.time()
        self._training = False
        self._lock = threading.Lock()

    # ---------- 特征 ----------

    @staticmethod
    def _to_feature(reading: dict) -> list[float]:
        """
        把一帧读数映射成 5 维特征向量。

        缺失读数（射线超程）用量程上限填充，保证维度恒定、输入稳定。

        :param reading: 含 battery/temperature/front/left/right 的字典。
        :return: [battery, temperature, front, left, right]
        """
        range_m = config.settings.sensor_range_m
        fill = lambda v: range_m if v is None else v  # noqa: E731 - 单行填充辅助。
        return [
            float(reading.get("battery", 100.0)),
            float(reading.get("temperature", 0.0)),
            float(fill(reading.get("front"))),
            float(fill(reading.get("left"))),
            float(fill(reading.get("right"))),
        ]

    # ---------- 模型训练（惰性导入重依赖） ----------

    def _fit(self, X: list) -> None:
        """标准化后训练 IsolationForest，并校准阈值；线程安全地整体替换状态。"""
        import numpy as np
        from sklearn.ensemble import IsolationForest  # 惰性导入，基础环境可无此依赖。

        arr = np.asarray(X, dtype=float)
        mean = arr.mean(axis=0)
        std = arr.std(axis=0)
        std[std == 0] = 1.0  # 某维无波动时避免除零。
        standardized = (arr - mean) / std

        contamination = self.contamination if self.contamination == "auto" else float(self.contamination)
        model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
        model.fit(standardized)

        # 用训练段（视为正常段）分数分布校准阈值，控制误报率。
        calibrated = float(np.percentile(model.score_samples(standardized), self.score_percentile))
        threshold = self._threshold_override if self._threshold_override is not None else calibrated

        with self._lock:
            self._model = model
            self._mean = mean
            self._std = std
            self._threshold = threshold

    def _retrain_worker(self, snapshot: list) -> None:
        """后台增量重训：训练完成后复位训练标志。"""
        try:
            self._fit(snapshot)
            logger.info("ML 模型增量重训完成，样本数 %d", len(snapshot))
        except Exception:  # noqa: BLE001 - 重训失败不应影响仿真主循环。
            logger.exception("ML 模型增量重训失败")
        finally:
            self._training = False

    # ---------- 推理接口 ----------

    def decision_score(self, reading: dict) -> float:
        """
        返回单条读数的异常分数（score_samples，越低越异常）。

        模型未就绪时返回 0.0（视为正常）。

        :param reading: 传感读数字典。
        :return: 异常分数。
        """
        import numpy as np  # 惰性导入。

        with self._lock:
            model, mean, std = self._model, self._mean, self._std
        if model is None or mean is None:
            return 0.0
        feature = (np.asarray([self._to_feature(reading)], dtype=float) - mean) / std
        return float(model.score_samples(feature)[0])

    def is_anomaly(self, reading: dict) -> bool:
        """判断单条读数是否为异常（供测试与离线评估使用）。"""
        with self._lock:
            threshold = self._threshold
        if threshold is None:
            return False
        return self.decision_score(reading) < threshold

    def update(self, reading: dict) -> list[dict]:
        """
        推进一帧：冷启动采集 / 在线打分，返回本轮新触发的异常事件。

        :param reading: 含 battery/temperature/front/left/right/position/mode 的字典。
        :return: 异常事件列表。
        """
        feature = self._to_feature(reading)
        self._tick += 1
        position = reading.get("position", [0, 0])
        events: list[dict] = []

        # 冷启动：采集足够样本后训练首个模型。
        if self._model is None:
            if not self._training:
                self._buffer.append(feature)
                if len(self._buffer) >= self.coldstart_ticks:
                    self._training = True
                    self._fit([list(v) for v in self._buffer])
                    self._window.extend(self._buffer)
                    self._training = False
                    logger.info("ML 模型冷启动完成，样本数 %d", len(self._buffer))
            return events

        # 在线打分：追加窗口并对最新样本评分。
        self._window.append(feature)
        score = self.decision_score(reading)
        with self._lock:
            threshold = self._threshold
        if threshold is not None and score < threshold:
            if "ml_anomaly" not in self._active:
                self._active.add("ml_anomaly")
                events.append(
                    self._record(
                        ANOMALY_ML,
                        f"机器学习检测到异常工况（评分 {score:.2f}）",
                        position,
                    )
                )
        else:
            self._active.discard("ml_anomaly")

        # 周期性后台增量重训。
        now = time.time()
        if now - self._last_retrain >= self.retrain_seconds and not self._training:
            self._last_retrain = now
            snapshot = [list(v) for v in self._window]
            if len(snapshot) >= self.window_size:
                self._training = True
                worker = threading.Thread(target=self._retrain_worker, args=(snapshot,), daemon=True)
                worker.start()

        return events

    def get_history(self) -> list[dict]:
        """获取全部历史异常事件。"""
        return list(self._history)

    def clear(self) -> None:
        """清空历史异常事件与在线状态。"""
        self._history.clear()
        self._active.clear()
        self._buffer.clear()
        self._window.clear()
        self._model = None
        self._mean = None
        self._std = None
        self._threshold = None
        self._tick = 0
        self._last_retrain = time.time()
        self._training = False


def create_detector(strategy: Optional[str] = None) -> BaseAnomalyDetector:
    """
    按策略创建异常检测器，对调用方透明。

    :param strategy: 'rule'（默认）或 'ml'。
    :return: 对应策略的检测器实例。
    """
    strategy = strategy or config.settings.anomaly_strategy
    if strategy == "ml":
        # 基础镜像不装 numpy/scikit-learn（见 requirements-ml.txt）：
        # 缺依赖时自动降级为规则基线，避免仿真 tick 抛 ImportError 后整个循环停摆。
        try:
            import numpy  # noqa: F401
            import sklearn  # noqa: F401
        except ImportError:
            logger.warning("未安装 numpy/scikit-learn，ml 策略自动降级为规则基线")
            return RuleAnomalyDetector()
        return MLAnomalyDetector()
    if strategy != "rule":
        logger.warning("未知异常检测策略 %r，回退到规则基线", strategy)
    return RuleAnomalyDetector()
