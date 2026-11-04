/**
 * 模块功能：一键路线规划（穿障 A* + 电力预算）
 * 作者：智能巡检机器人二维仿真系统 V2.3.1 前端开发组
 * 日期：2026-11-01
 * 版本：V2.3.1
 *
 * 与后端 app/services/planner.py 逐字段对应，保证本地仿真（SimulatedService）
 * 与后端模式（RemoteService）下"规划路线 / 待清障标记 / 电力预算"行为一致。
 * 与普通 astar.js 的区别：规划路线是理论最短路径——普通障碍格视为
 * "可通行但需要清除"，只有最外环边界墙与固定屏障不可穿越。
 *
 * V2.3.1：同步后端的八邻域口径（直行 1、斜行 √2、禁止斜穿墙角），
 * 并新增"拆哪一格能通"的建议，供不可达时给用户一键清障。
 */

/** 八邻域移动方向（dx, dy）。 */
const NEIGHBORS = [
  [0, -1],
  [0, 1],
  [-1, 0],
  [1, 0],
  [-1, -1],
  [1, -1],
  [-1, 1],
  [1, 1],
]

/** 斜向一步的几何长度。 */
const SQRT2 = Math.SQRT2

/**
 * octile 距离（八邻域启发）。
 *
 * @param {number[]} a - 坐标 [x, y]。
 * @param {number[]} b - 坐标 [x, y]。
 * @returns {number} 距离。
 */
function octile(a, b) {
  const dx = Math.abs(a[0] - b[0])
  const dy = Math.abs(a[1] - b[1])
  return dx + dy + (SQRT2 - 2) * Math.min(dx, dy)
}

/**
 * 计算起点到目标点的"理论最短路径"（可穿越普通障碍，边界墙/屏障不可穿越）。
 *
 * @param {number[][]} grid - 二维数组，0=可通行，1=障碍物，2=固定屏障。
 * @param {number[]} start - 起点 [x, y]。
 * @param {number[]} goal - 目标 [x, y]。
 * @returns {Object} { path, obstacles_on_path, cost }，不可规划时 path 为空数组。
 */
export function planRoute(grid, start, goal) {
  const height = grid.length
  const width = height ? grid[0].length : 0
  // 边界墙与固定屏障（2）不可穿越；普通障碍（1）视为"可通行但需清除"
  const passable = (x, y) =>
    x > 0 && x < width - 1 && y > 0 && y < height - 1 && grid[y][x] !== 2
  if (!passable(start[0], start[1]) || !passable(goal[0], goal[1])) {
    return { path: [], obstacles_on_path: [], cost: 0 }
  }

  const key = (x, y) => `${x},${y}`
  const startKey = key(start[0], start[1])
  const goalKey = key(goal[0], goal[1])
  const openList = [{ key: startKey, pos: start, f: octile(start, goal), h: octile(start, goal) }]
  const closedSet = new Set()
  const cameFrom = new Map()
  const gScore = new Map([[startKey, 0]])

  while (openList.length > 0) {
    openList.sort((a, b) => (a.f !== b.f ? a.f - b.f : a.h - b.h))
    const current = openList.shift()
    if (closedSet.has(current.key)) continue
    if (current.key === goalKey) {
      const path = [current.pos]
      let cursor = current.key
      while (cameFrom.has(cursor)) {
        const previous = cameFrom.get(cursor)
        path.unshift(previous)
        cursor = key(previous[0], previous[1])
      }
      // V2.4.0：石头(1) / 沙子(3) / 金刚石(4) 都算"待清障"
      const obstacles = path.filter(([x, y]) => [1, 3, 4].includes(grid[y][x]))
      return { path, obstacles_on_path: obstacles, cost: gScore.get(current.key) }
    }
    closedSet.add(current.key)

    for (const [dx, dy] of NEIGHBORS) {
      const nx = current.pos[0] + dx
      const ny = current.pos[1] + dy
      if (!passable(nx, ny)) continue
      const neighborKey = key(nx, ny)
      if (closedSet.has(neighborKey)) continue
      let stepCost = 1
      if (dx !== 0 && dy !== 0) {
        // 与 astar 同规则：不允许斜穿墙角。
        if (!passable(current.pos[0] + dx, current.pos[1]) || !passable(current.pos[0], current.pos[1] + dy)) {
          continue
        }
        stepCost = SQRT2
      }
      const tentativeG = gScore.get(current.key) + stepCost
      if (gScore.has(neighborKey) && tentativeG >= gScore.get(neighborKey) - 1e-12) continue
      cameFrom.set(neighborKey, current.pos)
      gScore.set(neighborKey, tentativeG)
      const h = octile([nx, ny], goal)
      openList.push({ key: neighborKey, pos: [nx, ny], f: tentativeG + h, h })
    }
  }
  return { path: [], obstacles_on_path: [], cost: 0 }
}

