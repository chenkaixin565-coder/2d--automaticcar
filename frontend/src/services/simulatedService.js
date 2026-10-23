/**
 * 模块功能：本地仿真器服务实现
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 本模块在前端完全模拟后端行为：200ms 推进一次仿真 tick，生成传感器数据、
 * 检测异常、执行巡检任务，并通过 onState/onEvent 推送与后端 WebSocket 协议
 * 逐字段一致的数据帧。下一阶段替换为 RemoteService 时，界面组件无需修改。
 */

import { RobotService } from './robotService.js'
import { astar } from './astar.js'

/** 仿真 tick 间隔，单位毫秒，与后端 WebSocket 推送频率一致。 */
const TICK_MS = 200

/** 每个栅格对应的实际距离（米）。 */
const CELL_METERS = 0.5

/** 传感器最大量程（米）。 */
const SENSOR_RANGE_METERS = 5.0

/** 传感器最大量程对应的栅格数。 */
const SENSOR_MAX_CELLS = Math.floor(SENSOR_RANGE_METERS / CELL_METERS)

/** 每移动一格消耗的电量百分比。 */
const BATTERY_MOVE_COST = 0.2

/** 每个 tick 静止消耗的电量百分比。 */
const BATTERY_IDLE_COST = 0.02

/** 充电点每个 tick 补充的电量百分比。 */
const CHARGE_RATE = 1.0

/** 低电量告警阈值。 */
const LOW_BATTERY_THRESHOLD = 20.0

/** 过热告警阈值（摄氏度）。 */
const OVERHEAT_THRESHOLD = 60.0

/** 传感器读数突变告警阈值（米）。 */
const SENSOR_JUMP_THRESHOLD = 2.0

/** 同一类异常的最小冷却时间（毫秒），避免重复刷屏。 */
const ANOMALY_COOLDOWN_MS = 5000

/** localStorage 中地图数据的键名。 */
const STORAGE_MAP_KEY = 'irm_map_v1'

/** 地图默认尺寸。 */
const DEFAULT_WIDTH = 30
const DEFAULT_HEIGHT = 20

/**
 * 本地仿真器服务类。
 *
 * 继承自 RobotService，所有状态在浏览器内计算，不依赖外部网络请求。
 */
export class SimulatedService extends RobotService {
  constructor() {
    super()

    this._map = this._loadMap()
    this._stateListeners = new Set()
    this._eventListeners = new Set()
    this._anomalies = []
    this._snapshots = []
    this._lastSensors = { front: null, left: null, right: null, temperature: 35.0 }
    this._internalTemp = 35.0
    this._anomalyCooldowns = new Map()
    this._preChargeMode = 'manual'

    this._initRobotState()
    this._initPatrolState()

    // 用于调试与自动化截图脚本访问服务实例
    if (typeof window !== 'undefined') {
      window.robotService = this
    }

    this._startLoop()
  }

  /**
   * 初始化机器人状态。
   */
  _initRobotState() {
    const start = this._map.start
    this._state = {
      x: start[0],
      y: start[1],
      theta: 0,
      battery: 100.0,
      speed: 0.0,
      mode: 'manual',
      path: [],
      sensors: { front: null, left: null, right: null, temperature: 35.0 },
    }
    this._visitedTrail = [[start[0], start[1]]]
  }

  /**
   * 初始化巡检任务状态。
   */
  _initPatrolState() {
    this._patrol = {
      running: false,
      goals: [],
      currentGoalIndex: 0,
      totalGoals: 0,
      pathRemain: 0,
    }
  }

  /**
   * 启动仿真循环。
   */
  _startLoop() {
    this._tickInterval = setInterval(() => this._tick(), TICK_MS)
  }

  /**
   * 停止仿真循环（主要用于测试清理）。
   */
  _stopLoop() {
    if (this._tickInterval) {
      clearInterval(this._tickInterval)
      this._tickInterval = null
    }
  }

