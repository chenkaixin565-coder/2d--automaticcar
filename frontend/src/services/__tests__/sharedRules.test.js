/**
 * 模块功能：共享规则的单一来源测试（V2.2.0）
 * 作者：智能巡检机器人二维仿真系统 V2.2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.2.0
 *
 * 断言前端使用的每个数值都等于 `shared/simulation-rules.json`，
 * 默认地图也逐格等于 `shared/default-map.json`。任何一侧被改动而另一侧
 * 没跟上，这里会直接失败。
 */

import { describe, expect, it } from 'vitest'
import RULES from '../../../../shared/simulation-rules.json'
import DEFAULT_MAP from '../../../../shared/default-map.json'
import {
  BATTERY_IDLE_COST,
  BATTERY_MOVE_COST,
  CELL_METERS,
  CHARGE_RATE,
  CLEAR_OBSTACLE_COST,
  LOW_BATTERY_THRESHOLD,
  MAX_MAP_SIZE,
  MIN_MAP_SIZE,
  OVERHEAT_THRESHOLD,
  PENDING_LIMIT,
  SENSOR_FAULT_COOLDOWN_MS,
  SENSOR_JUMP_THRESHOLD,
  TEMP_BASE,
  TEMP_COOL_PER_TICK,
  TEMP_MAX,
  TEMP_RISE_PER_MOVE,
} from '../rules.js'
import { getPreset } from '../mapPresets.js'

describe('共享仿真规则', () => {
  it('电量规则与 JSON 一致', () => {
    expect(BATTERY_MOVE_COST).toBe(RULES.battery.move_cost)
    expect(BATTERY_IDLE_COST).toBe(RULES.battery.idle_cost)
    expect(LOW_BATTERY_THRESHOLD).toBe(RULES.battery.low_threshold)
    expect(CLEAR_OBSTACLE_COST).toBe(RULES.battery.clear_cost)
    expect(CHARGE_RATE).toBe(RULES.battery.charge_rate)
  })

  it('传感器与温度规则与 JSON 一致', () => {
    expect(CELL_METERS).toBe(RULES.sensor.cell_meters)
    expect(SENSOR_JUMP_THRESHOLD).toBe(RULES.sensor.fault_delta)
    expect(SENSOR_FAULT_COOLDOWN_MS).toBe(RULES.sensor.fault_cooldown_s * 1000)
    expect(TEMP_BASE).toBe(RULES.temperature.base)
    expect(TEMP_RISE_PER_MOVE).toBe(RULES.temperature.rise_per_move)
    expect(TEMP_COOL_PER_TICK).toBe(RULES.temperature.cool_per_tick)
    expect(TEMP_MAX).toBe(RULES.temperature.max)
    expect(OVERHEAT_THRESHOLD).toBe(RULES.temperature.overheat_threshold)
  })

  it('地图尺寸与记录上限与 JSON 一致', () => {
    expect(MIN_MAP_SIZE).toBe(RULES.maps.min_size)
    expect(MAX_MAP_SIZE).toBe(RULES.maps.max_size)
    expect(PENDING_LIMIT).toBe(RULES.maps.pending_limit)
  })

  it('默认厂房地图逐格等于 shared/default-map.json', () => {
    const preset = getPreset('factory')
    expect(preset.width).toBe(DEFAULT_MAP.width)
    expect(preset.height).toBe(DEFAULT_MAP.height)
    expect(preset.grid).toEqual(DEFAULT_MAP.grid)
    expect(preset.start).toEqual(DEFAULT_MAP.start)
    expect(preset.goals).toEqual(DEFAULT_MAP.goals)
    expect(preset.charge_point).toEqual(DEFAULT_MAP.charge_point)
  })
})