/** 保留两位小数，避免浮点误差在界面上露出（如 12.400000000002）。 */
function round2(value) {
  return Math.round(value * 100) / 100
}

/**
 * 规划路线并按电力预算决定可清除的障碍个数。
 *
 * 预算模型：总耗电 = 路径几何长度 × moveCost + 待清障数 × clearCost。
 * 电量充足时全部纳入；仅够移动时按剩余电量截断为前 k 个；连移动都不够时不可到达。
 *
 * @param {number[][]} grid - 二维栅格数组。
 * @param {number[]} start - 起点 [x, y]。
 * @param {number[]} goal - 目标 [x, y]。
 * @param {number} battery - 当前电量百分比。
 * @param {number} moveCost - 每移动一格耗电百分比（斜向按 √2 格折算）。
 * @param {number} clearCost - 每清除一处障碍耗电百分比。
 * @returns {Object} 路线规划对象，字段与后端 build_plan 一致。
 */
export function buildPlan(grid, start, goal, battery, moveCost, clearCost, materialCosts = {}) {
  const result = planRoute(grid, start, goal)
  const base = {
    goal: [...goal],
    path: [],
    obstacles: [],
    clearable: [],
    move_cost: 0,
    clear_cost: 0,
    total_cost: 0,
    battery,
    clear_unit_cost: clearCost,
    reachable: false,
    enough: false,
    message: '无法规划路线：目标不可达',
    suggestion: null,
  }
  if (result.path.length === 0) {
    return base
  }

  const { path, obstacles_on_path: obstacles, cost } = result
  // V2.4.0：每格按材质计价（石头 5%、沙子 2%、金刚石 20%）
  const perCell = obstacles.map(([x, y]) => {
    const value = grid[y][x]
    const unit = materialCosts[value]
    return typeof unit === 'number' ? unit : clearCost
  })
  const moveCostTotal = round2(cost * moveCost)
  const fullClearCost = round2(perCell.reduce((sum, value) => sum + value, 0))
  const totalCost = round2(moveCostTotal + fullClearCost)

  let clearable
  let clearableCost
  let enough
  let reachable
  if (battery + 1e-9 >= totalCost) {
    clearable = obstacles
    clearableCost = fullClearCost
    enough = true
    reachable = true
  } else if (battery + 1e-9 >= moveCostTotal) {
    // 按路径顺序累加，直到预算不够为止
    const budget = battery - moveCostTotal
    clearable = []
    clearableCost = 0
    for (let index = 0; index < obstacles.length; index += 1) {
      if (clearableCost + perCell[index] > budget + 1e-9) break
      clearable.push(obstacles[index])
      clearableCost += perCell[index]
    }
    clearableCost = round2(clearableCost)
    enough = false
    reachable = true
  } else {
    clearable = []
    clearableCost = 0
    enough = false
    reachable = false
  }

  return {
    goal: [...goal],
    path,
    obstacles,
    clearable,
    move_cost: moveCostTotal,
    clear_cost: clearableCost,
    total_cost: totalCost,
    battery,
    clear_unit_cost: clearCost,
    reachable,
    enough,
    message: '',
    suggestion: null,
  }
}

/**
 * 目标完全不可达时，找一处"拆掉它就能通"的障碍（V2.3.1）。
 *
 * 策略与后端 find_min_obstacle_to_remove 一致：逐个试拆普通障碍，
 * 选使路径代价最小的那一格；单格拆除无解时返回 null。
 *
 * @param {number[][]} grid - 二维栅格数组。
 * @param {number[]} start - 起点 [x, y]。
 * @param {number[]} goal - 目标 [x, y]。
 * @returns {number[]|null} 建议清除的坐标，或 null。
 */
export function suggestRemoval(grid, start, goal) {
  const height = grid.length
  const width = height ? grid[0].length : 0
  let best = null
  let bestCost = Infinity
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      if (grid[y][x] !== 1) continue
      grid[y][x] = 0
      const result = planRoute(grid, start, goal)
      grid[y][x] = 1
      if (result.path.length > 0 && result.cost < bestCost) {
        bestCost = result.cost
        best = [x, y]
      }
    }
  }
  return best
}