  /**
   * 单个仿真 tick：推进状态、消耗电量、更新传感器、检测异常。
   */
  _tick() {
    this._updateBatteryAndTemperature(false)

    // 低电量优先处理：自动返回充电点
    if (this._state.battery < LOW_BATTERY_THRESHOLD && this._state.mode !== 'charging') {
      this._enterChargingMode()
    }

    if (this._state.mode === 'charging') {
      this._processCharging()
    } else if (this._patrol.running) {
      this._processPatrol()
    } else {
      // 手动模式下静止，仅保持传感器刷新
      this._state.speed = 0.0
    }

    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
  }

  /**
   * 进入充电模式：记录先前模式并规划到充电点的路径。
   */
  _enterChargingMode() {
    this._preChargeMode = this._state.mode
    this._state.mode = 'charging'
    const pathResult = astar(this._map.grid, [this._state.x, this._state.y], this._map.charge_point)
    this._state.path = pathResult.path
    this._addAnomaly(
      'low_battery',
      `电量低于 ${LOW_BATTERY_THRESHOLD}%，自动返回充电点`,
      [this._state.x, this._state.y]
    )
  }

  /**
   * 处理充电逻辑。
   */
  _processCharging() {
    const charge = this._map.charge_point
    if (this._state.x === charge[0] && this._state.y === charge[1]) {
      this._state.battery = Math.min(100.0, this._state.battery + CHARGE_RATE)
      this._state.speed = 0.0
      if (this._state.battery >= 90.0) {
        this._state.mode = this._preChargeMode === 'patrol' && this._patrol.currentGoalIndex < this._patrol.totalGoals ? 'patrol' : 'manual'
        this._emitEvent('notice', { message: '充电完成，继续当前任务' })
      }
    } else {
      this._followPath()
    }
  }

  /**
   * 处理巡检任务逻辑。
   */
  _processPatrol() {
    if (!this._state.path || this._state.path.length <= 1) {
      this._patrol.currentGoalIndex += 1
      if (this._patrol.currentGoalIndex >= this._patrol.totalGoals) {
        this._patrol.running = false
        this._state.mode = 'manual'
        this._state.path = []
        this._emitEvent('notice', { message: '巡检任务已完成，可进入路径回放' })
        return
      }
      this._planToCurrentGoal()
    }
    if (this._state.path && this._state.path.length > 1) {
      this._followPath()
    }
  }

  /**
   * 沿当前路径前进一步。
   */
  _followPath() {
    const next = this._state.path[1]
    if (this._canMoveTo(next)) {
      this._moveTo(next)
      this._state.path.shift()
      this._updateBatteryAndTemperature(true)
      if (this._patrol.running) {
        this._patrol.pathRemain = Math.max(0, this._state.path.length - 1)
      }
    } else {
      this._setBlocked()
    }
  }

  /**
   * 移动到指定栅格。
   *
   * @param {number[]} next - 目标栅格 [x, y]。
   */
  _moveTo(next) {
    const dx = next[0] - this._state.x
    const dy = next[1] - this._state.y
    this._state.x = next[0]
    this._state.y = next[1]
    this._state.theta = this._directionToTheta(dx, dy)
    this._state.speed = 1.0
    this._visitedTrail.push([next[0], next[1]])
  }

  /**
   * 将方向增量转换为朝向角度（弧度）。
   *
   * @param {number} dx - x 方向增量。
   * @param {number} dy - y 方向增量。
   * @returns {number} 弧度值。
   */
  _directionToTheta(dx, dy) {
    if (dx > 0) return 0
    if (dx < 0) return Math.PI
    if (dy > 0) return Math.PI / 2
    if (dy < 0) return -Math.PI / 2
    return this._state.theta
  }

  /**
   * 判断机器人是否可以移动到目标栅格。
   *
   * @param {number[]} pos - 目标坐标 [x, y]。
   * @returns {boolean} 是否可移动。
   */
  _canMoveTo(pos) {
    const [x, y] = pos
    if (x < 0 || x >= this._map.width || y < 0 || y >= this._map.height) {
      return false
    }
    return this._map.grid[y][x] === 0
  }

