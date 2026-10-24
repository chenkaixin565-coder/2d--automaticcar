/**
 * 模块功能：远程后端服务实现（RemoteService）
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-24
 * 版本：V1.0
 *
 * 本模块实现与 RobotService 完全相同的接口，但数据来源为 FastAPI 后端：
 * - 同步 getter（getMap / getPatrolStatus / getAnomalies / getVisitedTrail /
 *   getSnapshots / getSensors）返回内部缓存，由 WebSocket 推送帧与 REST 响应
 *   实时刷新，从而保证界面组件与本地仿真器零差异；
 * - 控制类方法（move / reset / startPatrol / stopPatrol / updateMap /
 *   clearAnomalies）优先通过 WebSocket 命令帧下发，未连接时回退到 REST；
 * - 推送的数据结构与服务端 WebSocket 协议逐字段一致。
 *
 * 接入方式：在 URL 后附加 ?backend=http(s)://后端地址 即可切换到本服务，
 * 不带该参数时由上层工厂默认回退到 SimulatedService（纯静态部署保持原状）。
 */

import { RobotService } from './robotService.js'

/** localStorage 中地图数据的键名，与 SimulatedService 共用。 */
const STORAGE_MAP_KEY = 'irm_map_v1'

/**
 * 远程后端服务类。
 *
 * 继承自 RobotService，所有状态来自 FastAPI 后端，不修改界面组件代码。
 */
export class RemoteService extends RobotService {
  /**
   * 构造远程服务实例。
   *
   * @param {string} baseUrl - 后端基地址，例如 http://localhost:8000。
   */
  constructor(baseUrl) {
    super()

    this._baseUrl = baseUrl.replace(/\/$/, '')
    this._wsUrl = this._baseUrl.replace(/^http/, 'ws') + '/api/v1/ws'

    this._stateListeners = new Set()
    this._eventListeners = new Set()
    this._connected = false
    this._ws = null
    /** 标识本服务为远程后端实现，供上层区分数据源。 */
    this.isRemote = true

    // 内部缓存（同步 getter 直接返回）
    this._map = this._defaultMap()
    this._state = {
      x: 0, y: 0, theta: 0, battery: 100, speed: 0, mode: 'manual',
      path: [], sensors: { front: null, left: null, right: null, temperature: 35 },
    }
    this._patrol = { running: false, current_goal: null, progress: 0, path_remain: 0 }
    this._anomalies = []
    this._snapshots = []
    this._visitedTrail = [[0, 0]]
    this._lastPos = { x: 0, y: 0 }

    // 暴露给调试与自动化脚本
    if (typeof window !== 'undefined') {
      window.robotService = this
    }

    this._connect()
    this._fetchInitial()
  }

  // ----------------------------------------------------------------------
  // 连接与初始化
  // ----------------------------------------------------------------------

  /**
   * 建立 WebSocket 连接并绑定消息处理。
   */
  _connect() {
    try {
      this._ws = new WebSocket(this._wsUrl)
      this._ws.onopen = () => {
        this._connected = true
        this._fetchInitial()
        this._emitEvent('notice', { message: '已连接到后端仿真服务' })
      }
      this._ws.onmessage = (event) => this._handleFrame(JSON.parse(event.data))
      this._ws.onclose = () => {
        this._connected = false
        this._emitEvent('notice', { message: '与后端连接已断开' })
        // 5 秒后尝试重连
        setTimeout(() => this._connect(), 5000)
      }
      this._ws.onerror = () => {
        this._connected = false
      }
    } catch (error) {
      console.error('WebSocket 连接失败：', error)
    }
  }

  /**
   * 处理后端推送的帧。
   *
   * @param {Object} frame - { type, data }。
   */
  _handleFrame(frame) {
    if (frame.type === 'state') {
      this._state = frame.data
      if (frame.data.patrol) this._patrol = frame.data.patrol
      this._trackTrail(frame.data)
      this._recordSnapshot(frame.data)
      this._emitState()
    } else if (frame.type === 'anomaly') {
      this._anomalies.unshift(frame.data)
      if (this._anomalies.length > 200) this._anomalies.pop()
      this._emitEvent('anomaly', frame.data)
    } else if (frame.type === 'notice') {
      const msg = frame.data && frame.data.message ? frame.data.message : ''
      if (msg.includes('复位') || msg.includes('复位到起点')) {
        this._visitedTrail = [[this._state.x, this._state.y]]
        this._snapshots = []
      }
      this._emitEvent('notice', frame.data)
    }
  }

