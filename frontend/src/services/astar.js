/**
 * 模块功能：A* 路径规划算法（前端临时实现）
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 【临时实现】最终版本迁移至后端 Python 模块，函数签名与返回结构保持一致。
 * 当前版本在浏览器中完成栅格地图的寻路、避障与调试输出，便于前端独立运行。
 */

/**
 * 在二维栅格地图上使用 A* 算法搜索从起点到终点的最短路径。
 *
 * @param {number[][]} grid - 二维数组，0 表示可通行，1 表示障碍物。
 * @param {number[]} start - 起点坐标 [x, y]。
 * @param {number[]} goal - 终点坐标 [x, y]。
 * @returns {Object} 搜索结果：{ path: number[][], visited_count: number, cost: number }
 *   - path: 由坐标点 [x, y] 组成的路径数组，包含起点和终点；寻路失败时为空数组。
 *   - visited_count: 算法扩展过的节点数量，用于调试与性能评估。
 *   - cost: 路径总代价；无路径时为 0。
 */
export function astar(grid, start, goal) {
  const height = grid.length
  if (height === 0) {
    return { path: [], visited_count: 0, cost: 0 }
  }
  const width = grid[0].length

  // 起点或终点越界或为障碍物时直接返回失败
  if (
    !inBounds(start, width, height) ||
    !inBounds(goal, width, height) ||
    grid[start[1]][start[0]] !== 0 ||
    grid[goal[1]][goal[0]] !== 0
  ) {
    return { path: [], visited_count: 0, cost: 0 }
  }

  // 开放列表与关闭集合
  const openList = []
  const closedSet = new Set()
  const cameFrom = new Map()
  const gScore = new Map()
  const fScore = new Map()

  const startKey = key(start)
  const goalKey = key(goal)

  gScore.set(startKey, 0)
  fScore.set(startKey, heuristic(start, goal))
  openList.push({ key: startKey, pos: start, f: fScore.get(startKey) })

  let visitedCount = 0

  // 四邻域：右、下、左、上
  const directions = [
    [1, 0],
    [0, 1],
    [-1, 0],
    [0, -1],
  ]

  while (openList.length > 0) {
    // 取出 f 值最小的节点
    openList.sort((a, b) => a.f - b.f)
    const current = openList.shift()
    visitedCount += 1

    if (current.key === goalKey) {
      const path = reconstructPath(cameFrom, current.pos, start)
      return {
        path,
        visited_count: visitedCount,
        cost: gScore.get(current.key),
      }
    }

    closedSet.add(current.key)

    for (const [dx, dy] of directions) {
      const neighbor = [current.pos[0] + dx, current.pos[1] + dy]
      const neighborKey = key(neighbor)

      if (!inBounds(neighbor, width, height)) {
        continue
      }
      if (grid[neighbor[1]][neighbor[0]] !== 0) {
        continue
      }
      if (closedSet.has(neighborKey)) {
        continue
      }

      const tentativeG = gScore.get(current.key) + 1

      if (!gScore.has(neighborKey) || tentativeG < gScore.get(neighborKey)) {
        cameFrom.set(neighborKey, current.pos)
        gScore.set(neighborKey, tentativeG)
        const f = tentativeG + heuristic(neighbor, goal)
        fScore.set(neighborKey, f)

        const existing = openList.find((item) => item.key === neighborKey)
        if (existing) {
          existing.f = f
        } else {
          openList.push({ key: neighborKey, pos: neighbor, f })
        }
      }
    }
  }

  // 开放列表耗尽，未找到路径
  return { path: [], visited_count: visitedCount, cost: 0 }
}

/**
 * 检查坐标是否在地图范围内。
 *
 * @param {number[]} pos - 坐标 [x, y]。
 * @param {number} width - 地图宽度（列数）。
 * @param {number} height - 地图高度（行数）。
 * @returns {boolean} 是否在边界内。
 */
function inBounds(pos, width, height) {
  return pos[0] >= 0 && pos[0] < width && pos[1] >= 0 && pos[1] < height
}

/**
 * 曼哈顿距离启发函数，适合四方向移动的栅格地图。
 *
 * @param {number[]} a - 当前坐标 [x, y]。
 * @param {number[]} b - 目标坐标 [x, y]。
 * @returns {number} 启发值。
 */
function heuristic(a, b) {
  return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1])
}

/**
 * 将坐标转换为字符串键，便于 Map/Set 使用。
 *
 * @param {number[]} pos - 坐标 [x, y]。
 * @returns {string} 唯一键。
 */
function key(pos) {
  return `${pos[0]},${pos[1]}`
}

/**
 * 根据 cameFrom 映射重建路径。
 *
 * @param {Map<string, number[]>} cameFrom - 父节点映射。
 * @param {number[]} current - 终点坐标 [x, y]。
 * @param {number[]} start - 起点坐标 [x, y]。
 * @returns {number[][]} 从起点到终点的路径数组。
 */
function reconstructPath(cameFrom, current, _start) {
  const path = [current]
  let currentKey = key(current)
  while (cameFrom.has(currentKey)) {
    const previous = cameFrom.get(currentKey)
    path.unshift(previous)
    currentKey = key(previous)
  }
  return path
}
