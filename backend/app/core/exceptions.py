"""
异常定义模块。

模块功能：定义系统自定义异常类型，便于接口层统一捕获并返回规范的
HTTP 错误响应。各业务异常均携带可读的中文错误信息。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from fastapi import HTTPException


class SimulationError(Exception):
    """仿真业务基础异常。"""


class InvalidMapError(SimulationError):
    """地图数据非法（尺寸错误、坐标越界、栅格取值非法）。"""


class InvalidMoveError(SimulationError):
    """移动指令非法（坐标越界或碰撞障碍物）。"""


class PathNotFoundError(SimulationError):
    """A* 寻路失败，目标不可达。"""


def http_error(status_code: int, detail: str) -> HTTPException:
    """
    构造统一的 HTTP 异常。

    :param status_code: HTTP 状态码。
    :param detail: 错误详情（中文描述）。
    :return: FastAPI 的 HTTPException 实例。
    """
    return HTTPException(status_code=status_code, detail=detail)
