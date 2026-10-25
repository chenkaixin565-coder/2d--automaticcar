/**
 * 模块功能：本地仿真器服务实现
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 本模块在前端完全模拟后端行为：200ms 推进一次仿真 tick，生成传感器数据、
 * 检测异常、执行巡检任务，并通过 onState/onEvent 推送与后端 WebSocket 协议
 * 逐字段一致的数据帧。下一阶段替换为 RemoteService 时，界面组件无需修改。
 */

import { RobotService } from './robotService.js'
import { astar } from './astar.js'
import { buildPlan } from './routePlanner.js'
import { MAP_PRESETS, getPreset } from './mapPresets.js'
import { enforceBorder, isBoundaryCell } from '../utils/mapBoundary.js'

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

/** 每清除一处障碍消耗的电量百分比（与后端 CLEAR_OBSTACLE_COST 一致）。 */
const CLEAR_OBSTACLE_COST = 5.0

/** 过热告警阈值（摄氏度）。 */
const OVERHEAT_THRESHOLD = 60.0

/** 传感器读数突变告警阈值（米）。 */
const SENSOR_JUMP_THRESHOLD = 2.0

/** 同一类异常的最小冷却时间（毫秒），避免重复刷屏。 */
const ANOMALY_COOLDOWN_MS = 5000

/** localStorage 中地图数据的键名。 */
const STORAGE_MAP_KEY = 'irm_map_v1'

