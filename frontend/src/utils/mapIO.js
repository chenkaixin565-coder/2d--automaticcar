/**
 * 模块功能：地图 JSON 导入导出工具
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-24
 * 版本：V1.0
 *
 * 地图文件为 JSON 对象：{ width, height, grid, start, goals, charge_point }。
 * 导入时必须做完整结构校验，防止脏数据把仿真引擎带崩（防御式编程）。
 * 真正的边界：导入时强制补齐四周边界墙，且起点/充电点/巡检点不得位于边界环。
 */

import { enforceBorder, isBoundaryCell } from './mapBoundary.js'

/** 地图宽高合法范围。 */
const MIN_SIZE = 5
const MAX_SIZE = 100

/**
 * 校验地图对象结构是否合法。
 *
 * @param {Object} map - 待校验的地图对象。
 * @returns {{ ok: boolean, error?: string, map?: Object }} 校验结果。
 */
export function validateMap(map) {
  if (!map || typeof map !== 'object') {
    return { ok: false, error: '文件内容不是有效的地图对象' }
  }
  const { width, height, grid, start, goals, charge_point: chargePoint } = map

  if (!Number.isInteger(width) || !Number.isInteger(height) || width < MIN_SIZE || height < MIN_SIZE || width > MAX_SIZE || height > MAX_SIZE) {
    return { ok: false, error: `地图宽高必须是 ${MIN_SIZE}~${MAX_SIZE} 之间的整数` }
  }
  if (
    !Array.isArray(grid) ||
    grid.length !== height ||
    !grid.every(
      (row) =>
        Array.isArray(row) &&
        row.length === width &&
        row.every((cell) => cell === 0 || cell === 1 || cell === 2)
    )
  ) {
    return { ok: false, error: '栅格数据不完整：应为 height 行、每行 width 个 0/1/2 值（0=通行 1=障碍 2=固定屏障）' }
  }

  const inBounds = (p) =>
    Array.isArray(p) &&
    p.length === 2 &&
    Number.isInteger(p[0]) &&
    Number.isInteger(p[1]) &&
    p[0] >= 0 &&
    p[0] < width &&
    p[1] >= 0 &&
    p[1] < height
  const isFree = (p) => grid[p[1]][p[0]] === 0

  if (!inBounds(start)) {
    return { ok: false, error: '起点坐标非法' }
  }
  if (!isFree(start)) {
    return { ok: false, error: '起点不能位于障碍格上' }
  }
  if (!inBounds(chargePoint)) {
    return { ok: false, error: '充电点坐标非法' }
  }
  if (!isFree(chargePoint)) {
    return { ok: false, error: '充电点不能位于障碍格上' }
  }
  if (!Array.isArray(goals) || !goals.every(inBounds)) {
    return { ok: false, error: '巡检点列表格式非法' }
  }
  for (const goal of goals) {
    if (!isFree(goal)) {
      return { ok: false, error: `巡检点 [${goal[0]}, ${goal[1]}] 位于障碍格上` }
    }
  }

  // 真正的边界：关键点不得落在边界环上（边界墙不可通行、不可编辑）
  const onBoundary = (p) => isBoundaryCell(p[0], p[1], width, height)
  if (onBoundary(start)) {
    return { ok: false, error: '起点不能位于地图边界上（边界墙不可通行）' }
  }
  if (onBoundary(chargePoint)) {
    return { ok: false, error: '充电点不能位于地图边界上（边界墙不可通行）' }
  }
  for (const goal of goals) {
    if (onBoundary(goal)) {
      return { ok: false, error: `巡检点 [${goal[0]}, ${goal[1]}] 不能位于地图边界上` }
    }
  }

  // 强制补齐四周边界墙，保证真正的边界不变量
  enforceBorder(grid, width, height)

  // 只保留契约字段，剔除文件里的多余属性
  return { ok: true, map: { width, height, grid, start, goals, charge_point: chargePoint } }
}

/**
 * 触发浏览器下载地图 JSON 文件。
 *
 * @param {Object} map - 地图对象。
 * @param {string} [filename] - 下载文件名，缺省按时间戳生成。
 */
export function exportMap(map, filename) {
  const data = JSON.stringify(map, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `irm_map_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 读取文件并解析为地图对象（含结构校验）。
 *
 * @param {File} file - 用户选择的 .json 文件。
 * @returns {Promise<Object>} 校验通过的地图对象；失败时抛出 Error。
 */
export async function importMap(file) {
  const text = await file.text()
  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error('文件不是合法的 JSON 格式')
  }
  const result = validateMap(parsed)
  if (!result.ok) {
    throw new Error(result.error)
  }
  return result.map
}