  /**
   * 拉取传感器与异常数据以刷新缓存（地图以客户端为准，不覆盖）。
   */
  async _fetchInitial() {
    try {
      const sensors = await this._rest('GET', '/api/v1/sensors/latest')
      if (sensors) this._state.sensors = sensors
      const anomalies = await this._rest('GET', '/api/v1/events/anomalies')
      this._anomalies = Array.isArray(anomalies) ? anomalies : []
    } catch (error) {
      console.warn('初始数据拉取失败，将沿用本地缓存：', error)
    }
  }

  /**
   * 同步缓存中的轨迹：位置变化时追加一格。
   *
   * @param {Object} data - state 帧 data。
   */
  _trackTrail(data) {
    if (data.x !== this._lastPos.x || data.y !== this._lastPos.y) {
      this._visitedTrail.push([data.x, data.y])
      if (this._visitedTrail.length > 5000) this._visitedTrail.shift()
      this._lastPos = { x: data.x, y: data.y }
    }
  }

  /**
   * 记录回放快照（后端不存储，前端按帧重建）。
   *
   * @param {Object} data - state 帧 data。
   */
  _recordSnapshot(data) {
    this._snapshots.push({
      time: Date.now(),
      x: data.x, y: data.y, theta: data.theta,
      battery: data.battery, mode: data.mode,
      path: (data.path || []).map((p) => [...p]),
      visitedTrail: this._visitedTrail.map((p) => [...p]),
      sensors: { ...data.sensors },
    })
    if (this._snapshots.length > 5000) this._snapshots.shift()
  }

  // ----------------------------------------------------------------------
  // REST 封装
  // ----------------------------------------------------------------------

  /**
   * 通用 REST 请求封装。
   *
   * @param {string} method - HTTP 方法。
   * @param {string} path - 接口路径（不含基地址）。
   * @param {Object} [body] - 请求体（POST/PUT）。
   * @returns {Promise<Object>} 响应 JSON。
   */
  async _rest(method, path, body) {
    const options = { method, headers: { 'Content-Type': 'application/json' } }
    if (body !== undefined) options.body = JSON.stringify(body)
    const response = await fetch(this._baseUrl + path, options)
    if (!response.ok) {
      throw new Error(`REST ${method} ${path} 失败：HTTP ${response.status}`)
    }
    return response.json()
  }

  // ----------------------------------------------------------------------
  // 命令下发（优先 WS，回退 REST）
  // ----------------------------------------------------------------------

