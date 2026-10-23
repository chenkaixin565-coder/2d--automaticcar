/**
 * 模块功能：机器人数据服务层抽象接口
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
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
   * @returns {Promise<Object>|Object} { running, current_goal, progress, path_remain }。
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
   * { type: 'state', data: { x, y, theta, battery, speed, mode, path, sensors: { front, left, right, temperature } } }
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
