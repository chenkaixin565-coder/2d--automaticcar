<template>
  <div class="relative w-full h-full rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
    <canvas
      ref="canvasRef"
      class="absolute inset-0 w-full h-full cursor-crosshair touch-none"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
      @wheel.prevent="handleWheel"
      @touchstart="handleTouchStart"
      @touchmove="handleTouchMove"
      @touchend="handleTouchEnd"
    />
    <div class="absolute top-3 left-3 px-2 py-1 text-xs rounded-md bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300">
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
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 使用原生 Canvas 绘制地图栅格、障碍物、机器人、路径与已访问轨迹，
 * 并支持滚轮缩放、拖拽平移、悬停高亮以及地图编辑。
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

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
})

const emit = defineEmits([
  'view-change',
  'edit-obstacle',
  'set-goal',
  'set-start',
  'set-charge',
  'hover',
])

const canvasRef = ref(null)
const isPanning = ref(false)
const isPainting = ref(false)
const paintValue = ref(0)
const lastPaintCell = ref(null)
const panStart = ref({ x: 0, y: 0 })
const viewOffsetStart = ref({ x: 0, y: 0 })
const pinchStart = ref(null)
const pinchStartScale = ref(1)
const pinchStartOffset = ref({ x: 0, y: 0 })

const editModeLabel = computed(() => {
  const labels = {
    pan: '平移模式（滚轮缩放 / 拖拽平移）',
    obstacle: '障碍编辑（左键拖动绘制 / 擦除）',
    goal: '设置巡检点（点击地图添加 / 移除）',
    start: '设置起点（点击地图）',
    charge: '设置充电点（点击地图）',
  }
  return labels[props.editMode] || labels.pan
})

onMounted(() => {
  render()
  window.addEventListener('resize', render)
})

onUnmounted(() => {
  window.removeEventListener('resize', render)
})

watch(
  () => [props.map, props.robot, props.playbackSnapshot, props.scale, props.offset, props.editMode, props.isDark],
  () => render(),
  { deep: true }
)

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

  const snapshot = props.playbackSnapshot
  if (snapshot) {
    drawTrail(ctx, snapshot.visitedTrail || [])
    drawPath(ctx, snapshot.path || [])
    drawRobot(ctx, snapshot, true)
  } else {
    drawTrail(ctx, props.visitedTrail)
    drawPath(ctx, props.robot.path || [])
    drawRobot(ctx, props.robot, false)
  }

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
 */
function drawSpecialCells(ctx) {
  const { start, charge_point: chargePoint, goals } = props.map
  drawMarker(ctx, start, '#22c55e', 'S')
  drawMarker(ctx, chargePoint, '#f97316', 'C')
  if (goals) {
    goals.forEach((goal, index) => {
      drawMarker(ctx, goal, '#3b82f6', String(index + 1))
    })
  }
}

/**
 * 绘制单个标记点。
 */
function drawMarker(ctx, pos, color, label) {
  const cx = (pos[0] + 0.5) * CELL_PIXELS
  const cy = (pos[1] + 0.5) * CELL_PIXELS
  const radius = CELL_PIXELS * 0.35

  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(cx, cy, radius, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = '#ffffff'
  ctx.font = `${CELL_PIXELS * 0.35}px ui-sans-serif, system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, cx, cy)
}

/**
 * 绘制障碍物。
 */
function drawObstacles(ctx) {
  const grid = props.map.grid
  ctx.fillStyle = props.isDark ? '#4b5563' : '#374151'
  for (let y = 0; y < props.map.height; y += 1) {
    for (let x = 0; x < props.map.width; x += 1) {
      if (grid[y][x] === 1) {
        ctx.fillRect(x * CELL_PIXELS, y * CELL_PIXELS, CELL_PIXELS, CELL_PIXELS)
      }
    }
  }
}

/**
 * 绘制已访问轨迹。
 */
function drawTrail(ctx, trail) {
  if (!trail || trail.length < 2) return
  ctx.strokeStyle = props.isDark ? '#6b7280' : '#9ca3af'
  ctx.lineWidth = 2 / props.scale
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
 * 绘制机器人（圆形机身 + 朝向箭头）。
 */
function drawRobot(ctx, state, isGhost) {
  const cx = (state.x + 0.5) * CELL_PIXELS
  const cy = (state.y + 0.5) * CELL_PIXELS
  const radius = CELL_PIXELS * 0.35
  const theta = state.theta || 0

  ctx.save()
  ctx.translate(cx, cy)

  // 机身
  ctx.fillStyle = isGhost ? 'rgba(59, 130, 246, 0.4)' : '#2563eb'
  ctx.beginPath()
  ctx.arc(0, 0, radius, 0, Math.PI * 2)
  ctx.fill()

  // 朝向箭头
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = 3 / props.scale
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo(Math.cos(theta) * radius, Math.sin(theta) * radius)
  ctx.stroke()

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

function handleMouseDown(event) {
  if (event.button !== 0) return
  const pos = getEventPos(event)
  if (props.editMode === 'pan') {
    isPanning.value = true
    panStart.value = pos
    viewOffsetStart.value = { ...props.offset }
  } else if (props.editMode === 'obstacle') {
    const cell = screenToCell(pos.x, pos.y)
    if (inBounds(cell)) {
      isPainting.value = true
      paintValue.value = props.map.grid[cell[1]][cell[0]] === 1 ? 0 : 1
      lastPaintCell.value = `${cell[0]},${cell[1]}`
      emit('edit-obstacle', { x: cell[0], y: cell[1], value: paintValue.value })
    }
  } else if (props.editMode === 'goal') {
    const cell = screenToCell(pos.x, pos.y)
    if (inBounds(cell)) {
      emit('set-goal', { x: cell[0], y: cell[1] })
    }
  } else if (props.editMode === 'start') {
    const cell = screenToCell(pos.x, pos.y)
    if (inBounds(cell) && props.map.grid[cell[1]][cell[0]] === 0) {
      emit('set-start', { x: cell[0], y: cell[1] })
    }
  } else if (props.editMode === 'charge') {
    const cell = screenToCell(pos.x, pos.y)
    if (inBounds(cell) && props.map.grid[cell[1]][cell[0]] === 0) {
      emit('set-charge', { x: cell[0], y: cell[1] })
    }
  }
}

function handleMouseMove(event) {
  const pos = getEventPos(event)
  const cell = screenToCell(pos.x, pos.y)
  if (inBounds(cell)) {
    hoverCell.value = cell
    emit('hover', { x: cell[0], y: cell[1] })
  } else {
    hoverCell.value = null
  }

  if (isPanning.value) {
    const dx = pos.x - panStart.value.x
    const dy = pos.y - panStart.value.y
    emit('view-change', {
      scale: props.scale,
      offset: {
        x: viewOffsetStart.value.x + dx,
        y: viewOffsetStart.value.y + dy,
      },
    })
  } else if (isPainting.value && props.editMode === 'obstacle') {
    const key = `${cell[0]},${cell[1]}`
    if (inBounds(cell) && key !== lastPaintCell.value) {
      lastPaintCell.value = key
      emit('edit-obstacle', { x: cell[0], y: cell[1], value: paintValue.value })
    }
  }
}

function handleMouseUp() {
  isPanning.value = false
  isPainting.value = false
  lastPaintCell.value = null
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
