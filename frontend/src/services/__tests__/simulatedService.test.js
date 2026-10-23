/**
 * 模块功能：本地仿真器服务单元测试
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { SimulatedService } from '../simulatedService.js'

describe('SimulatedService', () => {
  let service

  beforeEach(() => {
    service = new SimulatedService()
    service._stopLoop()
  })

  afterEach(() => {
    service._stopLoop()
  })

  it('应返回合法地图对象', () => {
    const map = service.getMap()
    expect(map.width).toBeGreaterThan(0)
    expect(map.height).toBeGreaterThan(0)
    expect(map.grid.length).toBe(map.height)
    expect(map.start).toHaveLength(2)
    expect(map.charge_point).toHaveLength(2)
  })

  it('复位后机器人应位于起点且电量满格', () => {
    service.move(1, 0)
    service.reset()
    const map = service.getMap()
    expect(service._state.x).toBe(map.start[0])
    expect(service._state.y).toBe(map.start[1])
    expect(service._state.battery).toBe(100)
    expect(service._state.mode).toBe('manual')
  })

  it('computePath 应返回包含路径与访问节点数的对象', () => {
    const map = service.getMap()
    const result = service.computePath(map.start, map.goals[0])
    expect(result).toHaveProperty('path')
    expect(result).toHaveProperty('visited_count')
    expect(result).toHaveProperty('cost')
    if (result.path.length > 0) {
      expect(result.path[result.path.length - 1]).toEqual(map.goals[0])
    }
  })

  it('startPatrol 后巡检状态应为运行中', () => {
    service.startPatrol()
    const status = service.getPatrolStatus()
    expect(status.running).toBe(true)
    expect(service._patrol.totalGoals).toBeGreaterThan(0)
  })

  it('停止巡检后状态应恢复为 manual', () => {
    service.startPatrol()
    service.stopPatrol()
    expect(service.getPatrolStatus().running).toBe(false)
    expect(service._state.mode).toBe('manual')
  })

  it('onState 回调应接收到符合协议的状态帧', () => {
    return new Promise((resolve) => {
      let unsubscribe = null
      const callback = (frame) => {
        expect(frame.type).toBe('state')
        expect(frame.data).toHaveProperty('x')
        expect(frame.data).toHaveProperty('y')
        expect(frame.data).toHaveProperty('theta')
        expect(frame.data).toHaveProperty('battery')
        expect(frame.data).toHaveProperty('speed')
        expect(frame.data).toHaveProperty('mode')
        expect(frame.data).toHaveProperty('path')
        expect(frame.data).toHaveProperty('sensors')
        expect(frame.data.sensors).toHaveProperty('front')
        expect(frame.data.sensors).toHaveProperty('left')
        expect(frame.data.sensors).toHaveProperty('right')
        expect(frame.data.sensors).toHaveProperty('temperature')
        if (unsubscribe) {
          unsubscribe()
        }
        resolve()
      }
      unsubscribe = service.onState(callback)
    })
  })
})