  /**
   * 设置阻塞状态并触发异常。
   */
  _setBlocked() {
    this._state.mode = 'blocked'
    this._state.speed = 0.0
    this._addAnomaly('obstacle', '前方遇到障碍物，机器人已停止', [this._state.x, this._state.y])
    if (this._patrol.running) {
      this._patrol.running = false
    }
  }

  /**
   * 更新电量与内部温度。
   *
   * @param {boolean} moving - 本 tick 是否发生移动。
   */
  _updateBatteryAndTemperature(moving) {
    if (this._state.mode !== 'charging') {
      const cost = moving ? BATTERY_MOVE_COST : BATTERY_IDLE_COST
      this._state.battery = Math.max(0.0, parseFloat((this._state.battery - cost).toFixed(2)))
    }

    if (moving) {
      this._internalTemp += 0.1
    } else {
      this._internalTemp = Math.max(35.0, this._internalTemp - 0.05)
    }
  }

  /**
   * 更新三向距离传感器与温度读数，并检测传感器突变异常。
   */
  _updateSensors() {
    const front = this._castRay(this._state.theta)
    const left = this._castRay(this._state.theta - Math.PI / 2)
    const right = this._castRay(this._state.theta + Math.PI / 2)
    const noise = (Math.random() - 0.5) * 0.2
    const temperature = parseFloat((this._internalTemp + noise).toFixed(2))

    const sensors = {
      front: front === null ? null : parseFloat((front + noise).toFixed(2)),
      left: left === null ? null : parseFloat((left + noise).toFixed(2)),
      right: right === null ? null : parseFloat((right + noise).toFixed(2)),
      temperature,
    }

    this._detectSensorJump(sensors)
    this._detectOverheat(sensors.temperature)

    this._lastSensors = { ...sensors }
    this._state.sensors = sensors
  }

  /**
   * 沿给定角度投射射线，返回最近障碍物距离（米），超程返回 null。
   *
   * @param {number} theta - 射线角度（弧度）。
   * @returns {number|null} 障碍物距离或 null。
   */
  _castRay(theta) {
    const dir = this._thetaToDirection(theta)
    for (let step = 1; step <= SENSOR_MAX_CELLS; step += 1) {
      const cx = this._state.x + dir[0] * step
      const cy = this._state.y + dir[1] * step
      if (cx < 0 || cx >= this._map.width || cy < 0 || cy >= this._map.height) {
        return null
      }
      if (this._map.grid[cy][cx] === 1) {
        return step * CELL_METERS
      }
    }
    return null
  }

