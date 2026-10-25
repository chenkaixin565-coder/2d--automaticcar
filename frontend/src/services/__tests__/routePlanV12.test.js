/**
 * 模块功能：V1.2 新功能单元测试（一键规划 / 清障耗电 / 空电搬回 / 巡检受阻）
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { SimulatedService } from '../simulatedService.js'
import { planRoute, buildPlan } from '../routePlanner.js'

/** 8x6 受控地图：起点 [1,1]、目标 [6,4]、充电点 [1,4]，y=2 行有两处障碍。 */
function makeMap() {
  const width = 8
  const height = 6
  const grid = Array.from({ length: height }, () => Array(width).fill(0))
  for (let x = 0; x < width; x += 1) {
    grid[0][x] = 1
    grid[height - 1][x] = 1
  }
  for (let y = 0; y < height; y += 1) {
    grid[y][0] = 1
    grid[y][width - 1] = 1
  }
  grid[2][3] = 1
  grid[2][4] = 1
  return {
    width,
    height,
    grid,
    start: [1, 1],
    goals: [[6, 4]],
    charge_point: [1, 4],
  }
}

/** 单行走廊地图：起点 [1,1]、目标 [4,1]，(2,1) 是必经障碍。 */
function corridorGrid() {
  return [
    [1, 1, 1, 1, 1, 1],
    [1, 0, 1, 0, 0, 1],
    [1, 1, 1, 1, 1, 1],
  ]
}

function makeService() {
  const service = new SimulatedService()
  service._stopLoop()
  service.updateMap(makeMap())
  service.reset()
  return service
}

describe('routePlanner 穿障 A* 与电力预算', () => {
  it('规划路径可穿越普通障碍，路径上的障碍被记入 obstacles', () => {
    const grid = corridorGrid()
    const result = planRoute(grid, [1, 1], [4, 1])
    expect(result.path).toEqual([[1, 1], [2, 1], [3, 1], [4, 1]])
    expect(result.obstacles_on_path).toEqual([[2, 1]])
  })

  it('目标在边界墙上时不可规划', () => {
    const result = planRoute(corridorGrid(), [1, 1], [0, 1])
    expect(result.path).toEqual([])
  })

  it('电量充足时全部障碍纳入清障计划', () => {
    const plan = buildPlan(corridorGrid(), [1, 1], [4, 1], 100, 0.2, 5.0)
    expect(plan.reachable).toBe(true)
    expect(plan.enough).toBe(true)
    expect(plan.clearable).toEqual([[2, 1]])
    // 3 步移动 0.6 + 1 处清障 5.0
    expect(plan.move_cost).toBe(0.6)
    expect(plan.clear_cost).toBe(5)
    expect(plan.total_cost).toBe(5.6)
  })

  it('电量只够移动时按预算截断清障个数', () => {
    const plan = buildPlan(corridorGrid(), [1, 1], [4, 1], 5.5, 0.2, 5.0)
    expect(plan.reachable).toBe(true)
    expect(plan.enough).toBe(false)
    expect(plan.clearable).toEqual([])
  })

  it('连移动耗电都不够时不可到达', () => {
    const plan = buildPlan(corridorGrid(), [1, 1], [4, 1], 0.5, 0.2, 5.0)
    expect(plan.reachable).toBe(false)
    expect(plan.clearable).toEqual([])
  })

  it('多处障碍时截断为前 k 个', () => {
    const grid = [
      [1, 1, 1, 1, 1, 1, 1],
      [1, 0, 1, 1, 0, 0, 1],
      [1, 1, 1, 1, 1, 1, 1],
    ]
    // 4 步移动 0.8 + 2 处清障 10 = 10.8；电量 5.9 只够再清 1 处
    const plan = buildPlan(grid, [1, 1], [5, 1], 5.9, 0.2, 5.0)
    expect(plan.obstacles).toHaveLength(2)
    expect(plan.clearable).toHaveLength(1)
    expect(plan.enough).toBe(false)
  })
})

