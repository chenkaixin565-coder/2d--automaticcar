/**
 * V2.4.0 障碍材质测试。
 *
 * 覆盖：材质价格来自共享规则、规划按材质计价、清障按材质扣电、
 * 编辑格子接受 3/4、离线 Agent 能识别"沙子/金刚石"。
 */

import { beforeEach, describe, expect, it } from 'vitest'

import { buildPlan } from '../routePlanner.js'
import { CLEARABLE_MATERIALS, MATERIAL_COSTS, MATERIALS } from '../rules.js'
import { SimulatedService } from '../simulatedService.js'
import { handleAgentCommand } from '../agent.js'

describe('V2.4.0 材质配置', () => {
  it('三种材质的清障价格来自共享规则', () => {
    expect(MATERIALS.map((item) => item.value)).toEqual([1, 3, 4])
    expect(MATERIAL_COSTS[1]).toBe(5)
    expect(MATERIAL_COSTS[3]).toBe(2)
    expect(MATERIAL_COSTS[4]).toBe(20)
    expect(CLEARABLE_MATERIALS).toEqual([1, 3, 4])
  })
})

describe('V2.4.0 规划按材质计价', () => {
  it('沙子和金刚石按各自价格累加', () => {
    const grid = Array.from({ length: 7 }, () => Array(7).fill(0))
    grid[3][2] = 3
    grid[3][4] = 4
    const plan = buildPlan(grid, [1, 3], [5, 3], 100, 0.2, 5, MATERIAL_COSTS)
    expect(plan.path.length).toBeGreaterThan(1)
    expect(plan.move_cost).toBeCloseTo(0.8)
    expect(plan.clear_cost).toBeCloseTo(22)
    expect(plan.total_cost).toBeCloseTo(22.8)
    expect(plan.enough).toBe(true)
  })

  it('电量只够清沙子时截断为沙子', () => {
    const grid = Array.from({ length: 7 }, () => Array(7).fill(0))
    grid[3][2] = 3
    grid[3][4] = 4
    const plan = buildPlan(grid, [1, 3], [5, 3], 3.6, 0.2, 5, MATERIAL_COSTS)
    expect(plan.clearable).toEqual([[2, 3]])
    expect(plan.clear_cost).toBeCloseTo(2)
    expect(plan.enough).toBe(false)
  })
})

describe('V2.4.0 离线服务按材质扣电', () => {
  let service

  beforeEach(() => {
    service = new SimulatedService()
  })

  it('清沙子只扣 2%，清金刚石扣 20%', () => {
    const map = service.getMap()
    map.grid[3][3] = 3
    map.grid[5][3] = 4
    service.updateMap(map)
    service.setBatteryForTest?.(100)
    service.getState().battery = 100

    service.clearObstacleAt([3, 3])
    expect(service.getState().battery).toBeCloseTo(98)
    service.clearObstacleAt([3, 5])
    expect(service.getState().battery).toBeCloseTo(78)
  })

  it('setCell 接受 3/4，拒绝 5', () => {
    service.setCell(4, 4, 3)
    expect(service.getMap().grid[4][4]).toBe(3)
    service.setCell(4, 4, 4)
    expect(service.getMap().grid[4][4]).toBe(4)
    service.setCell(4, 4, 5)
    expect(service.getMap().grid[4][4]).toBe(4)
  })
})

describe('V2.4.0 离线 Agent 识别材质', () => {
  it('"把 3,3 设成沙子"解析为 set_cell 3', async () => {
    const service = new SimulatedService()
    const result = await handleAgentCommand('把 3,3 设成沙子', {
      service,
      map: service.getMap(),
      limits: { minMap: 10, maxMap: 60, clearCost: 5, maxBattery: 100, moveCost: 0.2 },
    })
    // 破坏性操作先返回确认请求
    expect(result.need_confirm).toBe(true)
    expect(result.tool).toBe('set_cell')
    expect(result.args.value).toBe(3)
  })
})
