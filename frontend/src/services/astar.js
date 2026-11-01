/**
 * 模块功能：A* 路径规划算法（前端实现）
 * 作者：智能巡检机器人二维仿真系统 V2.3.0 前端开发组
 * 日期：2026-10-30
 * 版本：V2.3.0
 *
 * 与后端 `backend/app/algorithms/astar.py` 保持同一套几何口径：
 *   - 八邻域（可关闭）：octile 启发，直行代价 1、斜行代价 √2，禁止斜穿墙角；
 *   - 四邻域：曼哈顿启发，一步代价 1；
 *   - 返回 { path, visited_count, cost, reachable, error }，字段与 Python 版逐字段一致，
 *     方便前端离线模式与后端在线模式互验。
 */

/** 四邻域方向。 */
const NEIGHBORS_4 = [
  [0, -1],
  [0, 1],
  [-1, 0],
  [1, 0],
]

/** 八邻域方向（四方向 + 四个对角）。 */
const NEIGHBORS_8 = [
  ...NEIGHBORS_4,
  [-1, -1],
  [1, -1],
  [-1, 1],
  [1, 1],
]

/** 斜向一步的几何长度。 */
const SQRT2 = Math.SQRT2

/**
 * 曼哈顿距离（四邻域启发）。
 *
 * @param {number[]} a - 坐标 [x, y]。
 * @param {number[]} b - 坐标 [x, y]。
 * @returns {number} 距离。
 */
function manhattan(a, b) {
  return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1])
}

/**
 * octile 距离（八邻域启发）：max + (√2 - 1) · min。
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
 * 极简二叉最小堆（按 f 升序，f 相同时按 h 升序）。
 */
class MinHeap {
  constructor() {
    this.items = []
  }

  get size() {
    return this.items.length
  }

  /**
   * 入堆。
   * @param {{f: number, h: number, seq: number, x: number, y: number}} node - 节点。
   */
  push(node) {
    this.items.push(node)
    let index = this.items.length - 1
    while (index > 0) {
      const parent = (index - 1) >> 1
      if (!this._less(this.items[index], this.items[parent])) break
      ;[this.items[index], this.items[parent]] = [this.items[parent], this.items[index]]
      index = parent
    }
  }

  /**
   * 弹出最小节点。
   * @returns {Object|undefined} 最小节点。
   */
  pop() {
    if (this.items.length === 0) return undefined
    const top = this.items[0]
    const last = this.items.pop()
    if (this.items.length > 0) {
      this.items[0] = last
      let index = 0
      for (;;) {
        const left = index * 2 + 1
        const right = left + 1
        let smallest = index
        if (left < this.items.length && this._less(this.items[left], this.items[smallest])) smallest = left
        if (right < this.items.length && this._less(this.items[right], this.items[smallest])) smallest = right
        if (smallest === index) break
        ;[this.items[index], this.items[smallest]] = [this.items[smallest], this.items[index]]
        index = smallest
      }
    }
    return top
  }

  /**
   * 比较两个节点：f 小者优先，f 相同时 h 小者优先（路径更直）。
   * @param {Object} a - 节点。
   * @param {Object} b - 节点。
   * @returns {boolean} a 是否应排在 b 前面。
   */
  _less(a, b) {
    if (a.f !== b.f) return a.f < b.f
    if (a.h !== b.h) return a.h < b.h
    return a.seq < b.seq
  }
}

/**
 * 在二维栅格地图上使用 A* 算法搜索从起点到终点的最短路径。
 *
 * @param {number[][]} grid - 二维数组，0 表示可通行，非 0 表示障碍。
 * @param {number[]} start - 起点坐标 [x, y]。
 * @param {number[]} goal - 终点坐标 [x, y]。
 * @param {boolean} [diagonal=true] - 是否启用八邻域（false 为四邻域直角路径）。
 * @returns {Object} { path, visited_count, cost, reachable, error }
 */
