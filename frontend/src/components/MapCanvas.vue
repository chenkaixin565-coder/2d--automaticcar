<template>
  <div class="relative w-full h-full rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900" :class="{ 'canvas-shake': shaking }">
    <canvas
      ref="canvasRef"
      class="absolute inset-0 w-full h-full cursor-crosshair touch-none"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="cancelInteraction(); handleHoverLeave()"
      @wheel.prevent="handleWheel"
      @contextmenu.prevent
      @touchstart="handleTouchStart"
      @touchmove="handleTouchMove"
      @touchend="handleTouchEnd"
    />
    <button
      class="absolute top-3 left-3 px-2.5 py-1 text-xs font-medium rounded-md bg-white/95 dark:bg-gray-800/95 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 shadow-sm"
      title="缩放到适合窗口（V2.0：固定在地图左上角）"
      @click="emit('fit')"
    >
      ⤢ 适配地图
    </button>
    <div
      v-if="editMode !== 'nav'"
      class="absolute bottom-3 left-14 px-2 py-1 text-xs rounded-md bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 pointer-events-none whitespace-nowrap"
    >
      {{ editModeLabel }}
    </div>
    <div class="absolute bottom-3 right-3 px-2 py-1 text-xs rounded-md bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
      缩放 {{ (scale * 100).toFixed(0) }}%
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：栅格地图画布
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 使用原生 Canvas 绘制地图栅格、障碍物、机器人、路径与已访问轨迹，
 * 并支持滚轮缩放、拖拽平移、悬停高亮以及地图编辑。
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { isBoundaryCell } from '../utils/mapBoundary.js'

/** 每个栅格的显示边长（像素）。 */
const CELL_PIXELS = 40