/** localStorage 中当前内置地图预设标识的键名。 */
const STORAGE_PRESET_KEY = 'irm_map_preset_v1'

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
    // 一键路线规划结果（含电力预算），未规划时为 null，随 state 帧下发
    this._plan = null
    // 低电量且充电点不可达的告警去重标记
    this._chargeUnreachableNotified = false
    // 本 tick 是否发生移动（电量在 tick 末尾按此结算，与后端一致）
    this._movedThisTick = false

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
      // 巡检受阻且无法绕行时，前方待清障障碍格 [x, y]；无阻碍为 null
      blockedBy: null,
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
    // 空电状态：不移动、不巡检、不再耗电，仅保持传感器刷新，
    // 等待用户在弹窗中确认后搬回起点
    if (this._state.mode === 'empty') {
      this._state.speed = 0.0
      this._updateSensors()
      this._recordSnapshot()
      this._emitState()
      return
    }

    // 本 tick 是否发生移动由 _moveTo 打标，电量在 tick 末尾统一结算，
    // 与后端 simulation_engine.tick 的“移动/静止/充电三种速率”一致
    this._movedThisTick = false

    // 低电量优先处理：充电点可达才自动返回充电点
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

    this._updateBatteryAndTemperature(this._movedThisTick)
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()

    // 电量耗尽：进入空电状态并停止移动，等待用户确认后搬回起点
    if (this._state.battery <= 0 && this._state.mode !== 'empty') {
      this._state.mode = 'empty'
      this._state.speed = 0.0
      this._state.path = []
      this._emitEvent('notice', { message: '机器人电量耗尽，已停止移动' })
      this._emitState()
    }
  }

  /**
   * 进入充电模式：记录先前模式并规划到充电点的路径。
   * 充电点不可达时不返航（告警一次），电量将继续耗尽直至空电。
   */
  _enterChargingMode() {
    const pathResult = astar(this._map.grid, [this._state.x, this._state.y], this._map.charge_point)
    if (pathResult.path.length === 0) {
      if (!this._chargeUnreachableNotified) {
        this._chargeUnreachableNotified = true
        this._addAnomaly(
          'low_battery',
          '电量过低且充电点不可达，电量将持续耗尽',
          [this._state.x, this._state.y]
        )
      }
      return
    }
    this._preChargeMode = this._state.mode
    this._state.mode = 'charging'
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
        this._chargeUnreachableNotified = false
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
   * 巡检模式下路径格被占用时不触发撞障告警，转 _handlePatrolBlocked
   * 优先绕行、绕不动则标记待清障目标（V1.2）。
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
    } else if (this._patrol.running) {
      this._handlePatrolBlocked(next)
    } else {
      this._setBlocked()
    }
  }

  /**
   * 巡检路径受阻处理（V1.2）：优先重规划绕行；无法绕行时把前方障碍
   * 标记为“待清障目标”，由用户一键清除后继续巡检，不中断巡检、不报障告警。
   *
   * @param {number[]} blockedCell - 被占用的路径格 [x, y]。
   */
  _handlePatrolBlocked(blockedCell) {
    const goal = this._patrol.goals[this._patrol.currentGoalIndex]
    if (goal) {
      const detour = astar(this._map.grid, [this._state.x, this._state.y], goal)
      if (detour.path.length > 1) {
        this._state.path = detour.path
        this._patrol.pathRemain = Math.max(0, detour.path.length - 1)
        if (this._patrol.blockedBy) {
          this._patrol.blockedBy = null
          this._emitEvent('notice', { message: '已自动绕开障碍，继续巡检' })
        }
        return
      }
    }
    const changed =
      !this._patrol.blockedBy ||
      this._patrol.blockedBy[0] !== blockedCell[0] ||
      this._patrol.blockedBy[1] !== blockedCell[1]
    if (changed) {
      this._patrol.blockedBy = [blockedCell[0], blockedCell[1]]
      this._emitEvent('notice', {
        message: `巡检受阻：前方 [${blockedCell[0]}, ${blockedCell[1]}] 有障碍，可一键清障（不会中断巡检）`,
      })
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
    this._movedThisTick = true
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
   * 计费规则与后端一致：仅“已到达充电点且静止充电”时不耗电；
   * 返航途中与普通移动一样按格计费，静止时按 idle 速率漏电。
   *
   * @param {boolean} moving - 本 tick 是否发生移动。
   */
  _updateBatteryAndTemperature(moving) {
    const charge = this._map.charge_point
    const atChargePoint = this._state.x === charge[0] && this._state.y === charge[1]
    const chargingAtPoint = this._state.mode === 'charging' && !moving && atChargePoint
    if (!chargingAtPoint) {
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
        plan: this._plan,
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
   * 同时恢复上次使用的内置地图预设标识（自定义地图时为 null）。
   *
   * @returns {Object} 地图对象。
   */
  _loadMap() {
    let presetKey = null
    try {
      presetKey = localStorage.getItem(STORAGE_PRESET_KEY)
    } catch {
      // localStorage 不可用时忽略，按无预设处理
    }
    try {
      const stored = localStorage.getItem(STORAGE_MAP_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed && parsed.grid && parsed.width && parsed.height) {
          this._presetKey = presetKey
          return parsed
        }
      }
    } catch (error) {
      console.warn('地图本地存储加载失败，使用默认地图：', error)
    }
    // 全新用户：默认地图即"默认厂房"预设
    this._presetKey = presetKey || 'factory'
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
   * 持久化当前内置地图预设标识（自定义地图时清除）。
   */
  _savePresetKey() {
    try {
      if (this._presetKey) {
        localStorage.setItem(STORAGE_PRESET_KEY, this._presetKey)
      } else {
        localStorage.removeItem(STORAGE_PRESET_KEY)
      }
    } catch (error) {
      console.warn('地图预设标识保存失败：', error)
    }
  }

  /**
   * 生成默认栅格地图（即"默认厂房"预设）。
   *
   * @returns {Object} 默认地图对象。
   */
  _createDefaultMap() {
    return getPreset('factory')
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
   * 本地仿真模式下地图即权威来源，直接返回当前地图
   * （与 RemoteService.fetchMap 保持接口对称）。
   * @returns {Promise<Object>} 当前地图对象。
   */
  async fetchMap() {
    return this._map
  }

  /**
   * 更新地图并持久化。地图被编辑后即视为自定义地图，清除预设标识。
   * @param {Object} map - 完整地图对象。
   */
  updateMap(map) {
    // 真正的边界：任何地图更新都强制补齐四周边界墙
    enforceBorder(map.grid, map.width, map.height)
    this._map = map
    this._presetKey = null
    // 地图整体变更后旧规划失去意义，直接作废
    this._plan = null
    this._saveMap()
    this._savePresetKey()
  }

  /**
   * 切换内置地图预设：整图替换、机器人复位到新起点并持久化。
   * @param {string} key - 预设标识（factory / warehouse / dense）。
   */
  loadPreset(key) {
    const presetMap = getPreset(key)
    if (!presetMap) {
      this._emitEvent('notice', { message: '未找到该内置地图' })
      return
    }
    // 真正的边界：预设同样强制补齐边界墙
    enforceBorder(presetMap.grid, presetMap.width, presetMap.height)
    this._map = presetMap
    this._presetKey = key
    this._plan = null
    this._saveMap()
    this._savePresetKey()
    // 机器人复位到新地图起点，避免停留在可能变为障碍的位置
    this._initRobotState()
    this._initPatrolState()
    this._internalTemp = 35.0
    this._snapshots = []
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    const name = MAP_PRESETS.find((item) => item.key === key)
    this._emitEvent('notice', { message: `已切换内置地图：${name ? name.name : key}` })
  }

  /**
   * 获取当前地图对应的预设标识，自定义地图返回 null。
   * @returns {string|null} 预设标识。
   */
  getPresetKey() {
    return this._presetKey
  }

  /**
   * 手动移动机器人。
   * @param {number} dx - x 方向增量。
   * @param {number} dy - y 方向增量。
   */
  move(dx, dy) {
    if (this._state.mode === 'empty') {
      this._emitEvent('notice', { message: '电量耗尽，无法移动；请将机器人搬回初始点' })
      this._emitState()
      return
    }
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
    this._plan = null
    this._chargeUnreachableNotified = false
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', { message: '机器人已复位到起点' })
  }

  /**
   * 一键排障：机器人被障碍卡住（mode=blocked）时，按当前朝向找到正前方
   * 障碍格并清除，随后恢复正常控制；无阻塞时仅推送系统提示。
   * 与后端 SimulationEngine.resolve_fault 行为保持一致。
   */
  resolveFault() {
    if (this._state.mode !== 'blocked') {
      this._emitEvent('notice', { message: '当前无阻塞故障，无需排障' })
      return
    }
    const dir = this._thetaToDirection(this._state.theta)
    const target = [this._state.x + dir[0], this._state.y + dir[1]]
    if (
      target[0] >= 0 && target[0] < this._map.width &&
      target[1] >= 0 && target[1] < this._map.height &&
      this._map.grid[target[1]][target[0]] === 1
    ) {
      if (isBoundaryCell(target[0], target[1], this._map.width, this._map.height)) {
        // 边界墙不可清除：仅恢复控制权，提示用户转向脱离
        this._state.mode = 'manual'
        this._state.path = []
        this._updateSensors()
        this._recordSnapshot()
        this._emitState()
        this._emitEvent('notice', { message: '前方是固定边界墙，无法清除；请向其他方向移动脱离' })
        return
      }
      this._map.grid[target[1]][target[0]] = 0
      this._saveMap()
    }
    this._state.mode = 'manual'
    this._state.path = []
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', { message: '已排除前方障碍，恢复正常控制' })
  }

  /**
   * 一键规划路线（V1.2）：理论最短路径（可穿越普通障碍）+ 电力预算内的待清障目标。
   * 规划结果随 state 帧下发，界面据此绘制闪烁虚线与红色清障标记。
   *
   * @param {number[]} goal - 目标点坐标 [x, y]。
   * @returns {Object} 路线规划对象（字段与后端 build_plan 一致）。
   */
  planRoute(goal) {
    const plan = buildPlan(
      this._map.grid,
      [this._state.x, this._state.y],
      goal,
      this._state.battery,
      BATTERY_MOVE_COST,
      CLEAR_OBSTACLE_COST
    )
    if (plan.path.length === 0) {
      this._plan = null
      this._emitEvent('notice', { message: plan.message || '无法规划路线：目标不可达' })
      this._emitState()
      return plan
    }
    this._plan = plan
    this._emitEvent('notice', {
      message: `路线已规划：全程 ${plan.path.length - 1} 格，待清障 ${plan.obstacles.length} 个，预计耗电 ${plan.total_cost.toFixed(1)}%`,
    })
    this._emitState()
    return plan
  }

  /**
   * 地图/电量变化后按原目标重算路线规划（无规划时跳过，与后端 _refresh_plan 对应）。
   */
  _refreshPlan() {
    if (!this._plan) {
      return
    }
    this._plan = buildPlan(
      this._map.grid,
      [this._state.x, this._state.y],
      this._plan.goal,
      this._state.battery,
      BATTERY_MOVE_COST,
      CLEAR_OBSTACLE_COST
    )
  }

  /**
   * 清除指定障碍格（V1.2 手动清障 / 规划内清障）。
   *
   * 真正的边界：最外环边界墙不可清除；空电状态下不可执行；非障碍格拒绝。
   * 每清除一处扣除 CLEAR_OBSTACLE_COST 电量，并刷新当前路线规划。
   *
   * @param {number[]} cell - 障碍坐标 [x, y]。
   */
  clearObstacleAt(cell) {
    if (this._state.mode === 'empty') {
      this._emitEvent('notice', { message: '电量耗尽，无法清障；请将机器人搬回初始点' })
      this._emitState()
      return
    }
    const [x, y] = cell
    if (x < 0 || x >= this._map.width || y < 0 || y >= this._map.height) {
      this._emitEvent('notice', { message: '坐标越界，无法清障' })
      this._emitState()
      return
    }
    if (isBoundaryCell(x, y, this._map.width, this._map.height)) {
      this._emitEvent('notice', { message: '该位置是固定边界墙，无法清除' })
      this._emitState()
      return
    }
    if (this._map.grid[y][x] !== 1) {
      this._emitEvent('notice', { message: `位置 [${x}, ${y}] 没有障碍，无需清除` })
      this._emitState()
      return
    }
    this._map.grid[y][x] = 0
    this._state.battery = Math.max(0.0, parseFloat((this._state.battery - CLEAR_OBSTACLE_COST).toFixed(2)))
    this._emitEvent('notice', { message: `已清除障碍 [${x}, ${y}]，消耗电量 ${CLEAR_OBSTACLE_COST.toFixed(0)}%` })
    // 清除的正是巡检受阻点时解除标记，巡检将在下一 tick 恢复推进
    if (this._patrol.blockedBy && this._patrol.blockedBy[0] === x && this._patrol.blockedBy[1] === y) {
      this._patrol.blockedBy = null
    }
    this._saveMap()
    this._refreshPlan()
    this._emitState()
  }

  /**
   * 按当前路线规划批量清除电力预算内的障碍（每处扣除清障电量）。
   */
  executePlanClear() {
    if (this._state.mode === 'empty') {
      this._emitEvent('notice', { message: '电量耗尽，无法清障；请将机器人搬回初始点' })
      this._emitState()
      return
    }
    if (!this._plan || this._plan.clearable.length === 0) {
      this._emitEvent('notice', { message: '当前没有可执行的清障目标' })
      this._emitState()
      return
    }
    let cleared = 0
    for (const [x, y] of this._plan.clearable) {
      if (isBoundaryCell(x, y, this._map.width, this._map.height)) {
        continue
      }
      if (this._map.grid[y][x] !== 1) {
        continue
      }
      this._map.grid[y][x] = 0
      this._state.battery = Math.max(
        0.0,
        parseFloat((this._state.battery - CLEAR_OBSTACLE_COST).toFixed(2))
      )
      cleared += 1
    }
    this._patrol.blockedBy = null
    this._emitEvent('notice', {
      message: `已按规划清除 ${cleared} 处障碍，共耗电 ${(cleared * CLEAR_OBSTACLE_COST).toFixed(0)}%`,
    })
    this._saveMap()
    this._refreshPlan()
    this._emitState()
  }

  /**
   * 空电搬回（V1.2）：用户确认后将机器人传送回地图起点并恢复满电。
   * 与后端 carry_home 行为一致：停巡检、回起点、满电、手动模式、作废规划。
   */
  carryBackHome() {
    this._patrol.running = false
    const start = this._map.start
    this._state.x = start[0]
    this._state.y = start[1]
    this._state.theta = 0
    this._state.battery = 100.0
    this._state.mode = 'manual'
    this._state.path = []
    this._plan = null
    this._chargeUnreachableNotified = false
    this._visitedTrail.push([start[0], start[1]])
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', { message: '机器人已搬回初始点，电量已恢复 100%' })
  }

  /**
   * 取消当前路线规划（V1.2）：作废规划缓存，界面停止展示闪烁虚线与标记。
   */
  cancelPlan() {
    this._plan = null
    this._emitEvent('notice', { message: '路线规划已取消' })
    this._emitState()
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
      blockedBy: null,
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
   * @returns {Object} { running, current_goal, progress, path_remain, blocked_by }。
   *   blocked_by 为巡检受阻且无法绕行时前方待清障障碍格 [x, y]，无阻碍为 null。
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
      blocked_by: this._patrol.blockedBy,
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
