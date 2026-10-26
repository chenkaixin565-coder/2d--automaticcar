/**
 * 模块功能：新增功能单元测试（一键排障 / 内置地图 / 地图导入导出 / 机器人形象）
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-24
 * 版本：V1.0
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { SimulatedService } from '../simulatedService.js'
import { MAP_PRESETS, getPreset } from '../mapPresets.js'
import { validateMap } from '../../utils/mapIO.js'
import { getAvatar, setAvatar, clearAvatar, readAvatarFile } from '../../utils/robotAvatar.js'

describe('一键排障 resolveFault', () => {
  let service
  let events

  beforeEach(() => {
    localStorage.clear()
    service = new SimulatedService()
    service._stopLoop()
    events = []
    service.onEvent((frame) => events.push(frame))
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('机器人卡住时应清除正前方障碍并恢复手动模式', () => {
    // 起点 [1,1] 面向 +x（theta=0），在 [3,1] 放障碍后向右撞上去
    service.move(1, 0)
    expect(service._state.x).toBe(2)
    service._map.grid[1][3] = 1
    service.move(1, 0)
    expect(service._state.mode).toBe('blocked')

    service.resolveFault()

    expect(service._map.grid[1][3]).toBe(0)
    expect(service._state.mode).toBe('manual')
    const notices = events.filter((f) => f.type === 'notice')
    expect(notices[notices.length - 1].data.message).toContain('已排除前方障碍')
  })

  it('未卡住时调用只应推送提示且不改变地图', () => {
    const before = JSON.stringify(service._map.grid)
    service.resolveFault()
    const notices = events.filter((f) => f.type === 'notice')
    expect(notices[notices.length - 1].data.message).toContain('当前无阻塞故障')
    expect(JSON.stringify(service._map.grid)).toBe(before)
  })

  it('正前方是边界墙（无 obstacle 格可拆）时也应恢复手动模式', () => {
    // 直接撞地图上边界：theta 初始为 0 时先转身向上再撞
    service._state.theta = -Math.PI / 2
    service._state.x = 1
    service._state.y = 1
    service.move(0, -1) // 目标 [1,0] 是边界墙
    expect(service._state.mode).toBe('blocked')

    service.resolveFault()
    expect(service._state.mode).toBe('manual')
    // 边界墙不可清除：排障后仍是墙
    expect(service._map.grid[0][1]).toBe(1)
  })
})

describe('真正的边界（不可编辑 / 不可清除 / 不可穿越）', () => {
  let service

  beforeEach(() => {
    localStorage.clear()
    service = new SimulatedService()
    service._stopLoop()
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('所有内置预设的四周边界都是墙', () => {
    for (const preset of MAP_PRESETS) {
      const { width, height, grid } = preset
      for (let x = 0; x < width; x += 1) {
        expect(grid[0][x]).toBe(1)
        expect(grid[height - 1][x]).toBe(1)
      }
      for (let y = 0; y < height; y += 1) {
        expect(grid[y][0]).toBe(1)
        expect(grid[y][width - 1]).toBe(1)
      }
    }
  })

  it('updateMap 应强制补齐被擦除的边界墙', () => {
    const map = getPreset('factory')
    map.grid[0][5] = 0 // 擦掉一段上边界
    map.grid[10][0] = 0 // 擦掉一段左边界
    service.updateMap(map)
    expect(service._map.grid[0][5]).toBe(1)
    expect(service._map.grid[10][0]).toBe(1)
  })

  it('机器人永远无法移动到边界格外（越界即 blocked）', () => {
    service._state.x = 1
    service._state.y = 1
    service._state.theta = -Math.PI / 2
    service.move(0, -1)
    expect(service._state.mode).toBe('blocked')
    expect(service._state.y).toBe(1) // 位置不变
  })

  it('validateMap 应强制补齐导入地图的边界墙', () => {
    const map = {
      width: 8,
      height: 6,
      grid: Array.from({ length: 6 }, () => Array(8).fill(0)),
      start: [2, 2],
      goals: [[5, 4]],
      charge_point: [3, 3],
    }
    const result = validateMap(map)
    expect(result.ok).toBe(true)
    expect(result.map.grid[0][0]).toBe(1)
    expect(result.map.grid[0][3]).toBe(1)
    expect(result.map.grid[5][7]).toBe(1)
    expect(result.map.grid[2][0]).toBe(1)
  })

  it('validateMap 应拒绝起点 / 巡检点 / 充电点位于边界环', () => {
    const base = () => ({
      width: 8,
      height: 6,
      grid: Array.from({ length: 6 }, () => Array(8).fill(0)),
      start: [2, 2],
      goals: [[5, 4]],
      charge_point: [3, 3],
    })
    const startOnBorder = validateMap({ ...base(), start: [0, 2] })
    expect(startOnBorder.ok).toBe(false)
    expect(startOnBorder.error).toContain('边界')
    expect(validateMap({ ...base(), goals: [[4, 0]] }).ok).toBe(false)
    expect(validateMap({ ...base(), charge_point: [7, 3] }).ok).toBe(false)
  })
})

describe('内置地图预设', () => {
  let service

  beforeEach(() => {
    localStorage.clear()
    service = new SimulatedService()
    service._stopLoop()
  })

  afterEach(() => {
    service._stopLoop()
    localStorage.clear()
  })

  it('应提供三张预设且关键点均不在障碍上', () => {
    expect(MAP_PRESETS).toHaveLength(3)
    for (const preset of MAP_PRESETS) {
      const map = getPreset(preset.key)
      expect(map).not.toBeNull()
      expect(map.grid).toHaveLength(map.height)
      expect(map.grid[0]).toHaveLength(map.width)
      // 起点 / 充电点 / 巡检点必须可通行
      expect(map.grid[map.start[1]][map.start[0]]).toBe(0)
      expect(map.grid[map.charge_point[1]][map.charge_point[0]]).toBe(0)
      for (const goal of map.goals) {
        expect(map.grid[goal[1]][goal[0]]).toBe(0)
      }
    }
  })

  it('getPreset 应返回深拷贝，改写不影响预设本体', () => {
    const a = getPreset('factory')
    a.grid[1][1] = 1
    a.width = 999
    const b = getPreset('factory')
    expect(b.grid[1][1]).toBe(0)
    expect(b.width).toBe(30)
  })

  it('切换预设后地图尺寸、机器人位置与预设标识应同步更新', () => {
    service.loadPreset('warehouse')
    const map = service.getMap()
    expect(map.width).toBe(24)
    expect(map.height).toBe(16)
    expect(service.getPresetKey()).toBe('warehouse')
    // 机器人复位到新地图起点
    expect(service._state.x).toBe(map.start[0])
    expect(service._state.y).toBe(map.start[1])
    expect(service._state.mode).toBe('manual')

    service.loadPreset('dense')
    expect(service.getMap().width).toBe(28)
    expect(service.getPresetKey()).toBe('dense')
  })

  it('切换不存在预设时应推送提示且保持原地图', () => {
    const before = service.getMap().width
    service.loadPreset('not-exist')
    expect(service.getMap().width).toBe(before)
  })

  it('手动编辑地图后预设标识应清除', () => {
    service.loadPreset('factory')
    expect(service.getPresetKey()).toBe('factory')
    service.updateMap(service.getMap())
    expect(service.getPresetKey()).toBeNull()
  })

  it('预设应持久化到 localStorage，新建服务可恢复', () => {
    service.loadPreset('dense')
    const restored = new SimulatedService()
    restored._stopLoop()
    expect(restored.getPresetKey()).toBe('dense')
    expect(restored.getMap().width).toBe(28)
  })
})

describe('地图导入校验 validateMap', () => {
  /** 构造一张最小合法地图。 */
  function validMap() {
    const width = 8
    const height = 6
    const grid = Array.from({ length: height }, () => Array(width).fill(0))
    return {
      width,
      height,
      grid,
      start: [1, 1],
      goals: [[6, 4]],
      charge_point: [6, 1],
    }
  }

  it('合法地图应通过且剔除多余字段', () => {
    const map = validMap()
    map.extra = 'should be removed'
    const result = validateMap(map)
    expect(result.ok).toBe(true)
    expect(result.map).not.toHaveProperty('extra')
  })

  it('栅格行数不足应拒绝', () => {
    const map = validMap()
    map.grid = map.grid.slice(0, 3)
    expect(validateMap(map).ok).toBe(false)
  })

  it('栅格含非法值（2）应拒绝', () => {
    const map = validMap()
    map.grid[2][2] = 3
    expect(validateMap(map).ok).toBe(false)
    // V2.1：2 是合法的"固定屏障"，应当通过校验
    map.grid[2][2] = 2
    expect(validateMap(map).ok).toBe(true)
  })

  it('起点位于障碍上应拒绝', () => {
    const map = validMap()
    map.grid[1][1] = 1
    expect(validateMap(map).ok).toBe(false)
  })

  it('巡检点越界应拒绝', () => {
    const map = validMap()
    map.goals = [[99, 4]]
    expect(validateMap(map).ok).toBe(false)
  })

  it('充电点位于障碍上应拒绝', () => {
    const map = validMap()
    map.grid[1][6] = 1
    expect(validateMap(map).ok).toBe(false)
  })

  it('宽高非法应拒绝', () => {
    const map = validMap()
    map.width = 2
    expect(validateMap(map).ok).toBe(false)
  })
})

describe('机器人形象存储', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('保存 / 读取 / 清除应形成闭环', () => {
    expect(getAvatar()).toBeNull()
    setAvatar('data:image/png;base64,AAAA')
    expect(getAvatar()).toBe('data:image/png;base64,AAAA')
    clearAvatar()
    expect(getAvatar()).toBeNull()
  })

  it('readAvatarFile 应接受图片文件并返回 data URL', async () => {
    const file = new File(['fake-bytes'], 'robot.png', { type: 'image/png' })
    const dataUrl = await readAvatarFile(file)
    expect(dataUrl.startsWith('data:image/png;base64,')).toBe(true)
  })

  it('readAvatarFile 应拒绝非图片文件', async () => {
    const file = new File(['x'], 'map.json', { type: 'application/json' })
    await expect(readAvatarFile(file)).rejects.toThrow('图片文件')
  })

  it('readAvatarFile 应拒绝超过 2MB 的图片', async () => {
    const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'big.png', { type: 'image/png' })
    await expect(readAvatarFile(big)).rejects.toThrow('2MB')
  })
})
