"""
事件数据模型模块。

模块功能：定义异常事件、巡检状态、WebSocket 推送帧等模型。事件字段
与公共契约的 anomaly 帧、notice 帧逐字段一致。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from typing import Optional

from pydantic import BaseModel, Field


class AnomalyEvent(BaseModel):
    """异常事件模型，对应 anomaly 帧的 data 字段。"""

    time: str = Field(..., description="事件时间（ISO 8601 字符串）")
    type: str = Field(..., description="异常类型 low_battery|obstacle|sensor_fault|overheat")
    message: str = Field(..., description="异常描述信息")
    position: list[int] = Field(..., description="发生位置 [x, y]")


class PatrolStatus(BaseModel):
    """巡检状态模型。"""

    running: bool = Field(..., description="巡检是否在运行")
    current_goal: Optional[list[int]] = Field(None, description="当前目标巡检点")
    progress: float = Field(..., description="巡检完成进度 0~1")
    path_remain: int = Field(..., description="当前段剩余路径长度")


class StateFrame(BaseModel):
    """WebSocket state 推送帧。"""

    type: str = "state"
    data: dict = Field(..., description="RobotState 序列化后的字典")


class AnomalyFrame(BaseModel):
    """WebSocket anomaly 推送帧。"""

    type: str = "anomaly"
    data: AnomalyEvent


class NoticeFrame(BaseModel):
    """WebSocket notice 推送帧。"""

    type: str = "notice"
    data: dict = Field(..., description="{'message': '...'}")
