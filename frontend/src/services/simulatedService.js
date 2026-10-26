/**
 * 模块功能：本地仿真器服务实现
 * 作者：智能巡检机器人二维仿真系统 V2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.0
 *
 * 本模块在浏览器内完全模拟后端行为：200ms 推进一次仿真 tick，生成传感器数据、
 * 检测异常、执行巡检任务，并通过 onState/onEvent 推送与后端 WebSocket 协议
 * 逐字段一致的数据帧。
 *
 * V2.0 与后端 simulation_engine 对齐的关键规则：
 *   1. 移动耗电 0.2%/格，只在 tick 里结算一次（修复原先 0.4%/格的翻倍 bug）；
 *   2. 只有在充电点静止时才回血，离开即取消充电；
 *   3. 清障前校验电量，批量清障逐处判断，不会出现"1% 电量拆一排墙"；
 *   4. 巡检遇阻：停在障碍前一格并抛出 blocked 事件，由用户决定清除/跳过/停止；
 *   5. 跳过时把障碍写入待清障记录，支持"一键清最近"；
 *   6. 低电量自动返航，充满后自动继续原巡检任务；
 *   7. 巡检进度统一为 0~1（修复接后端时进度条永远 0% 的问题）。
 */

import { RobotService } from './robotService.js'
import { astar } from './astar.js'
import { buildPlan } from './routePlanner.js'
import { MAP_PRESETS, getPreset } from './mapPresets.js'
import { enforceBorder, isBoundaryCell } from '../utils/mapBoundary.js'
import { validateMap } from '../utils/mapIO.js'

/**
 * 仿真规则全部来自 `shared/simulation-rules.json`（与后端同一份），
 * 这里只保留纯前端使用的展示常量（快照上限、存储键名）。
 */
import {
  ANOMALY_LIMIT,
  BATTERY_IDLE_COST,
  BATTERY_MOVE_COST,
  CELL_METERS,
  CHARGE_RATE,
  CLEAR_OBSTACLE_COST,
  LOW_BATTERY_THRESHOLD,
  MAX_MAP_SIZE,
  MIN_MAP_SIZE,
  OVERHEAT_THRESHOLD,
  PENDING_LIMIT,
  SENSOR_FAULT_COOLDOWN_MS,
  SENSOR_JUMP_THRESHOLD,
  SENSOR_MAX_CELLS,
  TEMP_BASE,
  TEMP_COOL_PER_TICK,
  TEMP_MAX,
  TEMP_RISE_PER_MOVE,
} from './rules.js'

/** 仿真 tick 间隔，单位毫秒，与后端 WebSocket 推送频率一致。 */
const TICK_MS = 200

/** 同一类异常的最小冷却时间（毫秒），避免重复刷屏。 */
const ANOMALY_COOLDOWN_MS = 5000

