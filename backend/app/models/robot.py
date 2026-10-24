"""
机器人与传感器数据模型模块。

模块功能：定义机器人状态帧、传感器读数、手动移动指令、巡检控制指令
等 Pydantic 模型。字段命名与公共接口契约及 WebSocket 协议逐字段一致。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from typing import Optional

from pydantic import BaseModel, Field


class Sensors(BaseModel):
    """三向测距传感器与温度传感器读数。"""

    front: Optional[float] = Field(None, description="正前方测距（米），超量程为 null")
    left: Optional[float] = Field(None, description="左侧测距（米），超量程为 null")
    right: Optional[float] = Field(None, description="右侧测距（米），超量程为 null")
    temperature: float = Field(..., description="机身温度（摄氏度）")


class RobotState(BaseModel):
    """机器人状态帧，对应 WebSocket state 帧的 data 字段。"""

    x: int = Field(..., description="机器人所在列坐标")
    y: int = Field(..., description="机器人所在行坐标")
    theta: float = Field(..., description="机器人朝向角（弧度）")
    battery: float = Field(..., description="剩余电量百分比")
    speed: float = Field(..., description="当前速度（格/step）")
    mode: str = Field(..., description="运行模式 manual|patrol|charging|blocked")
    path: list[list[int]] = Field(default_factory=list, description="当前规划路径")
    sensors: Sensors = Field(..., description="传感器读数")


class MoveCommand(BaseModel):
    """手动移动指令。"""

    dx: int = Field(..., description="水平方向步长 -1/0/1", ge=-1, le=1)
    dy: int = Field(..., description="垂直方向步长 -1/0/1", ge=-1, le=1)


class PatrolStartCommand(BaseModel):
    """开始自动巡检指令，goals 缺省时使用地图巡检点。"""

    goals: Optional[list[tuple[int, int]]] = Field(None, description="巡检点列表")
