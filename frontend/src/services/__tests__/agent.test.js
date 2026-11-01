/**
 * 模块功能：Agent 指令层单元测试（离线模式）
 * 作者：智能巡检机器人二维仿真系统 V2.3.0 前端开发组
 * 日期：2026-10-30
 * 版本：V2.3.0
 *
 * 覆盖：中文意图识别、坐标提取、参数校验、二次确认、与本地仿真服务的联动。
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { handleAgentCommand, parseRules, validateCall } from '../agent.js'
import { SimulatedService } from '../simulatedService.js'

const LIMITS = { minMap: 10, maxMap: 60, maxGoals: 12, clearCost: 5 }

/**
 * 找一张空闲、非关键点、非机器人所在格。
 *
 * @param {Object} map - 地图对象。
 * @param {Object} state - 机器人状态。
 * @returns {number[]} 坐标 [x, y]。
 */
function findFreeCell(map, state) {
  for (let y = 1; y < map.height - 1; y += 1) {
    for (let x = 1; x < map.width - 1; x += 1) {
      if (map.grid[y][x] !== 0) continue
      if (x === state.x && y === state.y) continue
      if (x === map.start[0] && y === map.start[1]) continue
      if (x === map.charge_point[0] && y === map.charge_point[1]) continue
      if (map.goals.some((goal) => goal[0] === x && goal[1] === y)) continue
      return [x, y]
    }
  }
  throw new Error('地图上没有可用空格')
}

describe('Agent 规则解析', () => {
  it.each([
    ['去 5,5 巡检', 'start_patrol'],
    ['开始巡检', 'start_patrol'],
    ['停止巡检', 'stop_patrol'],
    ['规划到 8,4 的路线', 'plan_route'],
    ['现在状态怎么样', 'status'],
    ['回充电点', 'go_charge'],
    ['把 3,4 的障碍清掉', 'clear_obstacle'],
    ['把 5,5 设成屏障', 'set_cell'],
    ['复位', 'reset'],
    ['向右移动一格', 'move'],
  ])('「%s」应识别为 %s', (text, tool) => {
    expect(parseRules(text).tool).toBe(tool)
  })

  it('应支持中文标点与括号里的坐标', () => {
    const parsed = parseRules('去 (6，3) 巡检')
    expect(parsed.tool).toBe('start_patrol')
    expect(parsed.args.goals).toEqual([[6, 3]])
  })

  it('听不懂的句子不应瞎猜动作', () => {
    expect(parseRules('今天天气不错').tool).toBeNull()
  })

  it('「前进」按当前朝向解释', () => {
    expect(parseRules('前进一步', [-1, 0]).args).toEqual({ dx: -1, dy: 0 })
  })
})

describe('Agent 参数校验', () => {
  it('拒绝白名单之外的工具', () => {
    expect(() => validateCall('exec_shell', {}, { map: { width: 5, height: 5, grid: [] }, state: {}, limits: LIMITS })).toThrow()
  })

  it('拒绝越界目标', () => {
    const map = { width: 5, height: 5, grid: Array.from({ length: 5 }, () => Array(5).fill(0)), start: [1, 1], charge_point: [1, 1], goals: [] }
    const state = { x: 1, y: 1, battery: 100, mode: 'manual' }
    expect(() => validateCall('plan_route', { goal: [99, 99] }, { map, state, limits: LIMITS })).toThrow(/地图之外/)
  })

  it('拒绝清除不是障碍的格子', () => {
    const map = { width: 5, height: 5, grid: Array.from({ length: 5 }, () => Array(5).fill(0)), start: [1, 1], charge_point: [1, 1], goals: [] }
    const state = { x: 1, y: 1, battery: 100, mode: 'manual' }
    expect(() => validateCall('clear_obstacle', { cell: [2, 2] }, { map, state, limits: LIMITS })).toThrow(/不是障碍物/)
  })
})

describe('Agent 与本地仿真服务联动', () => {
  let service

  beforeEach(() => {
    service = new SimulatedService()
    service._stopLoop()
    service.reset()
  })

  afterEach(() => {
    service._stopLoop()
  })

  it('状态查询应返回电量与模式', async () => {
    const result = await service.sendAgentCommand('现在状态怎么样')
    expect(result.understood).toBe(true)
    expect(result.executed).toBe(true)
    expect(result.message).toContain('电量')
    expect(result.message).toContain('模式')
    expect(result.source).toBe('rule')
  })

  it('规划指令只预览、不移动机器人', async () => {
    const map = service.getMap()
    const goal = map.goals[0] || [map.width - 2, map.height - 2]
    const before = { ...service.getState() }
    const result = await service.sendAgentCommand(`规划到 ${goal[0]},${goal[1]} 的路线`)
    expect(result.tool).toBe('plan_route')
    expect(result.executed).toBe(true)
    expect(service.getState().x).toBe(before.x)
    expect(service.getState().y).toBe(before.y)
  })

  it('破坏性操作需要确认，确认后才改变地图与电量', async () => {
    const map = service.getMap()
    const state = service.getState()
    const [x, y] = findFreeCell(map, state)
    service.setCell(x, y, 1)

    const first = await service.sendAgentCommand(`把 ${x},${y} 的障碍清掉`)
    expect(first.need_confirm).toBe(true)
    expect(first.executed).toBe(false)
    expect(map.grid[y][x]).toBe(1)
    expect(service.getState().battery).toBe(100)

    const second = await service.sendAgentCommand(`把 ${x},${y} 的障碍清掉`, true)
    expect(second.executed).toBe(true)
    expect(second.ok).toBe(true)
    expect(map.grid[y][x]).toBe(0)
    expect(service.getState().battery).toBe(95)
  })

  it('「回充电点」应让机器人进入 charging 模式', async () => {
    const result = await service.sendAgentCommand('回充电点')
    expect(result.executed).toBe(true)
    expect(service.getState().mode).toBe('charging')
  })

  it('越界指令应返回可读错误而不是抛异常', async () => {
    const result = await service.sendAgentCommand('去 999,999 巡检')
    expect(result.understood).toBe(true)
    expect(result.executed).toBe(false)
    expect(result.message).toContain('地图之外')
  })

  it('空指令应被拒绝', async () => {
    const result = await handleAgentCommand('   ', {
      service,
      map: service.getMap(),
      limits: LIMITS,
    })
    expect(result.understood).toBe(false)
    expect(result.message).toContain('不能为空')
  })
})
