/**
 * 模块功能：A* 算法单元测试
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 */

import { describe, it, expect } from 'vitest'
import { astar } from '../astar.js'

describe('astar', () => {
  it('应在无障碍地图中返回直线最短路径', () => {
    const grid = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2])
    expect(result.path).toEqual([
      [0, 0],
      [1, 0],
      [2, 0],
      [2, 1],
      [2, 2],
    ])
    expect(result.cost).toBe(4)
    expect(result.visited_count).toBeGreaterThan(0)
  })

  it('应能绕过障碍物到达目标', () => {
    const grid = [
      [0, 0, 0],
      [1, 1, 0],
      [0, 0, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2])
    expect(result.path.length).toBeGreaterThan(0)
    expect(result.path[result.path.length - 1]).toEqual([2, 2])
  })

  it('当目标不可达时应返回空路径', () => {
    const grid = [
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2])
    expect(result.path).toEqual([])
    expect(result.cost).toBe(0)
  })

  it('当起点或终点为障碍物时应返回空路径', () => {
    const grid = [
      [1, 0],
      [0, 0],
    ]
    expect(astar(grid, [0, 0], [1, 1]).path).toEqual([])
    expect(astar(grid, [1, 1], [0, 0]).path).toEqual([])
  })
})