const props = defineProps({
  map: {
    type: Object,
    required: true,
  },
  robot: {
    type: Object,
    required: true,
  },
  visitedTrail: {
    type: Array,
    default: () => [],
  },
  playbackSnapshot: {
    type: Object,
    default: null,
  },
  scale: {
    type: Number,
    default: 1,
  },
  offset: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
  },
  editMode: {
    type: String,
    default: 'pan',
  },
  isDark: {
    type: Boolean,
    default: false,
  },
  robotAvatar: {
    type: String,
    default: null,
  },
  // 一键路线规划结果（V1.2）：{ goal, path, obstacles, clearable, ... }，未规划为 null
  routePlan: {
    type: Object,
    default: null,
  },
  // 巡检目标点是否显示编号（V1.2：标号点地图 / 不标号点地图）
  showGoalNumbers: {
    type: Boolean,
    default: true,
  },
  // 巡检受阻且无法绕行时前方待清障障碍格 [x, y]（V1.2），无阻碍为 null
  patrolBlockedCell: {
    type: Array,
    default: null,
  },
  // 是否显示走过的尾迹（V2.0：默认隐藏，可手动开启）
  showTrail: {
    type: Boolean,
    default: false,
  },
  // 待清障记录 [[x, y], ...]（V2.0）
  pending: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits([
  'view-change',
  'edit-obstacle',
  'clear-obstacle',
  'set-goal',
  'set-start',
  'set-charge',
  'hover',
  'fit',
])

const canvasRef = ref(null)
const isPanning = ref(false)
const isPainting = ref(false)
const lastPaintCell = ref(null)
// 边界格涂抹被拒时的红色闪烁反馈 { x, y, until }
const rejectCell = ref(null)
let rejectTimer = null
const panStart = ref({ x: 0, y: 0 })
const viewOffsetStart = ref({ x: 0, y: 0 })
const pinchStart = ref(null)
const pinchStartScale = ref(1)
const pinchStartOffset = ref({ x: 0, y: 0 })

const editModeLabel = computed(() => {
  const labels = {
    obstacle: '障碍编辑：按住左键拖动绘制（右键拖动平移）',
    goal: '设置巡检点：点击地图添加 / 移除',
    start: '设置起点：点击地图',
    charge: '设置充电点：点击地图',
    clear: '清障模式：点击障碍清除（每处 5% 电量）',
    nav: '浏览：拖拽平移、滚轮缩放',
  }
  return labels[props.editMode] || labels.nav
})

onMounted(() => {
  ensureAnimInit()
  render()
  window.addEventListener('resize', render)
})

onUnmounted(() => {
  window.removeEventListener('resize', render)
  if (animFrame !== null) {
    cancelAnimationFrame(animFrame)
    animFrame = null
  }
  if (shakeTimer) {
    clearTimeout(shakeTimer)
  }
  clearTimeout(rejectTimer)
})

watch(
  () => [props.map, props.robot, props.playbackSnapshot, props.scale, props.offset, props.editMode, props.isDark, props.routePlan, props.patrolBlockedCell, props.showGoalNumbers],
  () => {
    ensureAnimInit()
    render()
    // 状态帧（5Hz）到达后继续平滑动画，直到插值收敛；
    // 规划路线/受阻标记存在时还需要持续重绘以驱动闪烁动画（见 startAnimLoop）
    startAnimLoop()
  },
  { deep: true }
)

// --------------------------------------------------------------------------
// 2D 平滑动画
// 后端/仿真器以 5Hz 推送格子坐标，直接绘制会产生跳变。这里维护一份动画
// 坐标，用指数平滑向目标位置/朝向插值（时间常数 60ms），requestAnimationFrame
// 逐帧重绘；收敛后自动停表，不做无用空转。
// --------------------------------------------------------------------------

const animPos = { x: 0, y: 0, theta: 0 }
let animInitialized = false
let animFrame = null
let lastFrameTime = 0

/** 指数平滑时间常数（毫秒）：越小越紧跟，越大越拖尾。 */
const ANIM_TAU_MS = 60

/** 首帧前把动画坐标对齐到当前机器人位置，避免从原点飞入。 */
function ensureAnimInit() {
  if (animInitialized) return
  animPos.x = props.robot.x
  animPos.y = props.robot.y
  animPos.theta = props.robot.theta || 0
  animInitialized = true
}

/** 角度最短路径插值，避免绕远路（如 350° → 10° 不转 340°）。 */
function lerpAngle(a, b, t) {
  let diff = b - a
  while (diff > Math.PI) diff -= Math.PI * 2
  while (diff < -Math.PI) diff += Math.PI * 2
  return a + diff * t
}

/** 启动动画循环；已在运行则复用。 */
function startAnimLoop() {
  if (animFrame !== null) return
  lastFrameTime = performance.now()
  const step = (now) => {
    // 后台标签页回来后 dt 可能极大，截断到 100ms 防止瞬移
    const dt = Math.min(100, now - lastFrameTime)
    lastFrameTime = now
    const target = props.playbackSnapshot || props.robot
    const t = 1 - Math.exp(-dt / ANIM_TAU_MS)
    animPos.x += (target.x - animPos.x) * t
    animPos.y += (target.y - animPos.y) * t
    animPos.theta = lerpAngle(animPos.theta, target.theta || 0, t)

    // 收敛判定：位置与朝向都足够接近则吸附
    const remainTheta = lerpAngle(animPos.theta, target.theta || 0, 1) - animPos.theta
    const settled =
      Math.abs(target.x - animPos.x) < 0.002 &&
      Math.abs(target.y - animPos.y) < 0.002 &&
      Math.abs(remainTheta) < 0.002
    if (settled) {
      animPos.x = target.x
      animPos.y = target.y
      animPos.theta = target.theta || 0
      // 规划路线（闪烁虚线）或巡检受阻标记存在时需要持续重绘驱动动画，
      // 二者都消失后才停表，不做无用空转
      const continuous = !!(props.routePlan || props.patrolBlockedCell)
      if (!continuous) {
        animFrame = null
      } else {
        animFrame = requestAnimationFrame(step)
      }
    } else {
      animFrame = requestAnimationFrame(step)
    }
    render()
  }
  animFrame = requestAnimationFrame(step)
}

// --------------------------------------------------------------------------
// 一键路线规划渲染（V1.2）
// 规划路径分两段绘制：已走过的路段为稳定蓝色虚线，未走的路段为琥珀色
// 闪烁虚线（lineDashOffset 动画 + 透明度呼吸）；路径上的障碍按电力预算
// 绘制红色标记（可清）或灰色空心标记（电量不足未纳入）。
// --------------------------------------------------------------------------

// 已走过的规划路径前缀长度（格数）：只增不减，机器人沿规划路线前进时
// 对应路段由闪烁虚线切换为稳定虚线；新规划到达时重置为 0
const walkedPrefix = ref(0)

watch(
  () => props.routePlan,
  () => {
    walkedPrefix.value = 0
  }
)

/**
 * 根据机器人当前位置更新已走前缀：取规划路径上机器人所在格的下标。
 */
function updateWalkedPrefix() {
  const plan = props.routePlan
  if (!plan || !plan.path || plan.path.length === 0) return
  const pos = props.playbackSnapshot || props.robot
  for (let i = plan.path.length - 1; i >= 0; i -= 1) {
    if (plan.path[i][0] === pos.x && plan.path[i][1] === pos.y) {
      if (i > walkedPrefix.value) walkedPrefix.value = i
      return
    }
  }
}

/**
 * 绘制规划路线：已走段稳定蓝虚线 + 未走段琥珀闪烁虚线。
 */
function drawPlannedRoute(ctx) {
  const plan = props.routePlan
  if (!plan || !plan.path || plan.path.length < 2) return
  const total = plan.path.length
  const walked = Math.min(walkedPrefix.value, total - 1)
  const phase = (performance.now() % 1000) / 1000

  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.lineWidth = 4 / props.scale

  const traceSegment = (from, to) => {
    ctx.beginPath()
    for (let i = from; i <= to; i += 1) {
      const [x, y] = plan.path[i]
      const px = (x + 0.5) * CELL_PIXELS
      const py = (y + 0.5) * CELL_PIXELS
      if (i === from) {
        ctx.moveTo(px, py)
      } else {
        ctx.lineTo(px, py)
      }
    }
    ctx.stroke()
  }

  // 已走段：稳定蓝色虚线
  if (walked >= 1) {
    ctx.strokeStyle = props.isDark ? '#60a5fa' : '#3b82f6'
    ctx.setLineDash([8 / props.scale, 5 / props.scale])
    traceSegment(0, walked)
  }

  // 未走段：琥珀色闪烁虚线（透明度呼吸 + 流动偏移）
  if (walked < total - 1) {
    const pulse = 0.55 + 0.45 * Math.sin(phase * Math.PI * 2)
    ctx.strokeStyle = `rgba(245, 158, 11, ${pulse.toFixed(3)})`
    ctx.setLineDash([8 / props.scale, 5 / props.scale])
    ctx.lineDashOffset = -phase * 13 / props.scale
    traceSegment(walked, total - 1)
    ctx.lineDashOffset = 0
  }

  ctx.setLineDash([])
  ctx.restore()
}

/**
 * 绘制规划路径上的清障目标标记：电力预算内为红色标记（白 ×），
 * 电量不足未纳入的为灰色空心标记。
 */
function drawPlanMarks(ctx) {
  const plan = props.routePlan
  if (!plan || !plan.obstacles || plan.obstacles.length === 0) return
  const clearable = new Set((plan.clearable || []).map(([x, y]) => `${x},${y}`))
  const phase = (performance.now() % 1000) / 1000
  const pulse = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2)

  ctx.save()
  plan.obstacles.forEach(([x, y]) => {
    const cx = (x + 0.5) * CELL_PIXELS
    const cy = (y + 0.5) * CELL_PIXELS
    const r = CELL_PIXELS * 0.3
    if (clearable.has(`${x},${y}`)) {
      // 预算内待清障：红色实心 + 白色 ×（呼吸透明度，吸引注意力）
      ctx.fillStyle = `rgba(239, 68, 68, ${(0.7 + 0.3 * pulse).toFixed(3)})`
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#dc2626'
      ctx.lineWidth = 2 / props.scale
      ctx.stroke()
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 2.5 / props.scale
      ctx.beginPath()
      ctx.moveTo(cx - r * 0.45, cy - r * 0.45)
      ctx.lineTo(cx + r * 0.45, cy + r * 0.45)
      ctx.moveTo(cx + r * 0.45, cy - r * 0.45)
      ctx.lineTo(cx - r * 0.45, cy + r * 0.45)
      ctx.stroke()
    } else {
      // 电量不足未纳入：灰色空心虚线圆
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.9)'
      ctx.lineWidth = 2 / props.scale
      ctx.setLineDash([4 / props.scale, 3 / props.scale])
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.stroke()
      ctx.setLineDash([])
    }
  })
  ctx.restore()
}

