/**
 * 模块功能：内置地图预设库
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-24
 * 版本：V1.0
 *
 * 提供三张开箱即用的内置地图：默认厂房、仓储走廊、障碍密集区。
 * 网格约定 grid[y][x]：0=可通行，1=障碍；四周留一圈边界墙。
 * 所有地图均保证起点、巡检点、充电点位于可通行格。
 */

import DEFAULT_MAP from '../../../shared/default-map.json'

/** 生成全空网格（不含边界墙）。 */
function emptyGrid(width, height) {
  return Array.from({ length: height }, () => Array(width).fill(0))
}

/** 给网格加四周边界墙。 */
function addBorder(grid, width, height) {
  for (let x = 0; x < width; x += 1) {
    grid[0][x] = 1
    grid[height - 1][x] = 1
  }
  for (let y = 0; y < height; y += 1) {
    grid[y][0] = 1
    grid[y][width - 1] = 1
  }
}

/** 批量设置障碍格。 */
function setObstacles(grid, cells) {
  for (const [x, y] of cells) {
    grid[y][x] = 1
  }
}

/**
 * 默认厂房：30x20 空旷场地 + 若干段固定墙体，
 * 与 V1.0 初始版本默认地图一致，保证老用户打开即见熟悉画面。
 */
function factoryMap() {
  // V2.2.0：直接读 shared/default-map.json，后端启动用的是同一份文件。
  return {
    width: DEFAULT_MAP.width,
    height: DEFAULT_MAP.height,
    grid: DEFAULT_MAP.grid.map((row) => [...row]),
    start: [...DEFAULT_MAP.start],
    goals: DEFAULT_MAP.goals.map((goal) => [...goal]),
    charge_point: [...DEFAULT_MAP.charge_point],
  }
}

/**
 * 仓储走廊：24x16，三组竖向货架各留一个缺口，
 * 考验 A* 在狭长通道中的绕行能力。
 */
function warehouseMap() {
  const width = 24
  const height = 16
  const grid = emptyGrid(width, height)
  addBorder(grid, width, height)
  // 竖向货架：x=6/12/18，分别在 y=4/9/6 留缺口
  const racks = [
    { x: 6, gap: 4 },
    { x: 12, gap: 9 },
    { x: 18, gap: 6 },
  ]
  for (const rack of racks) {
    for (let y = 1; y < height - 1; y += 1) {
      if (y !== rack.gap) {
        grid[y][rack.x] = 1
      }
    }
  }
  // 底部横向短墙，形成需要二次绕行的陷阱
  setObstacles(grid, [
    [14, 13], [15, 13], [16, 13],
  ])
  return {
    width,
    height,
    grid,
    start: [1, 1],
    goals: [
      [22, 2],
      [22, 13],
      [11, 8],
    ],
    charge_point: [1, 14],
  }
}

/**
 * 障碍密集区：28x18，多点集群 + 封闭陷阱格，
 * 用于演示无法到达告警与一键排障。
 */
function denseMap() {
  const width = 28
  const height = 18
  const grid = emptyGrid(width, height)
  addBorder(grid, width, height)
  setObstacles(grid, [
    // 左上 3x3 封闭群（中心 [5,4] 成为陷阱格）
    [4, 3], [5, 3], [6, 3],
    [4, 4], [6, 4],
    [4, 5], [5, 5], [6, 5],
    // 中部散点
    [10, 6], [11, 6], [12, 7], [13, 7], [10, 8],
    // 右上横墙（留右侧绕行通道）
    [18, 3], [19, 3], [20, 3], [21, 3], [19, 4], [20, 4],
    // 左下 L 形群
    [5, 11], [6, 11], [7, 11], [6, 12], [7, 12], [8, 13],
    // 右下封闭群（中心 [21,13] 成为陷阱格）
    [20, 12], [21, 12], [22, 12],
    [20, 13], [22, 13],
    [20, 14], [21, 14], [22, 14],
    // 中央孤立障碍
    [14, 10], [15, 10],
  ])
  return {
    width,
    height,
    grid,
    start: [1, 1],
    goals: [
      [26, 2],
      [13, 15],
      [24, 8],
    ],
    charge_point: [26, 16],
  }
}

/** 内置地图列表（顺序即界面展示顺序）。 */
export const MAP_PRESETS = [
  {
    key: 'factory',
    name: '默认厂房',
    description: '30x20 空旷场地，适合基础演示',
    ...factoryMap(),
  },
  {
    key: 'warehouse',
    name: '仓储走廊',
    description: '24x16 货架通道，考验绕行',
    ...warehouseMap(),
  },
  {
    key: 'dense',
    name: '障碍密集区',
    description: '28x18 集群陷阱，演示排障',
    ...denseMap(),
  },
]

/**
 * 按 key 获取地图预设的深拷贝（避免调用方改写预设本体）。
 *
 * @param {string} key - 预设标识。
 * @returns {Object|null} 地图对象或 null。
 */
export function getPreset(key) {
  const preset = MAP_PRESETS.find((item) => item.key === key)
  if (!preset) return null
  // 只保留契约字段，并深拷贝避免调用方改写预设本体
  return JSON.parse(
    JSON.stringify({
      width: preset.width,
      height: preset.height,
      grid: preset.grid,
      start: preset.start,
      goals: preset.goals,
      charge_point: preset.charge_point,
    })
  )
}
