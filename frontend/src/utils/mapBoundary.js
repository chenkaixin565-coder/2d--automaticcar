/**
 * 模块功能：地图边界（真正的边界）工具函数
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-24
 * 版本：V1.0
 *
 * 地图最外环是真正的边界：不可编辑、不可清除、机器人不可穿越。
 * 本模块提供边界判定与边界墙强制补齐能力，供服务层、编辑交互、
 * 地图导入校验与渲染共用，保证该不变量在全链路上一致。
 */

/**
 * 判断坐标是否为边界墙单元格（最外环）。
 *
 * @param {number} x - 列坐标。
 * @param {number} y - 行坐标。
 * @param {number} width - 地图宽度。
 * @param {number} height - 地图高度。
 * @returns {boolean} 位于最外环返回 true。
 */
export function isBoundaryCell(x, y, width, height) {
  return x === 0 || y === 0 || x === width - 1 || y === height - 1
}

/**
 * 强制补齐四周边界墙（原地修改 grid）。
 *
 * @param {number[][]} grid - 二维栅格数组（0=通行 1=障碍）。
 * @param {number} width - 地图宽度。
 * @param {number} height - 地图高度。
 * @returns {number[][]} 补齐后的栅格数组。
 */
export function enforceBorder(grid, width, height) {
  for (let x = 0; x < width; x += 1) {
    grid[0][x] = 1
    grid[height - 1][x] = 1
  }
  for (let y = 0; y < height; y += 1) {
    grid[y][0] = 1
    grid[y][width - 1] = 1
  }
  return grid
}
