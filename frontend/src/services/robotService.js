/**
 * 模块功能：机器人数据服务层抽象接口
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 本模块定义前端与后端/仿真器交互的统一契约。所有界面组件只依赖 RobotService，
 * 具体实现可以是本地 SimulatedService，也可以是下一阶段的 RemoteService（REST + WebSocket）。
 * 切换实现时，界面代码无需改动。
 */

/**
 * 机器人数据服务抽象类。
 *
 * 子类必须实现以下所有方法，并保持返回值结构与后端 API / WebSocket 协议一致。
 */
export class RobotService {
  constructor() {
    if (new.target === RobotService) {
      throw new Error('RobotService 是抽象类，不能直接实例化')
    }
  }

  /**
   * 获取当前地图。
   * @returns {Promise<Object>|Object} 地图对象 { width, height, grid, start, goals, charge_point }。
   */
  getMap() {
    throw new Error('子类必须实现 getMap 方法')
  }

  /**
   * 更新地图。
   * @param {Object} map - 完整地图对象。
   * @returns {Promise<void>|void}
   */
  updateMap() {
    throw new Error('子类必须实现 updateMap 方法')
  }

  /**
   * 手动移动机器人。
   * @param {number} dx - x 方向增量，取值为 -1、0 或 1。
   * @param {number} dy - y 方向增量，取值为 -1、0 或 1。
   * @returns {Promise<void>|void}
   */
  move() {
    throw new Error('子类必须实现 move 方法')
  }

  /**
   * 将机器人复位到地图起点。
   * @returns {Promise<void>|void}
   */
  reset() {
    throw new Error('子类必须实现 reset 方法')
  }

  /**
   * 一键排障：机器人被障碍卡住（mode=blocked）时，清除正前方障碍格
   * 并恢复正常控制；无阻塞时仅推送系统提示。
   * @returns {Promise<void>|void}
   */
  resolveFault() {
    throw new Error('子类必须实现 resolveFault 方法')
  }

  /**
   * 一键规划路线（V1.2）：计算到目标点的穿障最短路径，并按当前电量决定
   * 可纳入的待清障障碍个数（移动耗电与清障耗电合并预算）。
   *
   * @param {number[]} goal - 目标点坐标 [x, y]。
   * @returns {Promise<Object>|Object} 路线规划对象
   *   { goal, path, obstacles, clearable, move_cost, clear_cost, total_cost,
   *     battery, clear_unit_cost, reachable, enough, message }。
   */
  planRoute() {
    throw new Error('子类必须实现 planRoute 方法')
  }

  /**
   * 清除指定障碍格（V1.2 手动清障 / 规划内清障）。
   * 边界墙、非障碍格与空电状态会被拒绝；每处扣除固定清障电量。
   *
   * @param {number[]} cell - 障碍坐标 [x, y]。
   * @returns {Promise<void>|void}
   */
  clearObstacleAt() {
    throw new Error('子类必须实现 clearObstacleAt 方法')
  }

  /**
   * 按当前路线规划批量清除电力预算内的障碍（V1.2）。
   * @returns {Promise<void>|void}
   */
  executePlanClear() {
    throw new Error('子类必须实现 executePlanClear 方法')
  }

  /**
   * 空电搬回（V1.2）：用户确认后将机器人传送回地图起点并恢复满电。
   * @returns {Promise<void>|void}
   */
  carryBackHome() {
    throw new Error('子类必须实现 carryBackHome 方法')
  }

  /**
   * 取消当前路线规划（V1.2）：界面停止展示闪烁虚线与清障标记。
   * @returns {Promise<void>|void}
   */
  cancelPlan() {
    throw new Error('子类必须实现 cancelPlan 方法')
  }

  /**
   * 切换内置地图预设（mapPresets.js 中的 factory / warehouse / dense）。
   * @param {string} _key - 预设标识。
   * @returns {Promise<void>|void}
   */
  loadPreset(_key) {
    throw new Error('子类必须实现 loadPreset 方法')
  }

  /**
   * 获取当前地图对应的预设标识，自定义地图返回 null。
   * @returns {Promise<string|null>|string|null} 预设标识。
   */
  getPresetKey() {
    throw new Error('子类必须实现 getPresetKey 方法')
  }

  /**
   * 从权威来源拉取地图并刷新缓存（后端模式下拉取服务端地图，
   * 本地模式直接返回当前地图）。
   * @returns {Promise<Object>} 地图对象。
   */
  fetchMap() {
    throw new Error('子类必须实现 fetchMap 方法')
  }

  /**
   * 计算从起点到终点的 A* 路径。
   * @param {number[]} start - 起点 [x, y]。
   * @param {number[]} goal - 终点 [x, y]。
   * @returns {Promise<Object>|Object} { path, visited_count, cost }。
   */
  computePath() {
    throw new Error('子类必须实现 computePath 方法')
  }

  /**
   * 开始自动巡检任务。
   * @param {number[][]} goals - 巡检点数组，缺省时使用地图预设巡检点。
   * @returns {Promise<void>|void}
   */
  startPatrol() {
    throw new Error('子类必须实现 startPatrol 方法')
  }

  /**
   * 停止自动巡检任务。
   * @returns {Promise<void>|void}
   */
  stopPatrol() {
    throw new Error('子类必须实现 stopPatrol 方法')
  }

  /**
   * 获取当前巡检状态。
   * @returns {Promise<Object>|Object} { running, current_goal, progress, path_remain, blocked_by }。
   *   blocked_by 为巡检受阻且无法绕行时前方待清障障碍格 [x, y]，无阻碍为 null（V1.2）。
   */
  getPatrolStatus() {
    throw new Error('子类必须实现 getPatrolStatus 方法')
  }

  /**
   * 获取最新传感器数据。
   * @returns {Promise<Object>|Object} 传感器数据 { front, left, right, temperature }。
   */
  getSensors() {
    throw new Error('子类必须实现 getSensors 方法')
  }

  /**
   * 获取历史异常事件列表。
   * @returns {Promise<Object[]>|Object[]} 异常事件数组。
   */
  getAnomalies() {
    throw new Error('子类必须实现 getAnomalies 方法')
  }

  /**
   * 注册状态推送回调。
   *
   * 回调函数接收的帧格式必须与后端 WebSocket state 帧一致：
   * { type: 'state', data: { x, y, theta, battery, speed, mode, path, sensors: { front, left, right, temperature }, patrol, plan } }
   *
   * @param {Function} callback - 状态回调函数。
   * @returns {Function} 取消订阅函数。
   */
  onState(_callback) {
    throw new Error('子类必须实现 onState 方法')
  }

  /**
   * 注册事件推送回调。
   *
   * 回调函数接收的帧格式必须与后端 WebSocket 事件帧一致：
   * anomaly: { type: 'anomaly', data: { time, type, message, position } }
   * notice:  { type: 'notice',  data: { message } }
   *
   * @param {Function} callback - 事件回调函数。
   * @returns {Function} 取消订阅函数。
   */
  onEvent(_callback) {
    throw new Error('子类必须实现 onEvent 方法')
  }
}
