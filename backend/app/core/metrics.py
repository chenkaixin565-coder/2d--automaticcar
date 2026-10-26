"""
指标模块。

模块功能：进程内计数器 + Prometheus 文本格式导出，不引入额外依赖。
覆盖请求量、状态码分布、限流 / 鉴权拒绝次数、WebSocket 连接数、
仿真 tick 次数与错误数、机器人关键状态。

边界说明：指标保存在进程内存，重启即清零；这是给单实例部署用的最小可观测面，
不是 Prometheus 服务端。

作者：智能巡检机器人二维仿真系统 V2.2.0 开发组
日期：2026-10-26
版本：V2.2.0
"""

import threading
import time
from collections import Counter


class MetricsRegistry:
    """线程安全的计数器集合。"""

    def __init__(self) -> None:
        """初始化计数器与启动时间。"""
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()
        self.started_at = time.time()

    def inc(self, name: str, value: int = 1) -> None:
        """
        计数器自增。

        :param name: 指标名（已包含标签信息，如 http_requests{method="GET",status="200"}）。
        :param value: 增量。
        """
        with self._lock:
            self._counters[name] += value

    def snapshot(self) -> dict[str, int]:
        """返回计数器快照（复制，避免渲染时持锁）。"""
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        """清零计数器（测试使用）。"""
        with self._lock:
            self._counters.clear()
            self.started_at = time.time()

    def render(self, extra: list[str] | None = None) -> str:
        """
        渲染 Prometheus 文本格式。

        :param extra: 额外指标行（引擎状态等由调用方组装）。
        :return: 文本格式指标。
        """
        lines: list[str] = [
            "# HELP irm_uptime_seconds 进程运行时长（秒）",
            "# TYPE irm_uptime_seconds gauge",
            f"irm_uptime_seconds {time.time() - self.started_at:.1f}",
        ]
        for name, value in sorted(self.snapshot().items()):
            metric, _, labels = name.partition("{")
            lines.append(f"{metric}{{{labels} {value}" if labels else f"{metric} {value}")
        if extra:
            lines.extend(extra)
        return "\n".join(lines) + "\n"


# 全局唯一指标注册表。
metrics = MetricsRegistry()