export function astar(grid, start, goal, diagonal = true) {
  const height = grid.length
  if (height === 0 || !grid[0] || grid[0].length === 0) {
    return { path: [], visited_count: 0, cost: 0, reachable: false, error: 'empty_map' }
  }
  const width = grid[0].length

  const inBounds = (pos) => pos[0] >= 0 && pos[0] < width && pos[1] >= 0 && pos[1] < height
  const isFree = (x, y) => x >= 0 && x < width && y >= 0 && y < height && grid[y][x] === 0

  if (!inBounds(start) || !inBounds(goal)) {
    return { path: [], visited_count: 0, cost: 0, reachable: false, error: 'out_of_bounds' }
  }
  if (!isFree(start[0], start[1])) {
    return { path: [], visited_count: 0, cost: 0, reachable: false, error: 'start_blocked' }
  }
  if (!isFree(goal[0], goal[1])) {
    return { path: [], visited_count: 0, cost: 0, reachable: false, error: 'goal_blocked' }
  }

  const neighbors = diagonal ? NEIGHBORS_8 : NEIGHBORS_4
  const heuristic = diagonal ? octile : manhattan
  const key = (x, y) => `${x},${y}`

  const open = new MinHeap()
  const gScore = new Map([[key(start[0], start[1]), 0]])
  const cameFrom = new Map()
  const closed = new Set()
  let seq = 0
  let visitedCount = 0

  const startH = heuristic(start, goal)
  open.push({ f: startH, h: startH, seq: seq++, x: start[0], y: start[1] })

  while (open.size > 0) {
    const current = open.pop()
    const currentKey = key(current.x, current.y)
    if (closed.has(currentKey)) continue
    closed.add(currentKey)
    visitedCount += 1

    if (current.x === goal[0] && current.y === goal[1]) {
      const path = [[current.x, current.y]]
      let cursor = currentKey
      while (cameFrom.has(cursor)) {
        const previous = cameFrom.get(cursor)
        path.push([previous[0], previous[1]])
        cursor = key(previous[0], previous[1])
      }
      path.reverse()
      return {
        path,
        visited_count: visitedCount,
        cost: gScore.get(currentKey),
        reachable: true,
        error: null,
      }
    }

    for (const [dx, dy] of neighbors) {
      const nx = current.x + dx
      const ny = current.y + dy
      if (!isFree(nx, ny) || closed.has(key(nx, ny))) continue

      let stepCost = 1
      if (dx !== 0 && dy !== 0) {
        // 禁止斜穿墙角：两侧正交格必须都可通行。
        if (!isFree(current.x + dx, current.y) || !isFree(current.x, current.y + dy)) continue
        stepCost = SQRT2
      }

      const tentative = gScore.get(currentKey) + stepCost
      const existing = gScore.get(key(nx, ny))
      if (existing !== undefined && tentative >= existing - 1e-12) continue

      cameFrom.set(key(nx, ny), [current.x, current.y])
      gScore.set(key(nx, ny), tentative)
      const h = heuristic([nx, ny], goal)
      open.push({ f: tentative + h, h, seq: seq++, x: nx, y: ny })
    }
  }

  return { path: [], visited_count: visitedCount, cost: 0, reachable: false, error: 'unreachable' }
}

/**
 * 两点之间的超覆盖线段（Bresenham）：线段擦过的格全部返回，
 * 用于视线检测时不会把"擦着墙角穿过去"误判为通视。
 *
 * @param {number} x0 - 起点 x。
 * @param {number} y0 - 起点 y。
 * @param {number} x1 - 终点 x。
 * @param {number} y1 - 终点 y。
 * @returns {number[][]} 穿过的格坐标。
 */
