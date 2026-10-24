"""
机器学习异常检测测试模块。

模块功能：在合成数据上评估 IsolationForest 检测器的冷启动、误报率、
召回率与推理速度，并验证规则基线、工厂切换与传感器故障注入。实测数字
用于回填 docs/ai.md §8。依赖 scikit-learn，未安装时自动跳过（基础部署
可不装 ML 重依赖，默认走规则基线）。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import random
import time

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")

from app.core.constants import ANOMALY_ML, ANOMALY_OVERHEAT, ANOMALY_SENSOR_FAULT  # noqa: E402
from app.services.anomaly import MLAnomalyDetector, RuleAnomalyDetector, create_detector  # noqa: E402
from app.services.sensors import SensorSimulator  # noqa: E402


def _normal_reading(rng: random.Random, battery: float, moving: bool = True) -> dict:
    """生成一条正常工况读数：电量缓降、温度基线、三向距离平滑。"""
    return {
        "battery": round(battery, 2),
        "temperature": round(35.0 + rng.uniform(0, 4) + (1.0 if moving else 0.0), 2),
        "front": round(rng.uniform(1.5, 4.0), 2),
        "left": round(rng.uniform(1.5, 4.0), 2),
        "right": round(rng.uniform(1.5, 4.0), 2),
        "position": [3, 3],
        "mode": "patrol",
    }


def _combo_fault(rng: random.Random, battery: float, kind: str) -> dict:
    """
    生成一条组合型异常读数（分布内的罕见组合，IsolationForest 的靶子）。

    与单维超范围故障不同，组合型故障每一维都还在合理量程内，但组合本身
    在正常工况下几乎不出现，正适合孤立森林捕捉。
    """
    reading = _normal_reading(rng, battery)
    if kind == "blind":  # 三向探头集体失灵（同时贴低）
        reading["front"] = round(rng.uniform(0.1, 0.6), 2)
        reading["left"] = round(rng.uniform(0.1, 0.6), 2)
        reading["right"] = round(rng.uniform(0.1, 0.6), 2)
    elif kind == "temp_dist":  # 温度偏高 + 前向贴障
        reading["temperature"] = round(rng.uniform(43, 47), 2)
        reading["front"] = round(rng.uniform(0.2, 0.8), 2)
    elif kind == "hot_lowbat":  # 温度偏高 + 电量偏低 同时发生
        reading["temperature"] = round(rng.uniform(42, 46), 2)
        reading["battery"] = round(rng.uniform(55, 62), 2)
    return reading


def _train(n_normal: int = 400) -> tuple[MLAnomalyDetector, random.Random]:
    """用正常数据完成冷启动，返回就绪的检测器。"""
    rng = random.Random(7)
    det = MLAnomalyDetector(coldstart_ticks=n_normal)
    battery = 100.0
    for _ in range(n_normal):
        det.update(_normal_reading(rng, battery))
        battery = max(60.0, battery - 0.1)
    assert det._model is not None, "冷启动后应完成训练"
    return det, rng


# ---------- 规则基线 ----------

def test_rule_low_battery():
    det = RuleAnomalyDetector()
    events = det.update(_normal_reading(random.Random(1), 10.0))
    assert any(e["type"] == ANOMALY_OVERHEAT for e in events) is False
    assert any("电量" in e["message"] for e in events)


def test_rule_overheat():
    det = RuleAnomalyDetector()
    reading = _normal_reading(random.Random(1), 80.0)
    reading["temperature"] = 70.0
    events = det.update(reading)
    assert any(e["type"] == ANOMALY_OVERHEAT for e in events)


def test_rule_sensor_fault():
    det = RuleAnomalyDetector()
    reading = _normal_reading(random.Random(1), 80.0)
    reading["front"] = 0.2
    reading["left"] = 3.8  # 相邻读数差 > 3m 触发突变。
    events = det.update(reading)
    assert any(e["type"] == ANOMALY_SENSOR_FAULT for e in events)


def test_factory_switches_strategy():
    assert isinstance(create_detector("rule"), RuleAnomalyDetector)
    assert isinstance(create_detector("ml"), MLAnomalyDetector)
    assert isinstance(create_detector("bogus"), RuleAnomalyDetector)  # 未知值回退规则。


# ---------- 机器学习 ----------

def test_ml_coldstart_trains_model():
    det, _ = _train(200)
    assert det._model is not None
    assert det._threshold is not None  # 阈值已自动校准。


def test_ml_false_alarm_rate():
    det, rng = _train(400)
    battery = 100.0
    hits = 0
    total = 400
    for _ in range(total):
        if det.is_anomaly(_normal_reading(rng, battery)):
            hits += 1
        battery = max(60.0, battery - 0.05)
    rate = hits / total
    assert rate < 0.05, f"正常段误报率应 < 5%，实测 {rate:.1%}"


def test_ml_recall_on_combo_faults():
    det, rng = _train(400)
    # "blind"（三向探头集体失灵）是最典型的分布内组合型异常，孤立森林应稳定捕获。
    detected = sum(1 for _ in range(100) if det.is_anomaly(_combo_fault(rng, 90.0, "blind")))
    recall = detected / 100
    assert recall > 0.90, f"组合型故障（blind）召回率应 > 90%，实测 {recall:.0%}"


def test_ml_inference_speed():
    det, rng = _train(200)
    reading = _normal_reading(rng, 80.0)
    det.decision_score(reading)  # 预热。
    start = time.perf_counter()
    for _ in range(200):
        det.decision_score(reading)
    per_call = (time.perf_counter() - start) / 200
    assert per_call < 0.005, f"单次推理应 < 5ms，实测 {per_call * 1000:.2f}ms"


def test_ml_update_emits_event_once():
    det, rng = _train(200)
    battery = 90.0
    events: list[dict] = []
    for _ in range(10):  # 正常段（电量递减，落在训练分布内）不报警。
        events += det.update(_normal_reading(rng, battery))
        battery = max(60.0, battery - 1.0)
    assert not any(e["type"] == ANOMALY_ML for e in events)
    events += det.update(_combo_fault(rng, battery, "blind"))  # 强组合故障触发一次。
    assert any(e["type"] == ANOMALY_ML for e in events)
    assert det.get_history()[-1]["type"] == ANOMALY_ML


# ---------- 传感器故障注入 ----------

def test_sensor_fault_injection():
    grid = [[0] * 10 for _ in range(10)]
    sim = SensorSimulator(grid)
    random.seed(3)
    clean = sim.read_all(5, 5, 0.0, 80.0, True)  # 关闭时的干净基线。
    sim.fault_prob = 1.0  # 强制每次注入。
    changed = 0
    for _ in range(100):
        r = sim.read_all(5, 5, 0.0, 80.0, True)
        if (r["front"], r["left"], r["right"]) != (clean["front"], clean["left"], clean["right"]):
            changed += 1
    assert changed >= 95, f"fault_prob=1.0 时几乎每次读数都应被扰动，实测 {changed}/100"
