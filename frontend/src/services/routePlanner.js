/**
 * 模块功能：一键路线规划（穿障 A* + 电力预算）
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 与后端 app/services/planner.py 逐字段对应，保证本地仿真（SimulatedService）
 * 与后端模式（RemoteService）下“规划路线 / 待清障标记 / 电力预算”行为一致。
 * 与普通 astar.js 的区别：规划路线是理论最短路径——普通障碍格视为
 * “可通行但需要清除”，只有最外环边界墙不可穿越。
 */

/** 四邻域移动方向（dx, dy）。 */
const NEIGHBORS = [
  [0, -1],
  [0, 1],
  [-1, 0],
  [1, 0],
]

/**
 * 计算起点到目标点的“理论最短路径”（可穿越普通障碍，边界墙不可穿越）。
 *
 * @param {number[][]} grid - 二维数组，0=可通行，1=障碍物。
 * @param {number[]} start - 起点 [x, y]。
 * @param {number[]} goal - 目标 [x, y]。
 * @returns {Object} { path: number[][], obstacles_on_path: number[][] }，不可规划时 path 为空数组。
 */
export function planRoute(grid, start, goal) {
  const height = grid.length
  const width = height ? grid[0].length : 0
  // 边界墙不可穿越；内部格（含普通障碍）均可通行
  const passable = (x, y) => x > 0 && x < width - 1 && y > 0 && y < height - 1
  if (!passable(start[0], start[1]) || !passable(goal[0], goal[1])) {
    return { path: [], obstacles_on_path: [] }
  }

  const startKey = `${start[0]},${start[1]}`
  const goalKey = `${goal[0]},${goal[1]}`
  const openList = [{ key: startKey, pos: start, f: manhattan(start, goal) }]
  const closedSet = new Set()
  const cameFrom = new Map()
  const gScore = new Map([[startKey, 0]])

  while (openList.length > 0) {
    openList.sort((a, b) => a.f - b.f)
    const current = openList.shift()
    if (current.key === goalKey) {
      const path = [current.pos]
      let key = current.key
      while (cameFrom.has(key)) {
        const previous = cameFrom.get(key)
        path.unshift(previous)
        key = `${previous[0]},${previous[1]}`
      }
      const obstacles = path.filter(([x, y]) => grid[y][x] === 1)
      return { path, obstacles_on_path: obstacles }
    }
    closedSet.add(current.key)

    for (const [dx, dy] of NEIGHBORS) {
      const neighbor = [current.pos[0] + dx, current.pos[1] + dy]
      if (!passable(neighbor[0], neighbor[1])) continue
      const neighborKey = `${neighbor[0]},${neighbor[1]}`
      if (closedSet.has(neighborKey)) continue
      const tentativeG = gScore.get(current.key) + 1
      if (!gScore.has(neighborKey) || tentativeG < gScore.get(neighborKey)) {
        cameFrom.set(neighborKey, current.pos)
        gScore.set(neighborKey, tentativeG)
        const f = tentativeG + manhattan(neighbor, goal)
        const existing = openList.find((item) => item.key === neighborKey)
        if (existing) {
          existing.f = f
        } else {
          openList.push({ key: neighborKey, pos: neighbor, f })
        }
      }
    }
  }
  return { path: [], obstacles_on_path: [] }
}

/**
 * 曼哈顿距离启发函数。
 *
 * @param {number[]} a - 坐标 [x, y]。
 * @param {number[]} b - 坐标 [x, y]。
 * @returns {number} 曼哈顿距离。
 */
function manhattan(a, b) {
  return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1])
}

/** 保留两位小数，避免浮点误差在界面上露出（如 12.400000000002）。 */
function round2(value) {
  return Math.round(value * 100) / 100
}

/**
 * 规划路线并按电力预算决定可清除的障碍个数。
 *
 * 预算模型：总耗电 = 移动格数 × moveCost + 待清障数 × clearCost。
 * 电量充足时全部纳入；仅够移动时按剩余电量截断为前 k 个；连移动都不够时不可到达。
 *
 * @param {number[][]} grid - 二维栅格数组。
 * @param {number[]} start - 起点 [x, y]。
 * @param {number[]} goal - 目标 [x, y]。
 * @param {number} battery - 当前电量百分比。
 * @param {number} moveCost - 每移动一格耗电百分比。
 * @param {number} clearCost - 每清除一处障碍耗电百分比。
 * @returns {Object} 路线规划对象，字段与后端 build_plan 一致。
 */
export function buildPlan(grid, start, goal, battery, moveCost, clearCost) {
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
  }
  if (result.path.length === 0) {
    return base
  }

  const { path, obstacles_on_path: obstacles } = result
  const moveCostTotal = round2((path.length - 1) * moveCost)
  const totalCost = round2(moveCostTotal + obstacles.length * clearCost)

  let clearable
  let enough
  let reachable
  if (battery + 1e-9 >= totalCost) {
    clearable = obstacles
    enough = true
    reachable = true
  } else if (battery + 1e-9 >= moveCostTotal) {
    const affordable = clearCost > 0 ? Math.floor((battery - moveCostTotal + 1e-9) / clearCost) : obstacles.length
    clearable = obstacles.slice(0, affordable)
    enough = false
    reachable = true
  } else {
    clearable = []
    enough = false
    reachable = false
  }

  return {
    goal: [...goal],
    path,
    obstacles,
    clearable,
    move_cost: moveCostTotal,
    clear_cost: round2(clearable.length * clearCost),
    total_cost: totalCost,
    battery,
    clear_unit_cost: clearCost,
    reachable,
    enough,
    message: '',
  }
}
