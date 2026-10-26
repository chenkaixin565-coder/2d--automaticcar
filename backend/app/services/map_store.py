"""
地图库存储模块（V2.1）。

模块功能：把用户保存的地图以 JSON 文件形式存放在服务端目录中，供多设备
同步使用。每张地图一个文件，文件名即 map_id，内容包含名称、栅格、起点、
巡检点、充电点与更新时间。

存储位置由环境变量 MAP_STORE_DIR 指定，默认 backend/data/maps。
注意：Render 免费实例的磁盘是临时的，重启后服务端地图会丢失；浏览器本地
地图库（localStorage）不受影响，可作为长期存档。
作者：智能巡检机器人二维仿真系统 V2.1 开发组
日期：2026-10-27
版本：V2.1
"""

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from app.models.map import GridMap

logger = logging.getLogger("services.map_store")

STORE_DIR = Path(os.getenv("MAP_STORE_DIR", "data/maps"))


def _ensure_dir() -> None:
    """确保存储目录存在。"""
    STORE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_id(raw: str) -> str:
    """把任意字符串规整成可用作文件名的 id。"""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", raw)
    return cleaned or uuid.uuid4().hex[:12]


def list_maps() -> list[dict]:
    """
    列出已保存地图的元信息（不含栅格数据）。

    :return: [{'id', 'name', 'width', 'height', 'updated_at', 'goals'}, ...]
    """
    _ensure_dir()
    items: list[dict] = []
    for path in sorted(STORE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("跳过损坏的地图文件：%s", path.name)
            continue
        items.append(
            {
                "id": path.stem,
                "name": data.get("name", path.stem),
                "width": data.get("width"),
                "height": data.get("height"),
                "updated_at": data.get("updated_at", ""),
                "goals": len(data.get("goals") or []),
            }
        )
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return items


def save_map(name: str, grid_map: GridMap, map_id: str | None = None) -> dict:
    """
    保存（或覆盖）一张地图。

    :param name: 地图名称。
    :param grid_map: 已校验的地图模型。
    :param map_id: 指定 id 时覆盖同名条目，否则新建。
    :return: 保存后的元信息。
    """
    _ensure_dir()
    clean_name = (name or "未命名地图").strip()[:40]
    identifier = _safe_id(map_id) if map_id else f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
    payload = {
        "id": identifier,
        "name": clean_name,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **grid_map.model_dump(),
    }
    (STORE_DIR / f"{identifier}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("地图已保存：%s（%s，%dx%d）", clean_name, identifier, grid_map.width, grid_map.height)
    return {k: payload[k] for k in ("id", "name", "width", "height", "updated_at")}


def load_map(map_id: str) -> dict | None:
    """
    读取一张地图的完整内容。

    :param map_id: 地图 id。
    :return: 地图字典，不存在时为 None。
    """
    path = STORE_DIR / f"{_safe_id(map_id)}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("地图文件损坏：%s", path.name)
        return None


def delete_map(map_id: str) -> bool:
    """
    删除一张地图。

    :param map_id: 地图 id。
    :return: 是否实际删除。
    """
    path = STORE_DIR / f"{_safe_id(map_id)}.json"
    if not path.is_file():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        logger.exception("删除地图失败：%s", path.name)
        return False
