"""
共享规则加载模块。

模块功能：读取仓库根目录 `shared/` 下的仿真规则与默认地图，作为后端与
前端唯一的口径来源（single source of truth）。

设计意图（V2.2.0）：V2.1 之前前后端各写一份常量，已经漂移出电量翻倍、
进度单位不一致、默认地图尺寸不同等问题。现在数值只允许出现在
`shared/simulation-rules.json`，两端都从这里读，任何一侧偏离都会在测试里暴露。

作者：智能巡检机器人二维仿真系统 V2.2.0 开发组
日期：2026-10-26
版本：V2.2.0
"""

import json
from functools import lru_cache
from pathlib import Path

# backend/app/core/shared.py -> backend/app -> backend -> 仓库根
SHARED_DIR = Path(__file__).resolve().parents[3] / "shared"
RULES_PATH = SHARED_DIR / "simulation-rules.json"
DEFAULT_MAP_PATH = SHARED_DIR / "default-map.json"


def _load_json(path: Path) -> dict:
    """
    读取 JSON 文件并在缺失时给出可定位的错误。

    :param path: 文件路径。
    :return: 解析后的字典。
    """
    if not path.is_file():
        raise RuntimeError(
            f"缺少共享规则文件 {path}；容器部署时请确认 Dockerfile 已 COPY shared/ 目录"
        )
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_rules() -> dict:
    """读取并缓存 `shared/simulation-rules.json`。"""
    return _load_json(RULES_PATH)


@lru_cache(maxsize=1)
def load_default_map() -> dict:
    """读取并缓存 `shared/default-map.json`。"""
    return _load_json(DEFAULT_MAP_PATH)
