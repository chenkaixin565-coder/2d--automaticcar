"""
限流模块。

模块功能：进程内的令牌桶限流，按客户端 IP 区分。用于演示"每个客户端
每分钟最多多少次请求"，避免单个脚本把仿真循环打满。

边界说明：计数保存在进程内存，多实例部署时每个实例各自计数；要做全局
配额需要 Redis 之类的共享存储，本项目刻意不引入该依赖。

作者：智能巡检机器人二维仿真系统 V2.2.0 开发组
日期：2026-10-26
版本：V2.2.0
"""

import threading
import time


class TokenBucketLimiter:
    """按 key（通常是客户端 IP）维护令牌桶。"""

    def __init__(self) -> None:
        """初始化空桶集合与线程锁。"""
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def reset(self) -> None:
        """清空所有桶（测试与热重载时使用）。"""
        with self._lock:
            self._buckets.clear()
            self._last_sweep = time.monotonic()

    def allow(self, key: str, per_minute: int, burst: int) -> tuple[bool, float]:
        """
        判断本次请求是否放行。

        :param key: 限流维度（客户端 IP）。
        :param per_minute: 每分钟补充的令牌数；<=0 表示关闭限流。
        :param burst: 桶容量（允许的瞬时突发）。
        :return: (是否放行, 建议等待秒数)。
        """
        if per_minute <= 0:
            return True, 0.0

        now = time.monotonic()
        capacity = float(max(1, burst or per_minute))
        rate_per_second = per_minute / 60.0

        with self._lock:
            tokens, last = self._buckets.get(key, (capacity, now))
            tokens = min(capacity, tokens + (now - last) * rate_per_second)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                allowed, wait = True, 0.0
            else:
                self._buckets[key] = (tokens, now)
                allowed, wait = False, (1.0 - tokens) / rate_per_second
            self._sweep(now)
            return allowed, wait

    def _sweep(self, now: float) -> None:
        """定期清理长时间不活跃的桶，避免 IP 种类多时内存持续增长。"""
        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        stale = [key for key, (_, last) in self._buckets.items() if now - last > 600]
        for key in stale:
            self._buckets.pop(key, None)


# 全局唯一限流器：HTTP 中间件与 WebSocket 握手共用。
limiter = TokenBucketLimiter()
