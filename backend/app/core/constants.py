"""
常量模块。

模块功能：定义地图格子语义、机器人运行模式、异常类型等枚举常量，
供仿真引擎、接口层统一引用，避免魔法字符串散落各处。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

# 地图格子取值：0 = 可通行，1 = 障碍物。
CELL_FREE = 0
CELL_OBSTACLE = 1

# 机器人运行模式。
MODE_MANUAL = "manual"      # 手动控制
MODE_PATROL = "patrol"      # 自动巡检
MODE_CHARGING = "charging"  # 充电返航
MODE_BLOCKED = "blocked"    # 碰撞受阻

# 异常类型。
ANOMALY_LOW_BATTERY = "low_battery"      # 低电量
ANOMALY_OBSTACLE = "obstacle"            # 障碍物/寻路失败
ANOMALY_SENSOR_FAULT = "sensor_fault"    # 传感器故障
ANOMALY_OVERHEAT = "overheat"            # 过热

# 四邻域移动方向（dx, dy），保持与前端坐标约定一致。
DIRECTION_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