function supercoverLine(x0, y0, x1, y1) {
  const cells = [[x0, y0]]
  const dx = x1 - x0
  const dy = y1 - y0
  const nx = Math.abs(dx)
  const ny = Math.abs(dy)
  const signX = Math.sign(dx)
  const signY = Math.sign(dy)

  if (nx === 0) {
    for (let step = 1; step <= ny; step += 1) cells.push([x0, y0 + signY * step])
    return cells
  }
  if (ny === 0) {
    for (let step = 1; step <= nx; step += 1) cells.push([x0 + signX * step, y0])
    return cells
  }

  let x = x0
  let y = y0
  let ix = 0
  let iy = 0
  while (ix < nx || iy < ny) {
    const tx = (1 + 2 * ix) / (2 * nx)
    const ty = (1 + 2 * iy) / (2 * ny)
    if (tx < ty) {
      x += signX
      ix += 1
      cells.push([x, y])
    } else if (tx > ty) {
      y += signY
      iy += 1
      cells.push([x, y])
    } else {
      cells.push([x + signX, y])
      cells.push([x, y + signY])
      x += signX
      y += signY
      ix += 1
      iy += 1
      cells.push([x, y])
    }
  }
  return cells
}

/**
 * 判断两格之间是否通视（线段穿过的格全部可通行）。
 *
 * @param {number[][]} grid - 栅格地图。
 * @param {number[]} start - 起点 [x, y]。
 * @param {number[]} goal - 终点 [x, y]。
 * @returns {boolean} 是否通视。
 */
export function lineOfSight(grid, start, goal) {
  const height = grid.length
  const width = height ? grid[0].length : 0
  for (const [x, y] of supercoverLine(start[0], start[1], goal[0], goal[1])) {
    if (x < 0 || x >= width || y < 0 || y >= height || grid[y][x] !== 0) return false
  }
  return true
}

/**
 * 把逐格路径抽稀成关键点（只保留必须转弯的点）。
 *
 * @param {number[][]} grid - 栅格地图。
 * @param {number[][]} path - 逐格路径。
 * @returns {number[][]} 关键点路径。
 */
export function smoothPath(grid, path) {
  if (path.length <= 2) return path.map((p) => [p[0], p[1]])
  const out = [[path[0][0], path[0][1]]]
  let anchor = 0
  while (anchor < path.length - 1) {
    let farthest = anchor + 1
    const limit = Math.min(path.length - 1, anchor + 32)
    let probe = anchor + 2
    while (probe <= limit && lineOfSight(grid, path[anchor], path[probe])) {
      farthest = probe
      probe += 1
    }
    out.push([path[farthest][0], path[farthest][1]])
    anchor = farthest
  }
  return out
}

/**
 * 把关键点路径回填成相邻格序列（与后端 expand_path 一致）。
 *
 * @param {number[][]} points - 关键点路径。
 * @returns {number[][]} 逐格路径。
 */
export function expandPath(points) {
  if (points.length <= 1) return points.map((p) => [p[0], p[1]])
  const expanded = [[points[0][0], points[0][1]]]
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1]
    const current = points[index]
    const segment = supercoverLine(previous[0], previous[1], current[0], current[1])
    for (const cell of segment.slice(1)) {
      const last = expanded[expanded.length - 1]
      if (!last || last[0] !== cell[0] || last[1] !== cell[1]) expanded.push([cell[0], cell[1]])
    }
  }
  return expanded
}

/**
 * 视线法平滑 + 逐格回填：拐点更少、但仍可被机器人逐格执行。
 *
 * @param {number[][]} grid - 栅格地图。
 * @param {number[][]} path - A* 输出的逐格路径。
 * @returns {number[][]} 处理后的路径；异常或不划算时原样返回。
 */
export function smoothAndExpand(grid, path) {
  if (path.length <= 2) return path.map((p) => [p[0], p[1]])
  const smoothed = smoothPath(grid, path)
  if (smoothed.length >= path.length) return path.map((p) => [p[0], p[1]])
  const expanded = expandPath(smoothed)
  return expanded.length <= path.length ? expanded : path.map((p) => [p[0], p[1]])
}
