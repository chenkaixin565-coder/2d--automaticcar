/**
 * 模块功能：仿真规则常量（前端侧）
 * 作者：智能巡检机器人二维仿真系统 V2.2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.2.0
 *
 * 唯一来源是仓库根目录 `shared/simulation-rules.json`，后端
 * `app/core/config.py` 读的是同一个文件。前端不再自己写死 0.2% / 20% /
 * 2.5m 这些数字，避免两套实现再次漂移。
 */

import RULES from '../../../shared/simulation-rules.json'

/** 每个栅格对应的实际距离（米）。 */
export const CELL_METERS = RULES.sensor.cell_meters

/** 传感器最大量程（米）。 */
export const SENSOR_RANGE_METERS = RULES.sensor.range_meters

/** 传感器最大量程对应的栅格数。 */
export const SENSOR_MAX_CELLS = Math.floor(SENSOR_RANGE_METERS / CELL_METERS)

/** 每移动一格消耗的电量百分比。 */
export const BATTERY_MOVE_COST = RULES.battery.move_cost

/** 待机每 tick 的耗电量。 */
export const BATTERY_IDLE_COST = RULES.battery.idle_cost

/** 充电点每个 tick 补充的电量百分比。 */
export const CHARGE_RATE = RULES.battery.charge_rate

/** 低电量告警阈值。 */
export const LOW_BATTERY_THRESHOLD = RULES.battery.low_threshold

/** 每清除一处障碍消耗的电量百分比。 */
export const CLEAR_OBSTACLE_COST = RULES.battery.clear_cost

/** 温度模型参数。 */
export const TEMP_BASE = RULES.temperature.base
export const TEMP_RISE_PER_MOVE = RULES.temperature.rise_per_move
export const TEMP_COOL_PER_TICK = RULES.temperature.cool_per_tick
export const TEMP_MAX = RULES.temperature.max

/** 过热告警阈值（摄氏度）。 */
export const OVERHEAT_THRESHOLD = RULES.temperature.overheat_threshold

/** 传感器单通道相邻帧突变告警阈值（米）。 */
export const SENSOR_JUMP_THRESHOLD = RULES.sensor.fault_delta

/** 同一通道两次告警的最小冷却时间（毫秒）。 */
export const SENSOR_FAULT_COOLDOWN_MS = RULES.sensor.fault_cooldown_s * 1000

/** 异常历史最多保留条数。 */
export const ANOMALY_LIMIT = RULES.maps.anomaly_history_max

/** 待清障记录上限。 */
export const PENDING_LIMIT = RULES.maps.pending_limit

/** 新建地图允许的尺寸范围。 */
export const MIN_MAP_SIZE = RULES.maps.min_size
export const MAX_MAP_SIZE = RULES.maps.max_size
