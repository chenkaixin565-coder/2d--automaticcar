/**
 * 模块功能：轨迹分段工具
 * 作者：智能巡检机器人二维仿真系统 V2.3.4 前端开发组
 * 日期：2026-11-01
 * 版本：V2.3.4
 *
 * "重新开始"会保留之前走过的尾迹，机器人却被立刻搬回起点；如果直接把整条
 * 轨迹一笔画下去，画面上就会多出一条从"上次位置"直连"起点"的线，穿过障碍，
 * 看起来像多画了一段。这里按"相邻两格最多相差 1"把轨迹切成多段，
 * 断点处重新起笔，就不会再出现这种跨地图的连线。
 */

/**
 * 把轨迹切成若干连续段。
 *
 * 相邻两点在八邻域内（横纵差都 ≤ 1）视为连续，可以连线；否则视为断点，
 * 从该点重新起笔。长度不足 2 的段（孤点）会被丢弃，因为它们画不出线。
 *
 * @param {number[][]} trail - 轨迹坐标数组 [[x, y], ...]。
 * @returns {number[][][]} 连续段数组，每段也是 [x, y] 数组。
 */
export function trailSegments(trail) {
  const segments = []
  let current = []
  let previous = null

  for (const point of trail || []) {
    if (!Array.isArray(point) || point.length < 2) continue
    if (point[0] === null || point[1] === null) continue
    const x = Number(point[0])
    const y = Number(point[1])
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue

    const adjacent =
      previous !== null && Math.abs(x - previous[0]) <= 1 && Math.abs(y - previous[1]) <= 1

    if (!adjacent) {
      // 断点（或第一点）：先把上一段收尾，再从当前点重新起笔。
      if (current.length > 1) segments.push(current)
      current = [[x, y]]
    } else {
      current.push([x, y])
    }
    previous = [x, y]
  }

  if (current.length > 1) segments.push(current)
  return segments
}
