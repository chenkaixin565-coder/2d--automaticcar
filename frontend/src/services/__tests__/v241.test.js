/**
 * V2.4.1 权限前置检查测试。
 *
 * 复现的问题：没有操作密钥时，点地图仍然能"改"（本地格子变了、随后才弹密钥框）。
 * 修复后要求：一旦服务端明确告知没有权限，写操作在**改本地状态之前**就被拦下。
 */

import { beforeEach, describe, expect, it } from 'vitest'

import { RemoteService } from '../remoteService.js'

/**
 * 造一个不连 WebSocket 的 RemoteService 实例（只测鉴权与写保护）。
 *
 * @returns {RemoteService} 测试用实例。
 */
function makeService() {
  const service = Object.create(RemoteService.prototype)
  service._map = { width: 5, height: 5, grid: Array.from({ length: 5 }, () => Array(5).fill(0)) }
  service._state = { x: 0, y: 0, theta: 0, battery: 100, speed: 0, mode: 'manual', path: [], sensors: {} }
  service._authState = null
  service._canControl = false
  service._authChecked = false
  service._events = []
  service._emitEvent = (type, data) => service._events.push({ type, data })
  return service
}

describe('V2.4.1 写操作前置鉴权', () => {
  let service

  beforeEach(() => {
    service = makeService()
  })

  it('还没收到权限结论时不拦截（交给服务端判定）', () => {
    expect(service.authChecked).toBe(false)
    expect(service._ensureControl()).toBe(true)
    expect(service._events).toHaveLength(0)
  })

  it('已知无权限：直接弹框，不再发命令', () => {
    service._authChecked = true
    service._canControl = false
    expect(service._ensureControl()).toBe(false)
    expect(service._events).toHaveLength(1)
    expect(service._events[0].type).toBe('auth_required')
    expect(service._events[0].data.message).toMatch('操作密钥')
  })

  it('有权限时不弹框', () => {
    service._authChecked = true
    service._canControl = true
    expect(service._ensureControl()).toBe(true)
    expect(service._events).toHaveLength(0)
  })

  it('无权限时 updateMap 不改本地地图（不会出现"图上改了但服务端没接"）', () => {
    service._authChecked = true
    service._canControl = false
    const original = service._map
    service.updateMap({ width: 6, height: 6, grid: Array.from({ length: 6 }, () => Array(6).fill(0)) })
    expect(service._map).toBe(original)
    expect(service._events[0].type).toBe('auth_required')
  })

  it('无权限时 setCell 不发送 WebSocket 命令', () => {
    service._authChecked = true
    service._canControl = false
    let sent = false
    service._connected = true
    service._ws = { readyState: 1, send: () => { sent = true } }
    service.setCell(1, 1, 1)
    expect(sent).toBe(false)
    expect(service._events[0].type).toBe('auth_required')
  })
})
