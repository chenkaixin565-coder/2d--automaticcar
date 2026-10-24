"""
地图数据模型模块。

模块功能：定义二维栅格地图的 Pydantic 数据模型。地图由二维数组 grid
表示（0 = 可通行，1 = 障碍物），并包含起点、巡检点集合与充电点。
所有字段命名严格遵循项目公共接口契约，不得改动。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from pydantic import BaseModel, Field, field_validator, model_validator

# 边界墙单元格取值（与普通障碍一致，但语义上不可编辑、不可清除）
CELL_BOUNDARY = 1


class GridMap(BaseModel):
    """二维栅格地图模型。"""

    width: int = Field(..., description="地图宽度（列数）", ge=1)
    height: int = Field(..., description="地图高度（行数）", ge=1)
    grid: list[list[int]] = Field(..., description="二维栅格数组，0=通行 1=障碍")
    start: tuple[int, int] = Field(..., description="机器人初始起点坐标 (x, y)")
    goals: list[tuple[int, int]] = Field(default_factory=list, description="巡检点集合")
    charge_point: tuple[int, int] = Field(..., description="充电点坐标 (x, y)")

    @field_validator("grid")
    @classmethod
    def validate_grid(cls, value: list[list[int]]) -> list[list[int]]:
        """
        校验栅格数组维度与取值合法性。

        :param value: 待校验的二维数组。
        :return: 校验通过的二维数组。
        :raises ValueError: 当行长度不一致或取值非 0/1 时抛出。
        """
        if not value:
            raise ValueError("栅格数组不能为空")
        row_len = len(value[0])
        for row in value:
            if len(row) != row_len:
                raise ValueError("栅格数组各行长度必须一致")
            for cell in row:
                if cell not in (0, 1):
                    raise ValueError("栅格取值只能为 0 或 1")
        return value

    @model_validator(mode="after")
    def enforce_boundary(self) -> "GridMap":
        """
        强制四周边界墙。

        地图最外环是真正的边界：不可编辑、不可清除、机器人不可穿越。
        任何来源的地图（REST 导入、WebSocket 更新、默认值）在模型校验
        阶段都会被补齐边界墙，保证该不变量始终成立。

        :return: 补齐边界墙后的自身。
        """
        for x in range(self.width):
            self.grid[0][x] = CELL_BOUNDARY
            self.grid[self.height - 1][x] = CELL_BOUNDARY
        for y in range(self.height):
            self.grid[y][0] = CELL_BOUNDARY
            self.grid[y][self.width - 1] = CELL_BOUNDARY
        return self

    def in_bounds(self, x: int, y: int) -> bool:
        """
        判断坐标是否越界。

        :param x: 列坐标。
        :param y: 行坐标。
        :return: 在地图范围内返回 True，否则 False。
        """
        return 0 <= x < self.width and 0 <= y < self.height

    def is_boundary(self, x: int, y: int) -> bool:
        """
        判断坐标是否为边界墙单元格（最外环）。

        :param x: 列坐标。
        :param y: 行坐标。
        :return: 位于最外环返回 True，否则 False。
        """
        return x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1

    def is_free(self, x: int, y: int) -> bool:
        """
        判断格子是否可通行。

        :param x: 列坐标。
        :param y: 行坐标。
        :return: 可通行返回 True，障碍或越界返回 False。
        """
        return self.in_bounds(x, y) and self.grid[y][x] == 0