describe('SimulatedService 一键规划路线', () => {
  let service

  beforeEach(() => {
    localStorage.clear()
    service = makeService()
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('planRoute 应存储规划并推送提示，state 帧携带同一份规划', () => {
    const plan = service.planRoute([6, 4])
    expect(plan.path.length).toBeGreaterThan(1)
    expect(plan.reachable).toBe(true)
    expect(service._plan).toBe(plan)
    let frame = null
    service.onState((f) => { frame = f })
    expect(frame.data.plan).toBe(plan)
  })

  it('目标不可达时应作废规划并提示', () => {
    const plan = service.planRoute([0, 2])
    expect(plan.path).toEqual([])
    expect(service._plan).toBeNull()
  })

  it('cancelPlan 应作废规划', () => {
    service.planRoute([6, 4])
    service.cancelPlan()
    expect(service._plan).toBeNull()
  })

  it('地图变更后旧规划作废', () => {
    service.planRoute([6, 4])
    const map = service.getMap()
    map.grid[4][5] = 1
    service.updateMap(map)
    expect(service._plan).toBeNull()
  })
})

describe('SimulatedService 清障', () => {
  let service

  beforeEach(() => {
    localStorage.clear()
    service = makeService()
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('clearObstacleAt 应清除障碍并扣除 5% 电量', () => {
    service._map.grid[4][4] = 1
    const batteryBefore = service._state.battery
    service.clearObstacleAt([4, 4])
    expect(service._map.grid[4][4]).toBe(0)
    expect(service._state.battery).toBeCloseTo(batteryBefore - 5, 5)
  })

  it('clearObstacleAt 应拒绝边界墙', () => {
    service.clearObstacleAt([0, 0])
    expect(service._map.grid[0][0]).toBe(1)
  })

  it('clearObstacleAt 应拒绝非障碍格且不扣电', () => {
    const batteryBefore = service._state.battery
    service.clearObstacleAt([3, 3])
    expect(service._state.battery).toBe(batteryBefore)
  })

  it('executePlanClear 应批量清除预算内障碍并扣电', () => {
    // 换用单行走廊地图：路径必须穿过 (2,1) 与 (3,1) 两处障碍
    service.updateMap({
      width: 6,
      height: 3,
      grid: [
        [1, 1, 1, 1, 1, 1],
        [1, 0, 1, 1, 0, 1],
        [1, 1, 1, 1, 1, 1],
      ],
      start: [1, 1],
      goals: [[4, 1]],
      charge_point: [1, 1],
    })
    service.reset()
    const plan = service.planRoute([4, 1])
    expect(plan.obstacles).toHaveLength(2)
    const batteryBefore = service._state.battery
    service.executePlanClear()
    expect(service._map.grid[1][2]).toBe(0)
    expect(service._map.grid[1][3]).toBe(0)
    expect(service._state.battery).toBeCloseTo(batteryBefore - 10, 5)
    // 刷新后的规划已无路径障碍
    expect(service._plan.obstacles).toHaveLength(0)
  })

  it('无规划时 executePlanClear 仅提示', () => {
    service.executePlanClear()
    expect(service._plan).toBeNull()
  })
})

describe('SimulatedService 空电状态', () => {
  let service

  beforeEach(() => {
    localStorage.clear()
    service = makeService()
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('电量耗尽后 tick 应转入空电状态并停止移动', () => {
    service._state.battery = 0.05
    for (let i = 0; i < 5; i += 1) service._tick()
    expect(service._state.mode).toBe('empty')
    const frozen = { x: service._state.x, y: service._state.y }
    service.move(1, 0)
    expect(service._state.x).toBe(frozen.x)
    expect(service._state.y).toBe(frozen.y)
  })

  it('空电状态下不可清障', () => {
    service._map.grid[4][4] = 1
    service._state.battery = 0.05
    for (let i = 0; i < 5; i += 1) service._tick()
    expect(service._state.mode).toBe('empty')
    service.clearObstacleAt([4, 4])
    expect(service._map.grid[4][4]).toBe(1)
  })

  it('carryBackHome 应传送回起点、恢复满电并作废规划', () => {
    service.planRoute([6, 4])
    service.move(1, 0)
    service._state.battery = 0.05
    for (let i = 0; i < 5; i += 1) service._tick()
    expect(service._state.mode).toBe('empty')
    service.carryBackHome()
    const start = service.getMap().start
    expect(service._state.x).toBe(start[0])
    expect(service._state.y).toBe(start[1])
    expect(service._state.battery).toBe(100)
    expect(service._state.mode).toBe('manual')
    expect(service._plan).toBeNull()
  })

  it('空电后复位应恢复正常手动状态', () => {
    service._state.battery = 0.05
    for (let i = 0; i < 5; i += 1) service._tick()
    expect(service._state.mode).toBe('empty')
    service.reset()
    expect(service._state.mode).toBe('manual')
    expect(service._state.battery).toBe(100)
  })
})

describe('SimulatedService 巡检受阻（V1.2：不告警、不中断）', () => {
  let service

  beforeEach(() => {
    localStorage.clear()
    service = makeService()
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('路径被占且无法绕行时应标记 blocked_by 且不产生 obstacle 告警', () => {
    // 目标与起点同行，起巡后封死前方一列制造绕不动的障碍
    service._map.goals = [[6, 1]]
    service.startPatrol([[6, 1]])
    service._tick() // 从 [1,1] 移动到 [2,1]
    expect(service._state.x).toBe(2)
    for (let y = 1; y < 5; y += 1) service._map.grid[y][3] = 1
    service._tick()
    expect(service._patrol.running).toBe(true)
    expect(service._patrol.blockedBy).toEqual([3, 1])
    expect(service.getAnomalies().filter((a) => a.type === 'obstacle')).toHaveLength(0)
  })

  it('清除受阻障碍后标记解除且巡检继续推进', () => {
    service.startPatrol([[6, 1]])
    service._tick()
    for (let y = 1; y < 5; y += 1) service._map.grid[y][3] = 1
    service._tick()
    expect(service._patrol.blockedBy).toEqual([3, 1])
    service.clearObstacleAt([3, 1])
    expect(service._patrol.blockedBy).toBeNull()
    service._tick()
    expect(service._state.x).toBe(3)
  })

  it('getPatrolStatus 应返回 blocked_by 字段', () => {
    expect(service.getPatrolStatus()).toHaveProperty('blocked_by')
    expect(service.getPatrolStatus().blocked_by).toBeNull()
  })
})