  /**
   * 将角度近似为四方向单位向量。
   *
   * @param {number} theta - 弧度。
   * @returns {number[]} 单位方向向量 [dx, dy]。
   */
  _thetaToDirection(theta) {
    const normalized = ((theta % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)
    const half = Math.PI / 4
    if (normalized < half || normalized >= 7 * half) return [1, 0]
    if (normalized < 3 * half) return [0, 1]
    if (normalized < 5 * half) return [-1, 0]
    return [0, -1]
  }

  /**
   * 检测传感器读数是否发生突变。
   *
   * @param {Object} sensors - 当前传感器读数。
   */
  _detectSensorJump(sensors) {
    const names = ['front', 'left', 'right']
    for (const name of names) {
      const current = sensors[name]
      const previous = this._lastSensors[name]
      if (current === null || previous === null) {
        continue
      }
      if (Math.abs(current - previous) >= SENSOR_JUMP_THRESHOLD) {
        this._addAnomaly(
          'sensor_fault',
          `${name === 'front' ? '前方' : name === 'left' ? '左侧' : '右侧'}传感器读数异常跳变`,
          [this._state.x, this._state.y]
        )
        break
      }
    }
  }

  /**
   * 检测温度是否过热。
   *
   * @param {number} temperature - 当前温度。
   */
  _detectOverheat(temperature) {
    if (temperature > OVERHEAT_THRESHOLD) {
      this._addAnomaly(
        'overheat',
        `机身温度过高：${temperature}℃`,
        [this._state.x, this._state.y]
      )
    }
  }

  /**
   * 添加异常事件，并做冷却去重。
   *
   * @param {string} type - 异常类型。
   * @param {string} message - 异常描述。
   * @param {number[]} position - 异常发生位置 [x, y]。
   */
  _addAnomaly(type, message, position) {
    const now = Date.now()
    const lastTime = this._anomalyCooldowns.get(type) || 0
    if (now - lastTime < ANOMALY_COOLDOWN_MS) {
      return
    }
    this._anomalyCooldowns.set(type, now)

    const anomaly = {
      time: new Date().toISOString(),
      type,
      message,
      position,
    }
    this._anomalies.unshift(anomaly)
    if (this._anomalies.length > 200) {
      this._anomalies.pop()
    }
    this._emitEvent('anomaly', anomaly)
  }

  /**
   * 记录当前 tick 的状态快照，用于回放。
   */
  _recordSnapshot() {
    this._snapshots.push({
      time: Date.now(),
      x: this._state.x,
      y: this._state.y,
      theta: this._state.theta,
      battery: this._state.battery,
      mode: this._state.mode,
      path: this._state.path.map((p) => [...p]),
      visitedTrail: this._visitedTrail.map((p) => [...p]),
      sensors: { ...this._state.sensors },
    })
    // 限制回放长度，防止内存无限增长
    if (this._snapshots.length > 5000) {
      this._snapshots.shift()
    }
  }

  /**
   * 使用最近邻贪心算法对巡检点排序。
   *
   * @param {number[][]} goals - 原始巡检点数组。
   * @returns {number[][]} 排序后的巡检点数组。
   */
  _orderGoals(goals) {
    const remaining = goals.map((g) => [...g])
    const ordered = []
    let current = [this._state.x, this._state.y]
    while (remaining.length > 0) {
      remaining.sort((a, b) => this._manhattan(current, a) - this._manhattan(current, b))
      const next = remaining.shift()
      ordered.push(next)
      current = next
    }
    return ordered
  }

  /**
   * 计算曼哈顿距离。
   *
   * @param {number[]} a - 坐标 [x, y]。
   * @param {number[]} b - 坐标 [x, y]。
   * @returns {number} 曼哈顿距离。
   */
  _manhattan(a, b) {
    return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1])
  }

  /**
   * 为当前巡检点规划 A* 路径。
   */
  _planToCurrentGoal() {
    const goal = this._patrol.goals[this._patrol.currentGoalIndex]
    const result = astar(this._map.grid, [this._state.x, this._state.y], goal)
    if (result.path.length === 0) {
      this._addAnomaly('obstacle', `无法到达巡检点 [${goal[0]}, ${goal[1]}]`, [this._state.x, this._state.y])
      this._patrol.currentGoalIndex += 1
      if (this._patrol.currentGoalIndex >= this._patrol.totalGoals) {
        this._patrol.running = false
        this._state.mode = 'manual'
        this._state.path = []
        this._emitEvent('notice', { message: '巡检任务已完成，可进入路径回放' })
        return
      }
      this._planToCurrentGoal()
      return
    }
    this._state.path = result.path
    this._patrol.pathRemain = Math.max(0, result.path.length - 1)
  }

  /**
   * 推送 state 帧到所有监听器。
   */
  _emitState() {
    const frame = {
      type: 'state',
      data: {
        x: this._state.x,
        y: this._state.y,
        theta: this._state.theta,
        battery: this._state.battery,
        speed: this._state.speed,
        mode: this._state.mode,
        path: this._state.path.map((p) => [...p]),
        sensors: { ...this._state.sensors },
      },
    }
    for (const callback of this._stateListeners) {
      try {
        callback(frame)
      } catch (error) {
        console.error('状态回调执行失败：', error)
      }
    }
  }

  /**
   * 推送事件帧到所有监听器。
   *
   * @param {string} eventType - 事件类型（anomaly / notice）。
   * @param {Object} data - 事件载荷。
   */
  _emitEvent(eventType, data) {
    const frame = { type: eventType, data }
    for (const callback of this._eventListeners) {
      try {
        callback(frame)
      } catch (error) {
        console.error('事件回调执行失败：', error)
      }
    }
  }

  /**
   * 从 localStorage 加载地图，不存在则生成默认地图。
   *
   * @returns {Object} 地图对象。
   */
  _loadMap() {
    try {
      const stored = localStorage.getItem(STORAGE_MAP_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed && parsed.grid && parsed.width && parsed.height) {
          return parsed
        }
      }
    } catch (error) {
      console.warn('地图本地存储加载失败，使用默认地图：', error)
    }
    return this._createDefaultMap()
  }

  /**
   * 将当前地图保存到 localStorage。
   */
  _saveMap() {
    try {
      localStorage.setItem(STORAGE_MAP_KEY, JSON.stringify(this._map))
    } catch (error) {
      console.warn('地图本地存储保存失败：', error)
    }
  }

  /**
   * 生成默认栅格地图。
   *
   * @returns {Object} 默认地图对象。
   */
  _createDefaultMap() {
    const grid = Array.from({ length: DEFAULT_HEIGHT }, () => Array(DEFAULT_WIDTH).fill(0))

    // 四周边界设为障碍物
    for (let x = 0; x < DEFAULT_WIDTH; x += 1) {
      grid[0][x] = 1
      grid[DEFAULT_HEIGHT - 1][x] = 1
    }
    for (let y = 0; y < DEFAULT_HEIGHT; y += 1) {
      grid[y][0] = 1
      grid[y][DEFAULT_WIDTH - 1] = 1
    }

    // 内部障碍物
    const obstacles = [
      [5, 3], [6, 3], [7, 3], [8, 3],
      [12, 5], [12, 6], [12, 7],
      [18, 4], [19, 4], [20, 4],
      [4, 12], [5, 12], [6, 12],
      [15, 13], [16, 13], [17, 13], [18, 13],
      [22, 10], [22, 11], [22, 12],
      [10, 16], [11, 16], [12, 16],
    ]
    for (const [x, y] of obstacles) {
      if (x > 0 && x < DEFAULT_WIDTH - 1 && y > 0 && y < DEFAULT_HEIGHT - 1) {
        grid[y][x] = 1
      }
    }

    return {
      width: DEFAULT_WIDTH,
      height: DEFAULT_HEIGHT,
      grid,
      start: [1, 1],
      goals: [
        [5, 5],
        [15, 8],
        [25, 5],
        [10, 15],
        [20, 16],
      ],
      charge_point: [DEFAULT_WIDTH - 2, DEFAULT_HEIGHT - 2],
    }
  }

  // ------------------------------------------------------------------------
  // 公共接口实现
  // ------------------------------------------------------------------------

  /**
   * 获取当前地图。
   * @returns {Object} 地图对象。
   */
  getMap() {
    return this._map
  }

  /**
   * 更新地图并持久化。
   * @param {Object} map - 完整地图对象。
   */
  updateMap(map) {
    this._map = map
    this._saveMap()
  }

  /**
   * 手动移动机器人。
   * @param {number} dx - x 方向增量。
   * @param {number} dy - y 方向增量。
   */
  move(dx, dy) {
    if (dx === 0 && dy === 0) {
      return
    }
    const target = [this._state.x + dx, this._state.y + dy]
    if (this._canMoveTo(target)) {
      this._moveTo(target)
      this._updateBatteryAndTemperature(true)
      this._state.path = []
      this._state.mode = 'manual'
      if (this._patrol.running) {
        this._patrol.running = false
        this._emitEvent('notice', { message: '手动控制已中断自动巡检' })
      }
      this._updateSensors()
      this._recordSnapshot()
      this._emitState()
    } else {
      this._setBlocked()
      this._emitState()
    }
  }

  /**
   * 将机器人复位到起点。
   */
  reset() {
    this._initRobotState()
    this._initPatrolState()
    this._internalTemp = 35.0
    this._snapshots = []
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', { message: '机器人已复位到起点' })
  }

  /**
   * 计算 A* 路径。
   * @param {number[]} start - 起点 [x, y]。
   * @param {number[]} goal - 终点 [x, y]。
   * @returns {Object} { path, visited_count, cost }。
   */
  computePath(start, goal) {
    return astar(this._map.grid, start, goal)
  }

  /**
   * 开始自动巡检。
   * @param {number[][]} goals - 巡检点数组，缺省时使用地图预设巡检点。
   */
  startPatrol(goals) {
    const targetGoals = goals && goals.length > 0 ? goals : this._map.goals
    if (targetGoals.length === 0) {
      this._emitEvent('notice', { message: '没有可用的巡检点' })
      return
    }
    this._snapshots = []
    this._patrol = {
      running: true,
      goals: this._orderGoals(targetGoals),
      currentGoalIndex: 0,
      totalGoals: targetGoals.length,
      pathRemain: 0,
    }
    this._state.mode = 'patrol'
    this._planToCurrentGoal()
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
  }

  /**
   * 停止自动巡检。
   */
  stopPatrol() {
    this._patrol.running = false
    this._state.mode = 'manual'
    this._state.path = []
    this._emitEvent('notice', { message: '自动巡检已停止' })
    this._emitState()
  }

  /**
   * 获取当前巡检状态。
   * @returns {Object} { running, current_goal, progress, path_remain }。
   */
  getPatrolStatus() {
    const currentGoal =
      this._patrol.running && this._patrol.currentGoalIndex < this._patrol.totalGoals
        ? this._patrol.goals[this._patrol.currentGoalIndex]
        : null
    let progress = 0
    if (this._patrol.totalGoals > 0) {
      progress = Math.round((this._patrol.currentGoalIndex / this._patrol.totalGoals) * 100)
    }
    return {
      running: this._patrol.running,
      current_goal: currentGoal,
      progress,
      path_remain: this._patrol.pathRemain,
    }
  }

  /**
   * 获取最新传感器数据。
   * @returns {Object} 传感器数据。
   */
  getSensors() {
    return { ...this._state.sensors }
  }

  /**
   * 获取历史异常事件列表。
   * @returns {Object[]} 异常事件数组。
   */
  getAnomalies() {
    return [...this._anomalies]
  }

  /**
   * 注册状态回调。
   * @param {Function} callback - 回调函数。
   * @returns {Function} 取消订阅函数。
   */
  onState(callback) {
    this._stateListeners.add(callback)
    // 立即推送一次当前状态，避免界面空白
    this._emitState()
    return () => {
      this._stateListeners.delete(callback)
    }
  }

  /**
   * 注册事件回调。
   * @param {Function} callback - 回调函数。
   * @returns {Function} 取消订阅函数。
   */
  onEvent(callback) {
    this._eventListeners.add(callback)
    return () => {
      this._eventListeners.delete(callback)
    }
  }

  /**
   * 获取回放快照数据。
   * @returns {Object[]} 状态快照数组。
   */
  getSnapshots() {
    return [...this._snapshots]
  }

  /**
   * 获取已访问轨迹。
   * @returns {number[][]} 坐标数组。
   */
  getVisitedTrail() {
    return this._visitedTrail.map((p) => [...p])
  }

  /**
   * 清空历史异常事件。
   */
  clearAnomalies() {
    this._anomalies = []
    this._anomalyCooldowns.clear()
  }
}