/**
 * 绘制待清障记录：橙色小圆环 + 叉号，表示"巡检时被跳过、还没清掉的障碍"。
 */
function drawPendingMarks(ctx) {
  const cells = props.pending || []
  if (!cells.length) return
  const inset = CELL_PIXELS * 0.28
  ctx.save()
  ctx.strokeStyle = '#f59e0b'
  ctx.lineWidth = 2 / props.scale
  cells.forEach((cell) => {
    const x = cell[0] * CELL_PIXELS
    const y = cell[1] * CELL_PIXELS
    ctx.strokeRect(x + inset, y + inset, CELL_PIXELS - inset * 2, CELL_PIXELS - inset * 2)
    ctx.beginPath()
    ctx.moveTo(x + inset, y + inset)
    ctx.lineTo(x + CELL_PIXELS - inset, y + CELL_PIXELS - inset)
    ctx.moveTo(x + CELL_PIXELS - inset, y + inset)
    ctx.lineTo(x + inset, y + CELL_PIXELS - inset)
    ctx.stroke()
  })
  ctx.restore()
}

/**
 * 绘制巡检受阻标记：橙色呼吸描边 + 中心感叹号，提示可一键清障。
 */
function drawPatrolBlocked(ctx) {
  const cell = props.patrolBlockedCell
  if (!cell || cell.length < 2) return
  const [x, y] = cell
  if (x < 0 || x >= props.map.width || y < 0 || y >= props.map.height) return
  const px = x * CELL_PIXELS
  const py = y * CELL_PIXELS
  const phase = (performance.now() % 1000) / 1000
  const pulse = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2)

  ctx.save()
  ctx.strokeStyle = `rgba(249, 115, 22, ${(0.55 + 0.45 * pulse).toFixed(3)})`
  ctx.lineWidth = 3 / props.scale
  ctx.setLineDash([5 / props.scale, 3 / props.scale])
  const inset = 2 / props.scale
  ctx.strokeRect(px + inset, py + inset, CELL_PIXELS - inset * 2, CELL_PIXELS - inset * 2)
  ctx.setLineDash([])

  // 中心橙色圆 + 白色感叹号
  const cx = px + CELL_PIXELS / 2
  const cy = py + CELL_PIXELS / 2
  const r = CELL_PIXELS * 0.28
  ctx.fillStyle = '#f97316'
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#ffffff'
  ctx.font = `bold ${CELL_PIXELS * 0.4}px ui-sans-serif, system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('!', cx, cy + CELL_PIXELS * 0.02)
  ctx.restore()
}

// 撞障碍抖动：机器人撞墙（mode 变为 blocked）时触发一次短促抖动。
const shaking = ref(false)
let shakeTimer = null

watch(
  () => props.robot.mode,
  (mode, prev) => {
    if (mode === 'blocked' && prev !== 'blocked') {
      triggerShake()
    }
  }
)

function triggerShake() {
  shaking.value = false
  // 下一帧再置位，确保同一状态连续触发时动画能重启。
  requestAnimationFrame(() => {
    shaking.value = true
    clearTimeout(shakeTimer)
    shakeTimer = setTimeout(() => {
      shaking.value = false
    }, 360)
  })
}

/**
 * 主绘制函数。
 */
function render() {
  const canvas = canvasRef.value
  if (!canvas) return

  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.floor(rect.width * dpr))
  canvas.height = Math.max(1, Math.floor(rect.height * dpr))

  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 适配高清屏：先按 DPR 缩放
  ctx.save()
  ctx.scale(dpr, dpr)

  // 应用世界坐标变换：平移 + 缩放
  ctx.save()
  ctx.translate(props.offset.x, props.offset.y)
  ctx.scale(props.scale, props.scale)

  drawGrid(ctx)
  drawSpecialCells(ctx)
  drawObstacles(ctx)
  drawRejectFlash(ctx)

  const snapshot = props.playbackSnapshot
  if (snapshot) {
    // 回放时按快照里的尾迹长度切片，避免每帧深拷贝整条轨迹
    drawTrail(ctx, (props.visitedTrail || []).slice(0, snapshot.trailLen || 0))
    drawPath(ctx, snapshot.path || [])
    drawRobot(ctx, { x: animPos.x, y: animPos.y, theta: animPos.theta }, true)
  } else {
    // V2.0：尾迹默认隐藏，由"显示尾迹"开关控制
    if (props.showTrail) {
      drawTrail(ctx, props.visitedTrail)
    }
    drawPlannedRoute(ctx)
    drawPath(ctx, props.robot.path || [])
    drawRobot(ctx, { x: animPos.x, y: animPos.y, theta: animPos.theta }, false)
  }

  // 规划清障标记、待清障记录与巡检受阻标记绘制在机器人之上，保证障碍格上可见
  drawPlanMarks(ctx)
  drawPendingMarks(ctx)
  drawPatrolBlocked(ctx)
  updateWalkedPrefix()
  drawHover(ctx)

  ctx.restore()
  ctx.restore()
}

/**
 * 绘制栅格线。
 */
function drawGrid(ctx) {
  const width = props.map.width
  const height = props.map.height
  ctx.strokeStyle = props.isDark ? '#374151' : '#e5e7eb'
  ctx.lineWidth = 1 / props.scale
  ctx.beginPath()
  for (let x = 0; x <= width; x += 1) {
    ctx.moveTo(x * CELL_PIXELS, 0)
    ctx.lineTo(x * CELL_PIXELS, height * CELL_PIXELS)
  }
  for (let y = 0; y <= height; y += 1) {
    ctx.moveTo(0, y * CELL_PIXELS)
    ctx.lineTo(width * CELL_PIXELS, y * CELL_PIXELS)
  }
  ctx.stroke()
}

/**
 * 绘制起点、充电点与巡检目标点。
 * 巡检目标点的编号可通过 showGoalNumbers 开关切换（标号点地图 / 不标号点地图）。
 */
function drawSpecialCells(ctx) {
  const { start, charge_point: chargePoint, goals } = props.map
  drawMarker(ctx, start, '#22c55e', 'S')
  drawMarker(ctx, chargePoint, '#f97316', 'C')
  if (goals) {
    goals.forEach((goal, index) => {
      // 圆点只表示位置；编号改成圆点右侧的横排小徽标，避免盖住图标本身
      drawMarker(ctx, goal, '#3b82f6', '')
      if (props.showGoalNumbers) {
        drawGoalBadge(ctx, goal, String(index + 1))
      }
    })
  }
}

/**
 * 绘制单个标记点。label 为空字符串时仅绘制圆点（不显示编号）。
 */
function drawMarker(ctx, pos, color, label) {
  const cx = (pos[0] + 0.5) * CELL_PIXELS
  const cy = (pos[1] + 0.5) * CELL_PIXELS
  const radius = CELL_PIXELS * 0.35

  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(cx, cy, radius, 0, Math.PI * 2)
  ctx.fill()

  if (!label) return

  ctx.fillStyle = '#ffffff'
  ctx.font = `${CELL_PIXELS * 0.35}px ui-sans-serif, system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, cx, cy)
}