  /**
   * 通过 WebSocket 下发命令帧。
   *
   * @param {string} action - 指令类型。
   * @param {Object} [payload] - 指令参数。
   * @returns {boolean} 是否成功通过 WS 下发。
   */
  _sendCommand(action, payload) {
    if (this._connected && this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify({ type: 'command', action, payload: payload || {} }))
      return true
    }
    return false
  }

  // ----------------------------------------------------------------------
  // 公共接口实现（与 SimulatedService 签名保持一致）
  // ----------------------------------------------------------------------

  /**
   * 获取当前地图（同步，返回缓存）。
   * @returns {Object} 地图对象。
   */
  getMap() {
    return this._map
  }

  /**
   * 更新地图：始终通过 REST PUT 同步到服务端（服务端不在 WS 命令中处理
   * 地图更新），并写入本地缓存供离线回退。
   * @param {Object} map - 完整地图对象。
   */
  updateMap(map) {
    this._map = map
    try {
      localStorage.setItem(STORAGE_MAP_KEY, JSON.stringify(map))
    } catch (error) {
      console.warn('地图本地存储失败：', error)
    }
    this._rest('PUT', '/api/v1/map', map).catch((e) => console.error('地图同步失败：', e))
  }

  /**
   * 手动移动机器人。
   * @param {number} dx - x 方向增量。
   * @param {number} dy - y 方向增量。
   */
  move(dx, dy) {
    if (!this._sendCommand('move', { dx, dy })) {
      this._rest('POST', '/api/v1/robot/move', { dx, dy }).catch((e) => console.error(e))
    }
  }

  /**
   * 复位机器人到起点。
   */
  reset() {
    if (!this._sendCommand('reset', {})) {
      this._rest('POST', '/api/v1/robot/reset').catch((e) => console.error(e))
    }
    this._visitedTrail = [[this._state.x, this._state.y]]
    this._snapshots = []
  }

  /**
   * 计算 A* 路径（调用后端接口）。
   * @param {number[]} start - 起点。
   * @param {number[]} goal - 终点。
   * @returns {Promise<Object>} { path, visited_count, cost }。
   */
  async computePath(start, goal) {
    return this._rest('GET', `/api/v1/path?start=${start[0]},${start[1]}&goal=${goal[0]},${goal[1]}`)
  }

  /**
   * 开始自动巡检。
   * @param {number[][]} goals - 巡检点数组。
   */
  startPatrol(goals) {
    this._snapshots = []
    if (!this._sendCommand('patrol_start', { goals })) {
      this._rest('POST', '/api/v1/patrol/start', { goals }).catch((e) => console.error(e))
    }
  }

  /**
   * 停止自动巡检。
   */
  stopPatrol() {
    if (!this._sendCommand('patrol_stop', {})) {
      this._rest('POST', '/api/v1/patrol/stop').catch((e) => console.error(e))
    }
  }

  /**
   * 获取当前巡检状态（同步，返回缓存）。
   * @returns {Object} { running, current_goal, progress, path_remain }。
   */
  getPatrolStatus() {
    return { ...this._patrol }
  }

  /**
   * 获取最新传感器数据（同步，返回缓存）。
   * @returns {Object} 传感器数据。
   */
  getSensors() {
    return { ...this._state.sensors }
  }

  /**
   * 获取历史异常事件（同步，返回缓存）。
   * @returns {Object[]} 异常事件数组。
   */
  getAnomalies() {
    return [...this._anomalies]
  }

  /**
   * 获取回放快照（同步，返回前端按帧重建的缓存）。
   * @returns {Object[]} 快照数组。
   */
  getSnapshots() {
    return [...this._snapshots]
  }

  /**
   * 获取已访问轨迹（同步，返回前端重建的缓存）。
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
    this._rest('DELETE', '/api/v1/events/anomalies').catch((e) => console.error(e))
  }

  /**
   * 注册状态回调。
   * @param {Function} callback - 回调函数。
   * @returns {Function} 取消订阅函数。
   */
  onState(callback) {
    this._stateListeners.add(callback)
    this._emitState()
    return () => this._stateListeners.delete(callback)
  }

  /**
   * 注册事件回调。
   * @param {Function} callback - 回调函数。
   * @returns {Function} 取消订阅函数。
   */
  onEvent(callback) {
    this._eventListeners.add(callback)
    return () => this._eventListeners.delete(callback)
  }

  // ----------------------------------------------------------------------
  // 推送
  // ----------------------------------------------------------------------

  /**
   * 推送 state 帧到所有监听器。
   */
  _emitState() {
    const frame = {
      type: 'state',
      data: {
        x: this._state.x, y: this._state.y, theta: this._state.theta,
        battery: this._state.battery, speed: this._state.speed, mode: this._state.mode,
        path: (this._state.path || []).map((p) => [...p]),
        sensors: { ...this._state.sensors },
      },
    }
    for (const cb of this._stateListeners) {
      try { cb(frame) } catch (error) { console.error('状态回调执行失败：', error) }
    }
  }

  /**
   * 推送事件帧到所有监听器。
   * @param {string} eventType - 事件类型。
   * @param {Object} data - 载荷。
   */
  _emitEvent(eventType, data) {
    const frame = { type: eventType, data }
    for (const cb of this._eventListeners) {
      try { cb(frame) } catch (error) { console.error('事件回调执行失败：', error) }
    }
  }

  /**
   * 生成默认地图（后端不可达时的兜底）。
   * @returns {Object} 默认地图对象。
   */
  _defaultMap() {
    const width = 16
    const height = 12
    const grid = Array.from({ length: height }, () => Array(width).fill(0))
    return {
      width, height, grid,
      start: [0, 0],
      goals: [[width - 1, height - 1], [Math.floor(width / 2), Math.floor(height / 2)]],
      charge_point: [0, 0],
    }
  }
}
