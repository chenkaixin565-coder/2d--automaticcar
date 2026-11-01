/**
 * 模块功能：V2.3.1 交互修复单元测试
 * 作者：智能巡检机器人二维仿真系统 V2.3.1 前端开发组
 * 日期：2026-11-01
 * 版本：V2.3.1
 *
 * 覆盖用户反馈的 5 个问题在离线模式下的行为：
 *   1. 不可达时保留规划结果（供界面显示"不可达 + 建议"）；
 *   2. 巡检点不可达时暂停并抛出 blocked 事件（带 reason=unreachable）；
 *   3. "按此路线巡检"只去该点，且开始巡检会作废预览；
 *   4. 一键排障在"有路线预览"时也能清障；
 *   5. 形象上传会广播 avatar 事件（在线模式下由后端同步到多端）。
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { parseRules, validateCall } from '../agent.js'
import { SimulatedService } from '../simulatedService.js'

/** 构造一张 12×8 空地图（两个巡检点）。 */
function blankMap() {
  return {
    width: 12,
    height: 8,
    grid: Array.from({ length: 8 }, () => Array(12).fill(0)),
    start: [1, 1],
    goals: [[9, 6], [5, 3]],
    charge_point: [1, 6],
  }
}

describe('V2.3.1 交互修复', () => {
  let service
  let events

  beforeEach(() => {
    service = new SimulatedService()
    service._stopLoop()
    service.updateMap(blankMap())
    service.reset()
    events = []
    service.onEvent((frame) => events.push(frame))
  })

  afterEach(() => {
    service._stopLoop()
  })

  it('「去 2 号巡检点」应只去第二个点，而不是全图巡检', async () => {
    const parsed = parseRules('去 2 号巡检点')
    expect(parsed.tool).toBe('start_patrol')
    expect(parsed.args.goal_index).toBe(2)

    const map = service.getMap()
    const result = await service.sendAgentCommand('去 2 号巡检点')
    expect(result.executed).toBe(true)
    expect(service._patrol.goals).toEqual([map.goals[1]])
    expect(service._patrol.totalGoals).toBe(1)
    expect(result.message).toContain('单点任务')
  })

  it('序号越界时应给出可读提示且不执行', async () => {
    const map = service.getMap()
    expect(() =>
      validateCall('start_patrol', { goal_index: 9 }, { map, state: service.getState(), limits: { minMap: 10, maxMap: 60, maxGoals: 12, clearCost: 5 } })
    ).toThrow(/没有第 9 号巡检点/)
  })

  it('开始巡检应静默作废预览（不再提示"路线规划已取消"）', () => {
    service.planRoute([9, 6])
    expect(service._plan).not.toBeNull()
    service.startPatrol([[9, 6]])
    expect(service._plan).toBeNull()
    expect(events.some((f) => f.type === 'notice' && /路线规划已取消/.test(f.data.message))).toBe(false)
  })

  it('目标被固定屏障围死时应保留规划并标记不可达', () => {
    const map = service.getMap()
    const [x, y] = map.goals[0]
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      map.grid[y + dy][x + dx] = 2
    }
    const plan = service.planRoute(map.goals[0])
    expect(plan.path).toEqual([])
    expect(service._plan).toEqual(plan)
    expect(plan.suggestion).toBeNull()
  })

  it('巡检点不可达时应暂停并抛出带建议的 blocked 事件', () => {
    const map = service.getMap()
    const [gx, gy] = map.goals[0]
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      map.grid[gy + dy][gx + dx] = 1
    }
    service.startPatrol([[gx, gy]])
    const blocked = events.find((f) => f.type === 'blocked')
    expect(blocked).toBeTruthy()
    expect(blocked.data.reason).toBe('unreachable')
    expect(blocked.data.goal).toEqual([gx, gy])
    expect(service._paused).toBe(true)
  })

  it('有路线预览时一键排障应清掉规划中的障碍', () => {
    const map = service.getMap()
    map.grid[3][3] = 1
    const plan = service.planRoute([5, 3])
    expect(plan.clearable).toEqual([[3, 3]])
    const before = service.getState().battery
    service.resolveFault()
    expect(map.grid[3][3]).toBe(0)
    expect(service.getState().battery).toBeCloseTo(before - 5, 5)
  })

  it('上传形象会广播 avatar 事件并可读回', async () => {
    const dataUrl = 'data:image/png;base64,iVBORw0KGgo='
    await service.uploadAvatar(dataUrl)
    expect(await service.getAvatar()).toBe(dataUrl)
    const avatarEvent = events.find((f) => f.type === 'avatar')
    expect(avatarEvent).toBeTruthy()
    expect(avatarEvent.data.data_url).toBe(dataUrl)
    await service.removeAvatar()
    expect(await service.getAvatar()).toBeNull()
  })
})