/** 回放快照上限。 */
const SNAPSHOT_LIMIT = 3000

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
    this._lastSensors = { front: null, left: null, right: null, temperature: TEMP_BASE }
    this._internalTemp = TEMP_BASE
    this._anomalyCooldowns = new Map()
    this._faultCooldowns = new Map()
    this._preChargeMode = 'manual'
    // 一键路线规划结果（预览），未规划时为 null，随 state 帧下发
    this._plan = null
    // 低电量且充电点不可达的告警去重标记
    this._chargeUnreachableNotified = false
    // 本 tick 是否发生移动（电量在 tick 末尾按此结算）
    this._movedThisTick = false
    // 待清障记录（巡检跳过时写入）
    this._pending = []
    // 巡检遇阻暂停状态
    this._paused = false
    this._blocked = null
    // 充电前是否处于巡检状态（充满自动继续）
    this._resumePatrolAfterCharge = false

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
      sensors: { front: null, left: null, right: null, temperature: TEMP_BASE },
    }
    this._visitedTrail = [[start[0], start[1]]]
  }

  /**
   * 初始化巡检任务状态。
   */
  _initPatrolState() {
    this._patrol = {
      running: false,
      paused: false,
      goals: [],
      currentGoalIndex: 0,
      totalGoals: 0,
      pathRemain: 0,
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
    // 空电状态：不移动、不巡检、不再耗电，仅保持传感器刷新
    if (this._state.mode === 'empty') {
      this._state.speed = 0.0
      this._updateSensors()
      this._recordSnapshot()
      this._emitState()
      return
    }

    this._movedThisTick = false

    // 低电量优先处理：充电点可达才自动返回充电点
    if (this._state.battery < LOW_BATTERY_THRESHOLD && this._state.mode !== 'charging') {
      this._enterChargingMode()
    }

    if (this._state.mode === 'charging') {
      this._processCharging()
    } else if (this._patrol.running && !this._paused) {
      this._processPatrol()
    } else if (this._paused) {
      this._state.speed = 0.0
    } else {
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
      this._paused = false
      this._blocked = null
      this._patrol.paused = false
      this._emitEvent('notice', { message: '机器人电量耗尽，已停止移动' })
      this._emitEvent('empty', { position: [this._state.x, this._state.y] })
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
        this._addAnomaly('low_battery', '电量过低且充电点不可达，电量将持续耗尽', [
          this._state.x,
          this._state.y,
        ])
      }
      return
    }
    this._preChargeMode = this._state.mode
    this._resumePatrolAfterCharge = this._patrol.running
    this._state.mode = 'charging'
    this._state.path = pathResult.path
    this._paused = false
    this._patrol.paused = false
    this._blocked = null
    this._addAnomaly(
      'low_battery',
      `电量低于 ${LOW_BATTERY_THRESHOLD}%，自动返回充电点`,
      [this._state.x, this._state.y]
    )
  }

  /**
   * 处理充电逻辑：只有停在充电点上才回血，充满后恢复原任务。
   */
  _processCharging() {
    const charge = this._map.charge_point
    const atCharge = this._state.x === charge[0] && this._state.y === charge[1]
    if (atCharge) {
      this._state.battery = Math.min(100.0, parseFloat((this._state.battery + CHARGE_RATE).toFixed(2)))
      this._state.speed = 0.0
      if (this._state.battery >= 100.0) {
        this._chargeUnreachableNotified = false
        if (this._resumePatrolAfterCharge && this._patrol.running) {
          this._state.mode = 'patrol'
          this._planToCurrentGoal()
          this._emitEvent('notice', { message: '充电完成（100%），继续巡检' })
        } else {
          this._state.mode = 'manual'
          this._emitEvent('notice', { message: '充电完成（100%）' })
        }
        this._resumePatrolAfterCharge = false
      }
    } else if (this._state.path && this._state.path.length > 1) {
      this._followPath()
    } else {
      // 路径失效：重新规划；实在到不了就放弃返航，避免原地"假装充电"。
      const retry = astar(this._map.grid, [this._state.x, this._state.y], charge)
      if (retry.path.length > 1) {
        this._state.path = retry.path
      } else {
        this._state.mode = 'manual'
        this._state.path = []
        this._emitEvent('notice', { message: '充电点不可达，已退出返航' })
      }
    }
  }

  /**
   * 处理巡检任务逻辑。
   */
  _processPatrol() {
    if (!this._state.path || this._state.path.length <= 1) {
      this._patrol.currentGoalIndex += 1
      if (this._patrol.currentGoalIndex >= this._patrol.totalGoals) {
        this._finishPatrol()
        return
      }
      this._planToCurrentGoal()
    }
    if (this._state.path && this._state.path.length > 1) {
      this._followPath()
    }
  }

  /**
   * 结束巡检：保留进度（不再把 completed 清零）。
   */
  _finishPatrol() {
    this._patrol.running = false
    this._patrol.paused = false
    this._patrol.currentGoalIndex = this._patrol.totalGoals
    this._patrol.pathRemain = 0
    this._paused = false
    this._blocked = null
    this._state.mode = 'manual'
    this._state.path = []
    this._state.speed = 0.0
    this._emitEvent('notice', { message: '巡检任务已完成，可进入路径回放' })
    this._emitState()
  }

  /**
   * 沿当前路径前进一步（电量在本 tick 末尾统一结算，避免重复扣电）。
   */
  _followPath() {
    const next = this._state.path[1]
    if (this._canMoveTo(next)) {
      this._moveTo(next)
      this._state.path.shift()
      if (this._patrol.running) {
        this._patrol.pathRemain = Math.max(0, this._state.path.length - 1)
      }
    } else if (this._patrol.running && !this._paused) {
      this._handlePatrolBlocked(next)
    } else {
      this._setBlocked()
    }
  }

  /**
   * 巡检路径受阻：优先重规划绕行；绕不动则暂停并抛出 blocked 事件等待用户决策。
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
        if (this._blocked || this._paused) {
          this._blocked = null
          this._paused = false
          this._patrol.paused = false
          this._patrol.blockedBy = null
          this._emitEvent('notice', { message: '已自动绕开障碍，继续巡检' })
        }
        return
      }
    }

    this._paused = true
    this._patrol.paused = true
    this._patrol.blockedBy = [blockedCell[0], blockedCell[1]]
    const isBarrier = this._map.grid[blockedCell[1]][blockedCell[0]] === 2
    this._blocked = {
      cell: [blockedCell[0], blockedCell[1]],
      reason: isBarrier ? 'barrier' : 'obstacle',
    }
    this._state.speed = 0.0
    this._emitEvent('blocked', {
      cell: [blockedCell[0], blockedCell[1]],
      reason: isBarrier ? 'barrier' : 'obstacle',
      message: isBarrier
        ? `巡检受阻：前方 [${blockedCell[0]}, ${blockedCell[1]}] 是固定屏障，无法清除，只能绕行或跳过`
        : `巡检受阻：前方 [${blockedCell[0]}, ${blockedCell[1]}] 有障碍，是否清除？`,
      battery: Math.round(this._state.battery * 10) / 10,
      clear_cost: CLEAR_OBSTACLE_COST,
    })
    this._emitState()
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
    this._internalTemp = Math.min(TEMP_MAX, this._internalTemp + TEMP_RISE_PER_MOVE)
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
      this._patrol.paused = false
    }
  }

  /**
   * 更新电量与内部温度。
   *
   * 计费规则与后端一致：本 tick 发生移动扣移动耗电；否则扣待机耗电（默认 0）。
   * 充电回血只在"停在充电点"时由 _processCharging 处理，这里不重复计算。
   *
   * @param {boolean} moving - 本 tick 是否发生移动。
   */
  _updateBatteryAndTemperature(moving) {
    if (moving) {
      this._state.battery = Math.max(0.0, parseFloat((this._state.battery - BATTERY_MOVE_COST).toFixed(2)))
    } else {
      if (BATTERY_IDLE_COST > 0) {
        this._state.battery = Math.max(
          0.0,
          parseFloat((this._state.battery - BATTERY_IDLE_COST).toFixed(2))
        )
      }
      this._internalTemp = Math.max(TEMP_BASE, this._internalTemp - TEMP_COOL_PER_TICK)
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
   * 检测传感器读数是否发生突变（同一通道跨帧比较，跨方向差异不算故障）。
   *
   * @param {Object} sensors - 当前传感器读数。
   */
  _detectSensorJump(sensors) {
    const names = ['front', 'left', 'right']
    const now = Date.now()
    for (const name of names) {
      const current = sensors[name]
      const previous = this._lastSensors[name]
      if (current === null || previous === null) {
        continue
      }
      if (Math.abs(current - previous) < SENSOR_JUMP_THRESHOLD) {
        continue
      }
      const last = this._faultCooldowns.get(name) || 0
      if (now - last < SENSOR_FAULT_COOLDOWN_MS) {
        continue
      }
      this._faultCooldowns.set(name, now)
      this._addAnomaly(
        'sensor_fault',
        `${name === 'front' ? '正前方' : name === 'left' ? '左侧' : '右侧'}传感器读数异常跳变`,
        [this._state.x, this._state.y]
      )
      break
    }
  }

  /**
   * 检测温度是否过热。
   *
   * @param {number} temperature - 当前温度。
   */
  _detectOverheat(temperature) {
    if (temperature > OVERHEAT_THRESHOLD) {
      this._addAnomaly('overheat', `机身温度过高：${temperature}℃`, [this._state.x, this._state.y])
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
    if (this._anomalies.length > ANOMALY_LIMIT) {
      this._anomalies.pop()
    }
    this._emitEvent('anomaly', anomaly)
  }

  /**
   * 记录当前 tick 的状态快照，用于回放。
   *
   * 只记录尾迹长度而不是深拷贝整条尾迹：原先每帧复制一次，长跑后内存会爆。
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
      trailLen: this._visitedTrail.length,
      sensors: { ...this._state.sensors },
    })
    if (this._snapshots.length > SNAPSHOT_LIMIT) {
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
   * 为当前巡检点规划 A* 路径（不可达时跳过并继续下一个）。
   */
  _planToCurrentGoal() {
    for (let guard = 0; guard <= this._patrol.goals.length; guard += 1) {
      const goal = this._patrol.goals[this._patrol.currentGoalIndex]
      if (!goal) {
        this._state.path = []
        return
      }
      const result = astar(this._map.grid, [this._state.x, this._state.y], goal)
      if (result.path.length > 0) {
        this._state.path = result.path
        this._patrol.pathRemain = Math.max(0, result.path.length - 1)
        return
      }
      this._addAnomaly('obstacle', `无法到达巡检点 [${goal[0]}, ${goal[1]}]，已跳过`, [
        this._state.x,
        this._state.y,
      ])
      this._patrol.currentGoalIndex += 1
      if (this._patrol.currentGoalIndex >= this._patrol.totalGoals) {
        this._finishPatrol()
        return
      }
    }
    this._state.path = []
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
        patrol: this.getPatrolStatus(),
        plan: this._plan,
        paused: this._paused,
        blocked: this._blocked,
        pending: this._pending.map((c) => [...c]),
        trail_len: this._visitedTrail.length,
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
   * @param {string} eventType - 事件类型（anomaly / notice / blocked / empty）。
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
   * 从 localStorage 加载地图，不存在或数据损坏则回落到默认地图。
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
        const check = validateMap(parsed)
        if (check.ok) {
          this._presetKey = presetKey
          return check.map
        }
        console.warn('本地地图校验失败，已恢复默认地图：', check.error)
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
   * 本地仿真模式下地图即权威来源，直接返回当前地图。
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
    enforceBorder(map.grid, map.width, map.height)
    this._map = map
    this._presetKey = null
    this._plan = null
    this._paused = false
    this._blocked = null
    this._patrol.paused = false
    this._patrol.running = false
    this._patrol.blockedBy = null
    this._state.path = []
    this._pending = this._pending.filter(
      ([x, y]) => x > 0 && y > 0 && x < map.width - 1 && y < map.height - 1 && map.grid[y][x] === 1
    )
    // 机器人所在格被画成障碍时，复位到起点（与后端一致）。
    if (!this._canMoveTo([this._state.x, this._state.y])) {
      this._state.x = map.start[0]
      this._state.y = map.start[1]
      this._visitedTrail.push([this._state.x, this._state.y])
    }
    if (this._state.mode !== 'empty') {
      this._state.mode = 'manual'
    }
    this._saveMap()
    this._savePresetKey()
  }

  /**
   * 新建空白地图（仅保留四周边界墙）并复位机器人（V2.0）。
   *
   * @param {number} width - 宽度（列数）。
   * @param {number} height - 高度（行数）。
   */
  newMap(width, height) {
    const w = Math.max(MIN_MAP_SIZE, Math.min(MAX_MAP_SIZE, Math.round(width)))
    const h = Math.max(MIN_MAP_SIZE, Math.min(MAX_MAP_SIZE, Math.round(height)))
    const grid = Array.from({ length: h }, () => Array(w).fill(0))
    enforceBorder(grid, w, h)
    const map = {
      width: w,
      height: h,
      grid,
      start: [1, 1],
      goals: [],
      charge_point: [w - 2, h - 2],
    }
    this._map = map
    this._presetKey = null
    this._plan = null
    this._pending = []
    this._blocked = null
    this._paused = false
    this._initRobotState()
    this._initPatrolState()
    this._internalTemp = TEMP_BASE
    this._snapshots = []
    this._visitedTrail = [[1, 1]]
    this._saveMap()
    this._savePresetKey()
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', { message: `已新建 ${w}×${h} 空白地图，可直接绘制障碍与巡检点` })
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
    enforceBorder(presetMap.grid, presetMap.width, presetMap.height)
    this._map = presetMap
    this._presetKey = key
    this._plan = null
    this._pending = []
    this._blocked = null
    this._paused = false
    this._saveMap()
    this._savePresetKey()
    this._initRobotState()
    this._initPatrolState()
    this._internalTemp = TEMP_BASE
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
   * 手动移动机器人（会中断自动巡检与充电）。
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
      const wasPatrol = this._patrol.running
      const wasCharging = this._state.mode === 'charging'
      if (wasPatrol || wasCharging || this._paused) {
        this._patrol.running = false
        this._patrol.paused = false
        this._patrol.blockedBy = null
        this._paused = false
        this._blocked = null
        this._resumePatrolAfterCharge = false
        this._preChargeMode = 'manual'
      }
      this._moveTo(target)
      this._state.battery = Math.max(
        0.0,
        parseFloat((this._state.battery - BATTERY_MOVE_COST).toFixed(2))
      )
      this._state.path = []
      this._state.mode = 'manual'
      if (wasPatrol) {
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
   *
   * @param {boolean} keepTrail - true = 重新开始并保留尾迹；false = 连尾迹一起清空。
   */
  reset(keepTrail = false) {
    const trail = this._visitedTrail
    this._initRobotState()
    this._initPatrolState()
    this._internalTemp = TEMP_BASE
    this._snapshots = []
    this._plan = null
    this._paused = false
    this._blocked = null
    this._chargeUnreachableNotified = false
    this._resumePatrolAfterCharge = false
    if (keepTrail) {
      this._visitedTrail = [...trail, [this._state.x, this._state.y]]
    }
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', {
      message: keepTrail ? '机器人已重新开始，保留历史尾迹' : '机器人已复位到起点',
    })
  }

  /**
   * 重新开始：复位机器人但保留已走过的尾迹（V2.0）。
   */
  restart() {
    this.reset(true)
  }

  /**
   * 一键排障：机器人被障碍卡住（mode=blocked）时，按当前朝向找到正前方
   * 障碍格并清除，随后恢复正常控制；无阻塞时仅推送系统提示。
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
   * 一键规划路线（V2.0 语义：预览，不移动机器人）。
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
   * 地图/电量变化后按原目标重算路线规划（无规划时跳过）。
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
   * 编辑单个格子（V2.1）：地图编辑用，不消耗电量。
   *
   * @param {number} x - 列坐标。
   * @param {number} y - 行坐标。
   * @param {0|1|2} value - 0=通行 1=障碍 2=固定屏障。
   */
  setCell(x, y, value) {
    if (![0, 1, 2].includes(value)) return
    if (x < 0 || x >= this._map.width || y < 0 || y >= this._map.height) return
    if (isBoundaryCell(x, y, this._map.width, this._map.height)) {
      this._emitEvent('notice', { message: '最外环是地图边界，不能编辑' })
      return
    }
    const isKeyCell =
      (x === this._map.start[0] && y === this._map.start[1]) ||
      (x === this._map.charge_point[0] && y === this._map.charge_point[1]) ||
      this._map.goals.some((g) => g[0] === x && g[1] === y)
    if (value !== 0 && isKeyCell) {
      this._emitEvent('notice', { message: '该格是起点 / 充电点 / 巡检点，不能设为障碍或屏障' })
      return
    }
    if (value !== 0 && x === this._state.x && y === this._state.y) {
      this._emitEvent('notice', { message: '机器人正站在该格上，请先移动机器人' })
      return
    }
    this._map.grid[y][x] = value
    this._pending = this._pending.filter((c) => !(c[0] === x && c[1] === y))
    if (this._blocked && this._blocked.cell[0] === x && this._blocked.cell[1] === y && value === 0) {
      this._blocked = null
      this._paused = false
      this._patrol.paused = false
      this._patrol.blockedBy = null
    }
    this._saveMap()
    this._refreshPlan()
    this._emitState()
  }

  /**
   * 清除指定障碍格（手动清障 / 计划内清障）。
   *
   * 边界墙、非障碍格、空电、电量不足都会被拒绝；每处扣除固定清障电量。
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
    if (this._map.grid[y][x] === 2) {
      this._emitEvent('notice', {
        message: '该位置是固定屏障，机器人无法清除；请在「擦除」编辑模式下人工擦除',
      })
      this._emitState()
      return
    }
    if (this._map.grid[y][x] !== 1) {
      this._emitEvent('notice', { message: `位置 [${x}, ${y}] 没有障碍，无需清除` })
      this._emitState()
      return
    }
    if (this._state.battery < CLEAR_OBSTACLE_COST) {
      this._emitEvent('notice', {
        message: `电量不足（需 ${CLEAR_OBSTACLE_COST.toFixed(0)}%），无法清障；请先返航充电`,
      })
      this._emitState()
      return
    }
    this._map.grid[y][x] = 0
    this._state.battery = Math.max(
      0.0,
      parseFloat((this._state.battery - CLEAR_OBSTACLE_COST).toFixed(2))
    )
    this._emitEvent('notice', {
      message: `已清除障碍 [${x}, ${y}]，消耗电量 ${CLEAR_OBSTACLE_COST.toFixed(0)}%`,
    })
    this._pending = this._pending.filter((c) => !(c[0] === x && c[1] === y))
    if (this._blocked && this._blocked.cell[0] === x && this._blocked.cell[1] === y) {
      this._blocked = null
      this._paused = false
      this._patrol.paused = false
      this._patrol.blockedBy = null
      if (this._patrol.running) {
        this._planToCurrentGoal()
        this._emitEvent('notice', { message: '障碍已清除，继续巡检' })
      }
    }
    this._saveMap()
    this._refreshPlan()
    this._emitState()
  }

  /**
   * 按当前路线规划批量清除电力预算内的障碍（逐处判断电量）。
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
      if (this._state.battery < CLEAR_OBSTACLE_COST) {
        break
      }
      this._map.grid[y][x] = 0
      this._state.battery = Math.max(
        0.0,
        parseFloat((this._state.battery - CLEAR_OBSTACLE_COST).toFixed(2))
      )
      this._pending = this._pending.filter((c) => !(c[0] === x && c[1] === y))
      cleared += 1
    }
    this._patrol.blockedBy = null
    if (this._blocked) {
      this._blocked = null
      this._paused = false
      this._patrol.paused = false
    }
    this._emitEvent('notice', {
      message: cleared
        ? `已按规划清除 ${cleared} 处障碍，共耗电 ${(cleared * CLEAR_OBSTACLE_COST).toFixed(0)}%`
        : '电量不足，未能清除任何障碍；请先返航充电',
    })
    if (this._patrol.running) {
      this._planToCurrentGoal()
    }
    this._saveMap()
    this._refreshPlan()
    this._emitState()
  }

  /**
   * 一键清除待清障记录中离机器人最近的一处（V2.0）。
   */
  clearNearestPending() {
    this._pending = this._pending.filter(
      ([x, y]) =>
        x > 0 && y > 0 && x < this._map.width - 1 && y < this._map.height - 1 && this._map.grid[y][x] === 1
    )
    if (this._pending.length === 0) {
      this._emitEvent('notice', { message: '没有待清障记录' })
      this._emitState()
      return
    }
    const nearest = this._pending.reduce((best, cur) => {
      const d = this._manhattan([this._state.x, this._state.y], cur)
      const bd = this._manhattan([this._state.x, this._state.y], best)
      return d < bd ? cur : best
    }, this._pending[0])
    this.clearObstacleAt([...nearest])
  }

  /**
   * 巡检遇阻决策（V2.0）：clear 清除并继续 / skip 跳过并记录 / stop 停止。
   * @param {'clear'|'skip'|'stop'} action - 决策动作。
   */
  patrolDecision(action) {
    if (!this._blocked) {
      this._emitEvent('notice', { message: '当前没有待决策的巡检阻碍' })
      return
    }
    const cell = [...this._blocked.cell]
    if (action === 'clear' && this._map.grid[cell[1]][cell[0]] === 2) {
      this._emitEvent('notice', { message: '前方是固定屏障，机器人无法清除；请选择跳过或停止' })
      return
    }
    if (action === 'clear') {
      this.clearObstacleAt(cell)
    } else if (action === 'skip') {
      if (!this._pending.some((c) => c[0] === cell[0] && c[1] === cell[1])) {
        if (this._pending.length >= PENDING_LIMIT) {
          this._pending.shift()
        }
        this._pending.push(cell)
      }
      this._blocked = null
      this._paused = false
      this._patrol.paused = false
      this._patrol.blockedBy = null
      this._patrol.currentGoalIndex += 1
      this._emitEvent('notice', {
        message: `已跳过该巡检点，障碍 [${cell[0]}, ${cell[1]}] 已记入待清障记录`,
      })
      if (this._patrol.currentGoalIndex >= this._patrol.totalGoals) {
        this._finishPatrol()
      } else {
        this._planToCurrentGoal()
      }
      this._emitState()
    } else if (action === 'stop') {
      this.stopPatrol()
    } else {
      this._emitEvent('notice', { message: '未知的决策动作' })
    }
  }

  /**
   * 获取待清障记录。
   * @returns {number[][]} 坐标数组。
   */
  getPending() {
    return this._pending.map((c) => [...c])
  }

  /**
   * 空电搬回：用户确认后将机器人传送回地图起点并恢复满电。
   */
  carryBackHome() {
    this._patrol.running = false
    this._patrol.paused = false
    const start = this._map.start
    this._state.x = start[0]
    this._state.y = start[1]
    this._state.theta = 0
    this._state.battery = 100.0
    this._state.mode = 'manual'
    this._state.path = []
    this._plan = null
    this._paused = false
    this._blocked = null
    this._chargeUnreachableNotified = false
    this._internalTemp = TEMP_BASE
    this._visitedTrail.push([start[0], start[1]])
    this._updateSensors()
    this._recordSnapshot()
    this._emitState()
    this._emitEvent('notice', { message: '机器人已搬回初始点，电量已恢复 100%' })
  }

  /**
   * 取消当前路线规划（预览）。
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
    if (this._state.mode === 'empty') {
      this._emitEvent('notice', { message: '电量耗尽，无法开始巡检；请先搬回初始点' })
      return
    }
    const targetGoals = goals && goals.length > 0 ? goals : this._map.goals
    if (!targetGoals || targetGoals.length === 0) {
      this._emitEvent('notice', { message: '没有可用的巡检点' })
      return
    }
    this._snapshots = []
    this._patrol = {
      running: true,
      paused: false,
      goals: this._orderGoals(targetGoals),
      currentGoalIndex: 0,
      totalGoals: targetGoals.length,
      pathRemain: 0,
      blockedBy: null,
    }
    this._paused = false
    this._blocked = null
    this._resumePatrolAfterCharge = false
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
    this._patrol.paused = false
    this._patrol.blockedBy = null
    this._paused = false
    this._blocked = null
    this._state.mode = 'manual'
    this._state.path = []
    this._emitEvent('notice', { message: '自动巡检已停止' })
    this._emitState()
  }

  /**
   * 获取当前巡检状态（progress 为 0~1 比例，与后端一致）。
   * @returns {Object} { running, paused, current_goal, progress, completed, total, path_remain, blocked_by }。
   */
  getPatrolStatus() {
    const currentGoal =
      this._patrol.running && this._patrol.currentGoalIndex < this._patrol.totalGoals
        ? this._patrol.goals[this._patrol.currentGoalIndex]
        : null
    const progress =
      this._patrol.totalGoals > 0
        ? Math.min(1, this._patrol.currentGoalIndex / this._patrol.totalGoals)
        : 0
    return {
      running: this._patrol.running,
      paused: this._patrol.paused,
      current_goal: currentGoal,
      progress,
      completed: this._patrol.currentGoalIndex,
      total: this._patrol.totalGoals,
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
   * 获取回放快照数据（快照里只存尾迹长度，回放时按长度切片）。
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
