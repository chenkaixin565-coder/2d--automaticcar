/**
 * 模块功能：轨迹分段工具单元测试（V2.3.4）
 * 作者：智能巡检机器人二维仿真系统 V2.3.4 前端开发组
 * 日期：2026-11-01
 * 版本：V2.3.4
 */

import { describe, expect, it } from 'vitest'
import { trailSegments } from '../trail.js'

describe('trailSegments', () => {
  it('连续走过的格子应保持为一段', () => {
    const trail = [
      [1, 1],
      [2, 1],
      [2, 2],
      [3, 3],
    ]
    const segments = trailSegments(trail)
    expect(segments).toHaveLength(1)
    expect(segments[0]).toHaveLength(4)
  })

  it('重新开始留下的"跳跃"应被切成多段', () => {
    // 先走到 [6,5]，点"重新开始"后被搬回 [1,1]，再走一步到 [2,1]
    const trail = [
      [1, 1],
      [2, 2],
      [3, 3],
      [5, 5],
      [6, 5],
      [1, 1],
      [2, 1],
    ]
    const segments = trailSegments(trail)
    expect(segments).toHaveLength(3)
    expect(segments[0][segments[0].length - 1]).toEqual([3, 3])
    expect(segments[1]).toEqual([
      [5, 5],
      [6, 5],
    ])
    expect(segments[2][0]).toEqual([1, 1])
  })

  it('孤点（前后都断开）不应产生线条', () => {
    const trail = [
      [1, 1],
      [2, 1],
      [9, 9],
      [3, 3],
    ]
    const segments = trailSegments(trail)
    expect(segments).toHaveLength(1)
    expect(segments[0]).toEqual([
      [1, 1],
      [2, 1],
    ])
  })

  it('空轨迹或非法点应安全返回空数组', () => {
    expect(trailSegments([])).toEqual([])
    expect(trailSegments(null)).toEqual([])
    expect(trailSegments([[1, 1], [null, 2], [3, 3]])).toEqual([])
  })
})
