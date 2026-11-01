/**
 * 模块功能：A* 算法与路径平滑单元测试（V2.3.0 八邻域）
 * 作者：智能巡检机器人二维仿真系统 V2.3.0 前端开发组
 * 日期：2026-10-30
 * 版本：V2.3.0
 */

import { describe, it, expect } from 'vitest'
import { astar, expandPath, lineOfSight, smoothAndExpand, smoothPath } from '../astar.js'

describe('astar', () => {
  it('八邻域下应沿对角线直达，代价为 2√2', () => {
    const grid = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2])
    expect(result.path).toEqual([
      [0, 0],
      [1, 1],
      [2, 2],
    ])
    expect(result.cost).toBeCloseTo(2 * Math.SQRT2, 9)
    expect(result.reachable).toBe(true)
    expect(result.error).toBeNull()
    expect(result.visited_count).toBeGreaterThan(0)
  })

  it('关闭八邻域时应退化为四邻域直角路径', () => {
    const grid = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2], false)
    expect(result.cost).toBe(4)
    expect(result.path.length).toBe(5)
  })

  it('不允许斜穿两个障碍之间的墙角', () => {
    const grid = [
      [0, 1, 0],
      [1, 0, 0],
      [0, 0, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2])
    expect(result.path).toEqual([])
    expect(result.error).toBe('unreachable')
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

  it('当目标不可达时应返回空路径与原因码', () => {
    const grid = [
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
    ]
    const result = astar(grid, [0, 0], [2, 2])
    expect(result.path).toEqual([])
    expect(result.cost).toBe(0)
    expect(result.reachable).toBe(false)
    expect(result.error).toBe('unreachable')
  })

  it('当起点或终点为障碍物时应返回空路径', () => {
    const grid = [
      [1, 0],
      [0, 0],
    ]
    expect(astar(grid, [0, 0], [1, 1]).path).toEqual([])
    expect(astar(grid, [0, 0], [1, 1]).error).toBe('start_blocked')
    expect(astar(grid, [1, 1], [0, 0]).error).toBe('goal_blocked')
  })
})

describe('路径平滑', () => {
  it('视线检测应被墙挡住', () => {
    const grid = [
      [0, 0, 0, 0, 0],
      [0, 0, 0, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 0, 0, 0, 0],
      [0, 0, 0, 0, 0],
    ]
    expect(lineOfSight(grid, [2, 0], [2, 4])).toBe(false)
    expect(lineOfSight(grid, [0, 0], [0, 4])).toBe(true)
    expect(lineOfSight(grid, [4, 0], [4, 4])).toBe(true)
  })

  it('阶梯路径应被抽稀成更少的关键点', () => {
    const grid = Array.from({ length: 8 }, () => Array(8).fill(0))
    const staircase = [
      [1, 1], [2, 1], [2, 2], [3, 2], [3, 3], [4, 3], [4, 4], [5, 4], [5, 5],
    ]
    const smoothed = smoothPath(grid, staircase)
    expect(smoothed[0]).toEqual([1, 1])
    expect(smoothed[smoothed.length - 1]).toEqual([5, 5])
    expect(smoothed.length).toBeLessThan(staircase.length)
  })

  it('回填后的每一对相邻格必须八连通', () => {
    const points = [
      [1, 1],
      [5, 5],
      [5, 1],
    ]
    const expanded = expandPath(points)
    expect(expanded[0]).toEqual([1, 1])
    expect(expanded[expanded.length - 1]).toEqual([5, 1])
    for (let index = 1; index < expanded.length; index += 1) {
      const dx = Math.abs(expanded[index][0] - expanded[index - 1][0])
      const dy = Math.abs(expanded[index][1] - expanded[index - 1][1])
      expect(Math.max(dx, dy)).toBe(1)
    }
  })

  it('平滑结果不应比原路径更长', () => {
    const grid = Array.from({ length: 10 }, () => Array(10).fill(0))
    const original = [
      [1, 1], [2, 1], [3, 1], [3, 2], [4, 2], [5, 2], [5, 3], [6, 3], [7, 3],
    ]
    const result = smoothAndExpand(grid, original)
    expect(result.length).toBeLessThanOrEqual(original.length)
    expect(result[0]).toEqual([1, 1])
    expect(result[result.length - 1]).toEqual([7, 3])
  })
})
