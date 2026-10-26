"""
地图数据模型模块。

模块功能：定义二维栅格地图的 Pydantic 数据模型。地图由二维数组 grid
表示（0 = 可通行，1 = 障碍物），并包含起点、巡检点集合与充电点。
所有字段命名严格遵循项目公共接口契约，不得改动。

V2.0 变更：补齐尺寸一致性与坐标合法性校验。历史上 width/height 与 grid
不一致会直接抛 IndexError 变成 500；起点/充电点/巡检点越界或落在墙里也
能保存成功，机器人会被"搬"到地图外。现在全部在校验层拦截为 422。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

from pydantic import BaseModel, Field, field_validator, model_validator

# 边界墙单元格取值（与普通障碍一致，但语义上不可编辑、不可清除）
CELL_BOUNDARY = 1


class GridMap(BaseModel):
    """二维栅格地图模型。"""

    width: int = Field(..., description="地图宽度（列数）", ge=3)
    height: int = Field(..., description="地图高度（行数）", ge=3)
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
        :raises ValueError: 当行为空、行长度不一致或取值非 0/1 时抛出。
        """
        if not value:
            raise ValueError("栅格数组不能为空")
        row_len = len(value[0])
        if row_len == 0:
            raise ValueError("栅格数组每行不能为空")
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
        校验尺寸一致性、强制四周边界墙，并校验起点/充电点/巡检点。

        地图最外环是真正的边界：不可编辑、不可清除、机器人不可穿越。
        任何来源的地图（REST 导入、WebSocket 更新、默认值）在模型校验
        阶段都会被补齐边界墙，保证该不变量始终成立。

        :return: 补齐边界墙后的自身。
        :raises ValueError: 尺寸不匹配、坐标越界、坐标落在墙/障碍上时抛出。
        """
        rows = len(self.grid)
        cols = len(self.grid[0])
        if rows != self.height or cols != self.width:
            raise ValueError(
                f"栅格尺寸与声明不一致：声明的 width={self.width}、height={self.height}，"
                f"实际每行 {cols} 列、共 {rows} 行"
            )

        # 补齐边界墙。
        for x in range(self.width):
            self.grid[0][x] = CELL_BOUNDARY
            self.grid[self.height - 1][x] = CELL_BOUNDARY
        for y in range(self.height):
            self.grid[y][0] = CELL_BOUNDARY
            self.grid[y][self.width - 1] = CELL_BOUNDARY

        self._check_point("起点", self.start)
        self._check_point("充电点", self.charge_point)

        seen: set[tuple[int, int]] = set()
        for goal in self.goals:
            self._check_point("巡检点", goal)
            if goal in seen:
                raise ValueError(f"巡检点 {list(goal)} 重复")
            seen.add(goal)
        return self

    def _check_point(self, label: str, point: tuple[int, int]) -> None:
        """
        校验单个关键坐标点是否合法。

        :param label: 坐标语义（起点 / 充电点 / 巡检点），用于错误信息。
        :param point: 坐标 (x, y)。
        :raises ValueError: 越界、位于边界墙或障碍格时抛出。
        """
        x, y = point
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f"{label}坐标 ({x}, {y}) 超出地图范围")
        if self.is_boundary(x, y):
            raise ValueError(f"{label}不能位于地图边界上（边界墙不可通行）")
        if self.grid[y][x] != 0:
            raise ValueError(f"{label} ({x}, {y}) 位于障碍格上")

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