/**
 * 绘制巡检点编号徽标：贴在圆点右上方的横排小标签。
 *
 * @param {Object} ctx - Canvas 上下文。
 * @param {number[]} pos - 栅格坐标 [x, y]。
 * @param {string} label - 编号文本。
 */
function drawGoalBadge(ctx, pos, label) {
  const cx = (pos[0] + 0.5) * CELL_PIXELS
  const cy = (pos[1] + 0.5) * CELL_PIXELS
  // 低缩放时按屏幕像素兜底，避免编号缩成看不清的小点
  const fs = Math.max(CELL_PIXELS * 0.3, 9 / props.scale)
  ctx.font = `600 ${fs}px ui-sans-serif, system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const w = Math.max(fs * 1.5, ctx.measureText(label).width + fs * 0.6)
  const h = fs * 1.5
  const bx = cx + CELL_PIXELS * 0.18
  const by = cy - CELL_PIXELS * 0.62

  ctx.save()
  ctx.fillStyle = props.isDark ? '#1d4ed8' : '#2563eb'
  ctx.strokeStyle = props.isDark ? '#0b1220' : '#ffffff'
  ctx.lineWidth = 1.5 / props.scale
  const r = 3 / props.scale
  ctx.beginPath()
  ctx.moveTo(bx + r, by)
  ctx.arcTo(bx + w, by, bx + w, by + h, r)
  ctx.arcTo(bx + w, by + h, bx, by + h, r)
  ctx.arcTo(bx, by + h, bx, by, r)
  ctx.arcTo(bx, by, bx + w, by, r)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = '#ffffff'
  ctx.font = `600 ${fs}px ui-sans-serif, system-ui, sans-serif`
  ctx.fillText(label, bx + w / 2, by + h / 2 + 0.5)
  ctx.restore()
}

/**
 * 绘制障碍物：普通障碍为灰色块，最外环边界墙用深色 + 斜线纹理
 * 明确区分“真正的边界”（不可编辑、不可清除、机器人不可穿越）。
 */
function drawObstacles(ctx) {
  const grid = props.map.grid
  const width = props.map.width
  const height = props.map.height
  const normalColor = props.isDark ? '#4b5563' : '#374151'
  const boundaryColor = props.isDark ? '#020617' : '#0f172a'
  const hatchColor = props.isDark ? '#1e293b' : '#334155'

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (grid[y][x] !== 1) continue
      const px = x * CELL_PIXELS
      const py = y * CELL_PIXELS
      if (isBoundaryCell(x, y, width, height)) {
        // 边界墙：深色底 + 两条斜线，视觉上与普通障碍明显区分
        ctx.fillStyle = boundaryColor
        ctx.fillRect(px, py, CELL_PIXELS, CELL_PIXELS)
        ctx.strokeStyle = hatchColor
        ctx.lineWidth = 2 / props.scale
        ctx.beginPath()
        ctx.moveTo(px, py)
        ctx.lineTo(px + CELL_PIXELS, py + CELL_PIXELS)
        ctx.moveTo(px + CELL_PIXELS, py)
        ctx.lineTo(px, py + CELL_PIXELS)
        ctx.stroke()
      } else {
        ctx.fillStyle = normalColor
        ctx.fillRect(px, py, CELL_PIXELS, CELL_PIXELS)
      }
    }
  }
}

/**
 * 绘制边界格涂抹被拒的红色闪烁反馈。
 */
function drawRejectFlash(ctx) {
  const cell = rejectCell.value
  if (!cell || Date.now() > cell.until) return
  const px = cell.x * CELL_PIXELS
  const py = cell.y * CELL_PIXELS
  ctx.fillStyle = 'rgba(239, 68, 68, 0.35)'
  ctx.fillRect(px, py, CELL_PIXELS, CELL_PIXELS)
  ctx.strokeStyle = '#ef4444'
  ctx.lineWidth = 2 / props.scale
  ctx.strokeRect(px, py, CELL_PIXELS, CELL_PIXELS)
}

/**
 * 触发边界格涂抹被拒的闪烁反馈（400ms 后自动清除并重绘）。
 */
function flashRejectCell(x, y) {
  rejectCell.value = { x, y, until: Date.now() + 400 }
  render()
  clearTimeout(rejectTimer)
  rejectTimer = setTimeout(() => {
    rejectCell.value = null
    render()
  }, 400)
}

/**
 * 绘制已访问轨迹。
 */
function drawTrail(ctx, trail) {
  if (!trail || trail.length < 2) return
  ctx.save()
  // V2.0：尾迹统一用细虚线，与"闪烁虚线的规划路线"区分开。
  ctx.strokeStyle = props.isDark ? 'rgba(148, 163, 184, 0.75)' : 'rgba(100, 116, 139, 0.6)'
  ctx.lineWidth = 1.6 / props.scale
  ctx.setLineDash([5 / props.scale, 5 / props.scale])
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  trail.forEach(([x, y], index) => {
    const px = (x + 0.5) * CELL_PIXELS
    const py = (y + 0.5) * CELL_PIXELS
    if (index === 0) {
      ctx.moveTo(px, py)
    } else {
      ctx.lineTo(px, py)
    }
  })
  ctx.stroke()
  ctx.restore()
}

/**
 * 绘制规划路径。
 */
function drawPath(ctx, path) {
  if (!path || path.length < 2) return
  ctx.strokeStyle = props.isDark ? '#60a5fa' : '#3b82f6'
  ctx.lineWidth = 3 / props.scale
  ctx.setLineDash([6 / props.scale, 4 / props.scale])
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  path.forEach(([x, y], index) => {
    const px = (x + 0.5) * CELL_PIXELS
    const py = (y + 0.5) * CELL_PIXELS
    if (index === 0) {
      ctx.moveTo(px, py)
    } else {
      ctx.lineTo(px, py)
    }
  })
  ctx.stroke()
  ctx.setLineDash([])
}

/**
 * 绘制机器人（自定义形象图片或圆形机身 + 朝向箭头）。
 * 形象图片保持正立，朝向由白色箭头指示，避免上传图标方向感丢失。
 */
function drawRobot(ctx, state, isGhost) {
  const cx = (state.x + 0.5) * CELL_PIXELS
  const cy = (state.y + 0.5) * CELL_PIXELS
  // 缩得很小时按屏幕像素兜底，保证仍能辨认出机器人
  const size = Math.max(CELL_PIXELS * 0.9, 18 / props.scale)
  const theta = state.theta || 0
  const alpha = isGhost ? 0.45 : 1

  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(theta)

  if (!isGhost && avatarImage.value) {
    const r = size / 2
    ctx.rotate(-theta)
    ctx.drawImage(avatarImage.value, -r, -r, size, size)
    ctx.restore()
    return
  }

  const body = size * 0.66
  ctx.globalAlpha = alpha

  // 阴影，让机器人从栅格里"浮"起来
  ctx.fillStyle = 'rgba(15, 23, 42, 0.18)'
  ctx.beginPath()
  ctx.ellipse(body * 0.08, body * 0.12, body * 0.62, body * 0.55, 0, 0, Math.PI * 2)
  ctx.fill()

  // 左右履带轮：深灰圆角块，明显区分于机身
  ctx.fillStyle = props.isDark ? '#111827' : '#334155'
  const wheelW = body * 0.3
  const wheelH = body * 0.78
  for (const sign of [-1, 1]) {
    ctx.beginPath()
    ctx.roundRect(
      sign * (body / 2 + wheelW * 0.18) - wheelW / 2,
      -wheelH / 2,
      wheelW,
      wheelH,
      wheelW * 0.45
    )
    ctx.fill()
  }

  // 机身：蓝色圆角矩形 + 白色描边
  const gradient = ctx.createLinearGradient(-body / 2, -body / 2, body / 2, body / 2)
  gradient.addColorStop(0, isGhost ? '#93c5fd' : '#60a5fa')
  gradient.addColorStop(1, isGhost ? '#60a5fa' : '#1d4ed8')
  ctx.fillStyle = gradient
  ctx.strokeStyle = props.isDark ? '#e2e8f0' : '#ffffff'
  ctx.lineWidth = Math.max(1.5, 2 / props.scale)
  ctx.beginPath()
  ctx.roundRect(-body / 2, -body / 2, body, body, body * 0.26)
  ctx.fill()
  ctx.stroke()

  // 顶部传感器穹顶
  ctx.fillStyle = isGhost ? '#dbeafe' : '#e0f2fe'
  ctx.beginPath()
  ctx.arc(body * 0.12, 0, body * 0.19, 0, Math.PI * 2)
  ctx.fill()
  ctx.strokeStyle = '#0ea5e9'
  ctx.lineWidth = Math.max(1, 1.5 / props.scale)
  ctx.stroke()

  // 前向箭头：贴在机身前方的三角，明确朝向
  ctx.fillStyle = '#ef4444'
  ctx.beginPath()
  ctx.moveTo(body * 0.92, 0)
  ctx.lineTo(body * 0.52, -body * 0.2)
  ctx.lineTo(body * 0.52, body * 0.2)
  ctx.closePath()
  ctx.fill()

  // 状态灯：低电量/阻塞时变红，否则绿色
  const lampColor = isGhost
    ? '#93c5fd'
    : state.mode === 'blocked' || (state.battery !== undefined && state.battery < 20)
      ? '#ef4444'
      : '#22c55e'
  ctx.fillStyle = lampColor
  ctx.beginPath()
  ctx.arc(-body * 0.24, -body * 0.24, Math.max(2, body * 0.1), 0, Math.PI * 2)
  ctx.fill()

  ctx.globalAlpha = 1
  ctx.restore()
}

/**
 * 绘制鼠标悬停高亮。
 */
function drawHover(ctx) {
  if (!hoverCell.value || props.editMode === 'pan') return
  const [x, y] = hoverCell.value
  if (x < 0 || x >= props.map.width || y < 0 || y >= props.map.height) return
  ctx.fillStyle = 'rgba(59, 130, 246, 0.2)'
  ctx.fillRect(x * CELL_PIXELS, y * CELL_PIXELS, CELL_PIXELS, CELL_PIXELS)
  ctx.strokeStyle = '#3b82f6'
  ctx.lineWidth = 1 / props.scale
  ctx.strokeRect(x * CELL_PIXELS, y * CELL_PIXELS, CELL_PIXELS, CELL_PIXELS)
}

// --------------------------------------------------------------------------
// 交互处理
// --------------------------------------------------------------------------

const hoverCell = ref(null)

// 悬停格变化时立即重绘，保证编辑模式下的高亮跟手
watch(hoverCell, () => render())

// --------------------------------------------------------------------------
// 自定义机器人形象：异步加载用户上传的图片，失败时回退默认矢量绘制
// --------------------------------------------------------------------------

const avatarImage = ref(null)

watch(
  () => props.robotAvatar,
  (url) => {
    avatarImage.value = null
    if (!url) {
      render()
      return
    }
    const img = new Image()
    img.onload = () => {
      avatarImage.value = img
      render()
    }
    img.onerror = () => {
      console.warn('机器人形象加载失败，使用默认绘制')
      avatarImage.value = null
      render()
    }
    img.src = url
  },
  { immediate: true }
)

function getEventPos(event) {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function screenToCell(screenX, screenY) {
  const worldX = (screenX - props.offset.x) / props.scale
  const worldY = (screenY - props.offset.y) / props.scale
  return [Math.floor(worldX / CELL_PIXELS), Math.floor(worldY / CELL_PIXELS)]
}

/**
 * 交互状态：按下位置与是否发生拖拽。
 * V2.0 起不再需要"平移模式"——任何模式下拖拽都能移动地图，
 * 编辑动作改为"按下不移动、松开才算点击"，避免误拖改图。
 */
const downPos = ref(null)
const downCell = ref(null)
const movedSinceDown = ref(false)

function handleMouseDown(event) {
  const pos = getEventPos(event)
  const cell = screenToCell(pos.x, pos.y)
  downPos.value = pos
  downCell.value = cell
  movedSinceDown.value = false

  // 右键 / 中键：任何模式下都能拖动地图。
  if (event.button === 1 || event.button === 2) {
    isPanning.value = true
    panStart.value = pos
    viewOffsetStart.value = { ...props.offset }
    return
  }
  if (event.button !== 0) return

  if (props.editMode === 'obstacle') {
    // 障碍模式：左键拖动只"画"不"擦"（擦除请用清障模式，消耗电量）。
    if (!inBounds(cell)) return
    isPainting.value = true
    lastPaintCell.value = `${cell[0]},${cell[1]}`
    if (isBoundaryCell(cell[0], cell[1], props.map.width, props.map.height)) {
      flashRejectCell(cell[0], cell[1])
      return
    }
    emit('edit-obstacle', { x: cell[0], y: cell[1], value: 1 })
    return
  }

  // 其它模式：先按"可能拖拽"处理，松开时若没移动才执行点击动作。
  isPanning.value = true
  panStart.value = pos
  viewOffsetStart.value = { ...props.offset }
}

function handleMouseMove(event) {
  if (pinchStart.value) return
  const pos = getEventPos(event)
  const cell = screenToCell(pos.x, pos.y)
  if (inBounds(cell)) {
    hoverCell.value = cell
    emit('hover', { x: cell[0], y: cell[1] })
  } else {
    hoverCell.value = null
    emit('hover', null)
  }

  if (isPainting.value && props.editMode === 'obstacle') {
    const key = `${cell[0]},${cell[1]}`
    if (inBounds(cell) && key !== lastPaintCell.value) {
      lastPaintCell.value = key
      if (isBoundaryCell(cell[0], cell[1], props.map.width, props.map.height)) {
        flashRejectCell(cell[0], cell[1])
        return
      }
      emit('edit-obstacle', { x: cell[0], y: cell[1], value: 1 })
    }
    return
  }

  if (isPanning.value && downPos.value) {
    const dx = pos.x - panStart.value.x
    const dy = pos.y - panStart.value.y
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
      movedSinceDown.value = true
    }
    if (movedSinceDown.value) {
      emit('view-change', {
        scale: props.scale,
        offset: { x: viewOffsetStart.value.x + dx, y: viewOffsetStart.value.y + dy },
      })
    }
  }
}

function handleMouseUp() {
  // 只有"按下后没拖动"才算一次点击编辑。
  if (
    !isPainting.value &&
    !movedSinceDown.value &&
    downCell.value &&
    inBounds(downCell.value)
  ) {
    applyClick(downCell.value)
  }
  resetInteraction()
}

/** 鼠标/手指移出画布：取消本次交互，不触发编辑。 */
function cancelInteraction() {
  resetInteraction()
}

function resetInteraction() {
  isPanning.value = false
  isPainting.value = false
  lastPaintCell.value = null
  downPos.value = null
  downCell.value = null
  movedSinceDown.value = false
}

/**
 * 按当前编辑模式执行一次点击动作。
 *
 * @param {number[]} cell - 栅格坐标 [x, y]。
 */
function applyClick(cell) {
  const [x, y] = cell
  if (props.editMode === 'goal') {
    emit('set-goal', { x, y })
  } else if (props.editMode === 'clear') {
    if (props.map.grid[y][x] === 1) emit('clear-obstacle', { x, y })
  } else if (props.editMode === 'start') {
    if (props.map.grid[y][x] === 0) emit('set-start', { x, y })
  } else if (props.editMode === 'charge') {
    if (props.map.grid[y][x] === 0) emit('set-charge', { x, y })
  }
}

function handleWheel(event) {
  const pos = getEventPos(event)
  const zoomFactor = event.deltaY < 0 ? 1.1 : 0.9
  const newScale = Math.min(Math.max(0.3, props.scale * zoomFactor), 5)

  // 以鼠标位置为中心缩放
  const worldX = (pos.x - props.offset.x) / props.scale
  const worldY = (pos.y - props.offset.y) / props.scale
  const newOffset = {
    x: pos.x - worldX * newScale,
    y: pos.y - worldY * newScale,
  }

  emit('view-change', { scale: newScale, offset: newOffset })
}

function getTouchDistance(touches) {
  const dx = touches[0].clientX - touches[1].clientX
  const dy = touches[0].clientY - touches[1].clientY
  return Math.sqrt(dx * dx + dy * dy)
}

function getTouchCenter(touches, rect) {
  const x = (touches[0].clientX + touches[1].clientX) / 2 - rect.left
  const y = (touches[0].clientY + touches[1].clientY) / 2 - rect.top
  return { x, y }
}

function handleTouchStart(event) {
  if (event.touches.length === 2) {
    isPanning.value = false
    isPainting.value = false
    const rect = canvasRef.value.getBoundingClientRect()
    pinchStart.value = {
      distance: getTouchDistance(event.touches),
      center: getTouchCenter(event.touches, rect),
    }
    pinchStartScale.value = props.scale
    pinchStartOffset.value = { ...props.offset }
    return
  }

  if (event.touches.length === 1) {
    const touch = event.touches[0]
    const fakeEvent = { clientX: touch.clientX, clientY: touch.clientY, button: 0 }
    handleMouseDown(fakeEvent)
  }
}

function handleTouchMove(event) {
  if (event.touches.length === 2 && pinchStart.value) {
    event.preventDefault()
    const rect = canvasRef.value.getBoundingClientRect()
    const newDistance = getTouchDistance(event.touches)
    const newCenter = getTouchCenter(event.touches, rect)
    const ratio = newDistance / pinchStart.value.distance
    const newScale = Math.max(0.25, Math.min(pinchStartScale.value * ratio, 3))

    // 以双指中心为锚点缩放
    const worldX = (pinchStart.value.center.x - pinchStartOffset.value.x) / pinchStartScale.value
    const worldY = (pinchStart.value.center.y - pinchStartOffset.value.y) / pinchStartScale.value
    const newOffset = {
      x: newCenter.x - worldX * newScale,
      y: newCenter.y - worldY * newScale,
    }

    emit('view-change', { scale: newScale, offset: newOffset })
    return
  }

  if (event.touches.length === 1) {
    event.preventDefault()
    const touch = event.touches[0]
    const fakeEvent = { clientX: touch.clientX, clientY: touch.clientY }
    handleMouseMove(fakeEvent)
  }
}

function handleTouchEnd(event) {
  if (event.touches.length < 2) {
    pinchStart.value = null
  }
  handleMouseUp()
}

function inBounds(cell) {
  const [x, y] = cell
  return x >= 0 && x < props.map.width && y >= 0 && y < props.map.height
}
</script>

<style scoped>
/* 撞障碍抖动：机器人 mode 切到 blocked 时整块地图快速左右晃动，
   动画只操作 transform，不触发重排，性能开销可忽略 */
.canvas-shake {
  animation: canvas-shake 0.36s ease-in-out;
}

@keyframes canvas-shake {
  0%, 100% { transform: translateX(0); }
  15% { transform: translateX(-6px); }
  30% { transform: translateX(6px); }
  45% { transform: translateX(-4px); }
  60% { transform: translateX(4px); }
  75% { transform: translateX(-2px); }
  90% { transform: translateX(2px); }
}
</style>
