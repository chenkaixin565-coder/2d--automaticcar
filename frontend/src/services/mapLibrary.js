/**
 * 模块功能：地图库（V2.1）
 * 作者：智能巡检机器人二维仿真系统 V2.1 前端开发组
 * 日期：2026-10-27
 * 版本：V2.1
 *
 * 提供两套存储：
 *   1. 本机库（localStorage）：任何环境都能用，刷新/断网都在；
 *   2. 云端库（后端 /api/v1/maps）：多设备同步，需要后端在线（Render 全栈模式）。
 * 两张库的条目结构一致：{ id, name, width, height, goals, updated_at, map? }
 */

import { validateMap } from '../utils/mapIO.js'

/** 本机地图库的存储键。 */
const LOCAL_KEY = 'irm_map_library_v1'

/** 地图库最多保留条数（localStorage 容量有限，地图本身不大）。 */
const LOCAL_LIMIT = 60

/**
 * 读取本机库全部条目。
 *
 * @returns {Array<Object>} 地图条目数组（含完整 map 数据）。
 */
export function listLocal() {
  try {
    const raw = localStorage.getItem(LOCAL_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    console.warn('本机地图库读取失败：', error)
    return []
  }
}

/**
 * 写回本机库。
 *
 * @param {Array<Object>} items - 条目数组。
 */
function writeLocal(items) {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(items.slice(0, LOCAL_LIMIT)))
  } catch (error) {
    console.warn('本机地图库保存失败：', error)
  }
}

/**
 * 保存一张地图到本机库（同名覆盖）。
 *
 * @param {string} name - 地图名称。
 * @param {Object} map - 完整地图对象。
 * @param {string|null} id - 传入则覆盖该条目。
 * @returns {Object} 保存后的条目。
 */
export function saveLocal(name, map, id = null) {
  const items = listLocal()
  const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ')
  const cleanName = (name || '未命名地图').trim().slice(0, 40)
  const entryId = id || `local-${Date.now()}`
  const entry = {
    id: entryId,
    name: cleanName,
    width: map.width,
    height: map.height,
    goals: map.goals ? map.goals.length : 0,
    updated_at: stamp,
    map: JSON.parse(JSON.stringify(map)),
  }
  const index = items.findIndex((item) => item.id === entryId)
  if (index >= 0) {
    items[index] = entry
  } else {
    items.unshift(entry)
  }
  writeLocal(items)
  return entry
}

/**
 * 从本机库删除一张地图。
 *
 * @param {string} id - 条目 id。
 */
export function removeLocal(id) {
  writeLocal(listLocal().filter((item) => item.id !== id))
}

/**
 * 重命名本机库条目。
 *
 * @param {string} id - 条目 id。
 * @param {string} name - 新名称。
 */
export function renameLocal(id, name) {
  const items = listLocal()
  const target = items.find((item) => item.id === id)
  if (target) {
    target.name = (name || target.name).trim().slice(0, 40)
    writeLocal(items)
  }
}

/**
 * 取出条目中的地图对象，并做一次结构校验。
 *
 * @param {Object} entry - 库条目。
 * @returns {{ok: boolean, map?: Object, error?: string}}
 */
export function entryToMap(entry) {
  if (!entry || !entry.map) return { ok: false, error: '条目没有地图数据' }
  return validateMap(entry.map)
}

// ---------------------------------------------------------------------------
// 云端库（需要后端）
// ---------------------------------------------------------------------------

/**
 * 判断当前环境是否可用云端地图库。
 *
 * @param {string} baseUrl - 后端基地址（同源时为空字符串）。
 * @returns {boolean} 是否启用。
 */
export function cloudEnabled(baseUrl) {
  return typeof baseUrl === 'string'
}

/**
 * 列出云端地图。
 *
 * @param {string} baseUrl - 后端基地址。
 * @returns {Promise<Array<Object>>} 元信息数组。
 */
export async function listCloud(baseUrl) {
  const res = await fetch(`${baseUrl}/api/v1/maps`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * 保存地图到云端。
 *
 * @param {string} baseUrl - 后端基地址。
 * @param {string} name - 名称。
 * @param {Object} map - 地图对象。
 * @param {string|null} id - 覆盖用 id。
 * @returns {Promise<Object>} 元信息。
 */
export async function saveCloud(baseUrl, name, map, id = null) {
  const res = await fetch(`${baseUrl}/api/v1/maps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, map, id }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * 读取云端地图。
 *
 * @param {string} baseUrl - 后端基地址。
 * @param {string} id - 地图 id。
 * @returns {Promise<Object>} 完整地图。
 */
export async function loadCloud(baseUrl, id) {
  const res = await fetch(`${baseUrl}/api/v1/maps/${id}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * 删除云端地图。
 *
 * @param {string} baseUrl - 后端基地址。
 * @param {string} id - 地图 id。
 */
export async function removeCloud(baseUrl, id) {
  const res = await fetch(`${baseUrl}/api/v1/maps/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}
