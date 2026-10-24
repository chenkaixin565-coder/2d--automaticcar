"""
虚拟传感器模块。

模块功能：在无实体硬件的前提下，基于栅格地图模拟三向测距雷达与温度
传感器读数。前/左/右三个方向各发射一条射线，计算到障碍物的距离（米）；
温度在基线之上叠加运动温升与高斯噪声。所有逻辑与前端 SimulatedService
保持一致，便于前后端行为互验。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import math
import random

from app.core import config
from app.core.constants import CELL_OBSTACLE


class SensorSimulator:
    """虚拟传感器模拟器。"""

    def __init__(self, grid: list[list[int]]) -> None:
        """
        初始化传感器。

        :param grid: 当前栅格地图，用于射线碰撞判定。
        """
        self.grid = grid

    def set_grid(self, grid: list[list[int]]) -> None:
        """更新地图引用（地图被编辑后调用）。"""
        self.grid = grid

    def _cast_ray(self, x: int, y: int, dx: int, dy: int) -> float | None:
        """
        沿指定方向发射射线，返回到障碍物的距离（米）。

        :param x: 起点列坐标。
        :param y: 起点行坐标。
        :param dx: 射线方向 x 分量（单位向量）。
        :param dy: 射线方向 y 分量（单位向量）。
        :return: 距离（米）；超出量程返回 None。
        """
        step = 0
        max_steps = int(config.settings.sensor_range_m / config.settings.cell_distance_m)
        current_x, current_y = x, y
        # 逐格推进，命中障碍物或越界即停止。
        while step < max_steps:
            step += 1
            current_x += dx
            current_y += dy
            if not self._in_bounds(current_x, current_y):
                return round(step * config.settings.cell_distance_m, 2)
            if self.grid[current_y][current_x] == CELL_OBSTACLE:
                return round(step * config.settings.cell_distance_m, 2)
        # 走满量程仍未命中，视为超程。
        return None

    def _in_bounds(self, x: int, y: int) -> bool:
        """判断坐标是否在地图范围内。"""
        height = len(self.grid)
        width = len(self.grid[0]) if height else 0
        return 0 <= x < width and 0 <= y < height

    def read_distances(self, x: int, y: int, theta: float) -> dict:
        """
        读取三向测距数据。

        根据机器人朝向 theta 计算前/左/右三个方向向量后分别测距。

        :param x: 机器人列坐标。
        :param y: 机器人行坐标。
        :param theta: 机器人朝向角（弧度）。
        :return: {'front': float|None, 'left': float|None, 'right': float|None}
        """
        # 朝向向量与左右法向量。
        forward = (round(math.cos(theta)), round(math.sin(theta)))
        left = (round(math.cos(theta - math.pi / 2)), round(math.sin(theta - math.pi / 2)))
        right = (round(math.cos(theta + math.pi / 2)), round(math.sin(theta + math.pi / 2)))
        return {
            "front": self._cast_ray(x, y, *forward),
            "left": self._cast_ray(x, y, *left),
            "right": self._cast_ray(x, y, *right),
        }

    def read_temperature(self, is_moving: bool) -> float:
        """
        读取机身温度：基线温度 + 运动温升 + 高斯噪声。

        :param is_moving: 机器人当前是否在移动。
        :return: 温度读数（摄氏度，保留一位小数）。
        """
        rise = config.settings.temperature_rise_per_move if is_moving else 0.0
        noise = random.gauss(0, config.settings.temperature_noise * 0.3)
        value = config.settings.base_temperature + rise + noise
        return round(value, 1)
