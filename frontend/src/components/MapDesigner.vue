<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[80] flex flex-col bg-gray-100 dark:bg-gray-950">
      <!-- 顶部工具条 -->
      <header class="shrink-0 flex flex-wrap items-center gap-2 px-3 py-2 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
        <span class="text-sm font-semibold mr-1">地图设计器</span>
        <input
          v-model="name"
          maxlength="40"
          placeholder="地图名称"
          class="px-2 py-1 text-sm rounded border border-gray-200 dark:border-gray-700 bg-transparent w-40"
        >

        <span class="mx-1 h-5 w-px bg-gray-200 dark:bg-gray-700" />

        <label class="text-xs text-gray-500">宽
          <input v-model.number="draftWidth" type="number" min="10" max="60" class="ml-1 w-16 px-1.5 py-1 text-sm rounded border border-gray-200 dark:border-gray-700 bg-transparent">
        </label>
        <label class="text-xs text-gray-500">高
          <input v-model.number="draftHeight" type="number" min="10" max="60" class="ml-1 w-16 px-1.5 py-1 text-sm rounded border border-gray-200 dark:border-gray-700 bg-transparent">
        </label>
        <button type="button" class="tool-btn" @click="applySize">应用尺寸</button>

        <span class="mx-1 h-5 w-px bg-gray-200 dark:bg-gray-700" />

        <button
          v-for="tool in tools"
          :key="tool.key"
          type="button"
          class="tool-btn"
          :class="tool.key === currentTool ? 'tool-btn-active' : ''"
          :title="tool.hint"
          @click="currentTool = tool.key"
        >
          {{ tool.label }}
        </button>

        <span class="mx-1 h-5 w-px bg-gray-200 dark:bg-gray-700" />

        <button type="button" class="tool-btn" @click="fitView">适配</button>
        <button type="button" class="tool-btn" @click="zoomBy(1.2)">＋</button>
        <button type="button" class="tool-btn" @click="zoomBy(1 / 1.2)">－</button>
        <button type="button" class="tool-btn" @click="clearAll">清空</button>

        <div class="flex-1" />
        <button type="button" class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800" @click="$emit('close')">返回仿真</button>
        <button type="button" class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800" @click="exportJson">导出 JSON</button>
        <button type="button" class="px-3 py-1.5 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700" @click="save">保存并载入</button>
      </header>

      <div ref="wrapRef" class="relative flex-1 overflow-hidden">
        <canvas
          ref="canvasRef"
          class="absolute inset-0 w-full h-full cursor-crosshair touch-none"
          @pointerdown="onDown"
          @pointermove="onMove"
          @pointerup="onUp"
          @pointerleave="onUp"
          @wheel.prevent="onWheel"
          @contextmenu.prevent
        />
        <div class="absolute bottom-3 left-3 px-2 py-1 text-xs rounded bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 pointer-events-none">
          {{ toolHint }} · 缩放 {{ (scale * 100).toFixed(0) }}%
        </div>
        <div class="absolute top-3 right-3 px-2.5 py-2 text-[11px] leading-5 rounded bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 pointer-events-none space-y-0.5">
          <div class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded-sm bg-slate-600" />普通障碍（机器人可清）</div>
          <div class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded-sm bg-slate-900" />固定屏障（不可穿越）</div>
          <div class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded-full bg-emerald-500" />起点</div>
          <div class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded-full bg-orange-500" />充电点</div>
          <div class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded-full bg-blue-500" />巡检点（点击可加/删）</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：地图设计器（V2.1）
 * 作者：智能巡检机器人二维仿真系统 V2.1 前端开发组
 * 日期：2026-10-27
 * 版本：V2.1
 *
 * 全屏画布，专门用来画地图：普通障碍、固定屏障、起点、充电点、巡检点。
 * 画布尺寸随地图大小自适应，可缩放/平移；最外环固定为边界墙（不可绘制）。
 * 保存后直接载入仿真，也可以导出成 JSON 传给别的设备。
 */

import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { enforceBorder, isBoundaryCell } from '../utils/mapBoundary.js'
import { exportMap } from '../utils/mapIO.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialMap: { type: Object, default: null },
})

const emit = defineEmits(['close', 'save'])

const CELL = 32
const MIN_SIZE = 10
const MAX_SIZE = 60

const tools = [
  { key: 'obstacle', label: '障碍', hint: '按住左键涂普通障碍（机器人可清除）' },
  { key: 'barrier', label: '屏障', hint: '按住左键涂固定屏障（不可穿越、机器人清不掉）' },
  { key: 'erase', label: '擦除', hint: '按住左键擦掉障碍/屏障（编辑不耗电）' },
  { key: 'start', label: '起点', hint: '点击设置机器人起点' },
  { key: 'charge', label: '充电点', hint: '点击设置充电点' },
  { key: 'goal', label: '巡检点', hint: '点击添加/移除巡检点' },
]

const canvasRef = ref(null)
const wrapRef = ref(null)
const name = ref('新地图')
const draftWidth = ref(30)
const draftHeight = ref(20)
const currentTool = ref('obstacle')
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
const hover = ref(null)

let map = ref(null)
let painting = false
let lastKey = ''
let dragging = false
let dragStart = null
let dragOrigin = null

const toolHint = computed(() => tools.find((t) => t.key === currentTool.value)?.hint || '')

function createBlank(width, height) {
  const grid = Array.from({ length: height }, () => Array(width).fill(0))
  enforceBorder(grid, width, height)
  return {
    width,
    height,
    grid,
    start: [1, 1],
    goals: [],
    charge_point: [width - 2, height - 2],
  }
}

function loadInitial() {
  const src = props.initialMap
  if (src && src.grid) {
    map.value = JSON.parse(JSON.stringify(src))
    draftWidth.value = src.width
    draftHeight.value = src.height
  } else {
    map.value = createBlank(30, 20)
    draftWidth.value = 30
    draftHeight.value = 20
  }
  nextTick(() => {
    fitView()
    render()
  })
}

/** 尺寸变化：保留重叠区域的绘制内容，越界的关键点夹回内部。 */
function applySize() {
  const w = Math.max(MIN_SIZE, Math.min(MAX_SIZE, Math.round(Number(draftWidth.value) || 30)))
  const h = Math.max(MIN_SIZE, Math.min(MAX_SIZE, Math.round(Number(draftHeight.value) || 20)))
  draftWidth.value = w
  draftHeight.value = h
  const old = map.value
  const grid = Array.from({ length: h }, () => Array(w).fill(0))
  for (let y = 0; y < Math.min(h, old.height); y += 1) {
    for (let x = 0; x < Math.min(w, old.width); x += 1) {
      grid[y][x] = old.grid[y][x]
    }
  }
  enforceBorder(grid, w, h)
  const clampPoint = (p) => [Math.min(w - 2, Math.max(1, p[0])), Math.min(h - 2, Math.max(1, p[1]))]
  map.value = {
    width: w,
    height: h,
    grid,
    start: clampPoint(old.start),
    charge_point: clampPoint(old.charge_point),
    goals: old.goals.map(clampPoint).filter((g, i, arr) => arr.findIndex((q) => q[0] === g[0] && q[1] === g[1]) === i),
  }
  fitView()
  render()
}

function clearAll() {
  if (!window.confirm('清空画布上的所有障碍、屏障、巡检点？')) return
  map.value = createBlank(map.value.width, map.value.height)
  render()
}

/** 让整张地图刚好铺满可视区域。 */
function fitView() {
  const wrap = wrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  const s = Math.min((rect.width - 48) / (map.value.width * CELL), (rect.height - 48) / (map.value.height * CELL))
  scale.value = Math.max(0.2, Math.min(s, 2.5))
  offset.value = {
    x: (rect.width - map.value.width * CELL * scale.value) / 2,
    y: (rect.height - map.value.height * CELL * scale.value) / 2,
  }
}

function zoomBy(factor) {
  const wrap = wrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  const cx = rect.width / 2
  const cy = rect.height / 2
  const next = Math.max(0.2, Math.min(scale.value * factor, 4))
  const wx = (cx - offset.value.x) / scale.value
  const wy = (cy - offset.value.y) / scale.value
  offset.value = { x: cx - wx * next, y: cy - wy * next }
  scale.value = next
  render()
}

function onWheel(event) {
  const wrap = wrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  const px = event.clientX - rect.left
  const py = event.clientY - rect.top
  const factor = event.deltaY < 0 ? 1.1 : 0.9
  const next = Math.max(0.2, Math.min(scale.value * factor, 4))
  const wx = (px - offset.value.x) / scale.value
  const wy = (py - offset.value.y) / scale.value
  offset.value = { x: px - wx * next, y: py - wy * next }
  scale.value = next
  render()
}

function toCell(event) {
  const wrap = wrapRef.value
  const rect = wrap.getBoundingClientRect()
  const x = Math.floor((event.clientX - rect.left - offset.value.x) / scale.value / CELL)
  const y = Math.floor((event.clientY - rect.top - offset.value.y) / scale.value / CELL)
  return [x, y]
}

function inBounds([x, y]) {
  return x >= 0 && x < map.value.width && y >= 0 && y < map.value.height
}

function onDown(event) {
  if (event.button === 2 || event.button === 1) {
    dragging = true
    dragStart = { x: event.clientX, y: event.clientY }
    dragOrigin = { ...offset.value }
    return
  }
  if (event.button !== 0) return
  painting = true
  lastKey = ''
  paint(toCell(event))
}

function onMove(event) {
  const cell = toCell(event)
  hover.value = inBounds(cell) ? cell : null
  if (dragging) {
    offset.value = {
      x: dragOrigin.x + (event.clientX - dragStart.x),
      y: dragOrigin.y + (event.clientY - dragStart.y),
    }
    render()
    return
  }
  if (painting) paint(cell)
  else render()
}

function onUp() {
  painting = false
  dragging = false
  lastKey = ''
}

/** 按当前工具处理一个格子。 */
function paint(cell) {
  if (!inBounds(cell)) return
  const [x, y] = cell
  const key = `${x},${y}`
  if (key === lastKey) return
  lastKey = key
  const m = map.value
  const boundary = isBoundaryCell(x, y, m.width, m.height)

  if (currentTool.value === 'start') {
    if (!boundary && m.grid[y][x] === 0) m.start = [x, y]
  } else if (currentTool.value === 'charge') {
    if (!boundary && m.grid[y][x] === 0) m.charge_point = [x, y]
  } else if (currentTool.value === 'goal') {
    if (boundary || m.grid[y][x] !== 0) return
    const idx = m.goals.findIndex((g) => g[0] === x && g[1] === y)
    if (idx >= 0) m.goals.splice(idx, 1)
    else m.goals.push([x, y])
  } else {
    if (boundary) return // 最外环固定为边界，不可绘制/擦除
    const isKey =
      (m.start[0] === x && m.start[1] === y) ||
      (m.charge_point[0] === x && m.charge_point[1] === y) ||
      m.goals.some((g) => g[0] === x && g[1] === y)
    if (currentTool.value === 'erase') {
      if (isKey) return
      m.grid[y][x] = 0
    } else if (currentTool.value === 'obstacle') {
      if (isKey) return
      m.grid[y][x] = 1
    } else if (currentTool.value === 'barrier') {
      if (isKey) return
      m.grid[y][x] = 2
    }
  }
  render()
}

function render() {
  const canvas = canvasRef.value
  const wrap = wrapRef.value
  if (!canvas || !wrap || !map.value) return
  const rect = wrap.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.floor(rect.width * dpr))
  canvas.height = Math.max(1, Math.floor(rect.height * dpr))
  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, rect.width, rect.height)

  const m = map.value
  const dark = document.documentElement.classList.contains('dark')
  ctx.save()
  ctx.translate(offset.value.x, offset.value.y)
  ctx.scale(scale.value, scale.value)

  // 底板
  ctx.fillStyle = dark ? '#0f172a' : '#ffffff'
  ctx.fillRect(0, 0, m.width * CELL, m.height * CELL)

  // 网格线
  ctx.strokeStyle = dark ? '#1f2937' : '#e5e7eb'
  ctx.lineWidth = 1 / scale.value
  ctx.beginPath()
  for (let x = 0; x <= m.width; x += 1) {
    ctx.moveTo(x * CELL, 0)
    ctx.lineTo(x * CELL, m.height * CELL)
  }
  for (let y = 0; y <= m.height; y += 1) {
    ctx.moveTo(0, y * CELL)
    ctx.lineTo(m.width * CELL, y * CELL)
  }
  ctx.stroke()

  // 格子
  for (let y = 0; y < m.height; y += 1) {
    for (let x = 0; x < m.width; x += 1) {
      const v = m.grid[y][x]
      if (v === 0) continue
      if (v === 2) {
        ctx.fillStyle = dark ? '#020617' : '#0f172a'
        ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
        ctx.strokeStyle = dark ? '#334155' : '#475569'
        ctx.lineWidth = 2 / scale.value
        ctx.beginPath()
        ctx.moveTo(x * CELL + 4, y * CELL + CELL - 4)
        ctx.lineTo(x * CELL + CELL - 4, y * CELL + 4)
        ctx.stroke()
      } else {
        ctx.fillStyle = dark ? '#475569' : '#64748b'
        ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
      }
    }
  }

  // 关键点
  const dot = (p, color, label) => {
    const cx = (p[0] + 0.5) * CELL
    const cy = (p[1] + 0.5) * CELL
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy, CELL * 0.32, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#fff'
    ctx.font = `600 ${CELL * 0.36}px ui-sans-serif, system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, cx, cy)
  }
  dot(m.start, '#22c55e', 'S')
  dot(m.charge_point, '#f97316', 'C')
  m.goals.forEach((g, i) => dot(g, '#3b82f6', String(i + 1)))

  // 悬停高亮
  if (hover.value) {
    const [hx, hy] = hover.value
    ctx.strokeStyle = '#38bdf8'
    ctx.lineWidth = 2 / scale.value
    ctx.strokeRect(hx * CELL + 1, hy * CELL + 1, CELL - 2, CELL - 2)
  }

  ctx.restore()
}

function save() {
  const m = map.value
  // 外围必须闭合：最外环全部非空（enforceBorder 已保证）
  for (let x = 0; x < m.width; x += 1) {
    if (m.grid[0][x] === 0 || m.grid[m.height - 1][x] === 0) {
      window.alert('外围没有闭合：最外环必须是墙。请检查地图边缘。')
      return
    }
  }
  emit('save', { name: (name.value || '未命名地图').trim().slice(0, 40), map: JSON.parse(JSON.stringify(m)) })
}

function exportJson() {
  exportMap(map.value, `${(name.value || 'map').trim() || 'map'}.json`)
}

function onKeydown(event) {
  if (event.key === 'Escape' && props.visible) emit('close')
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      loadInitial()
      window.addEventListener('keydown', onKeydown)
    } else {
      window.removeEventListener('keydown', onKeydown)
    }
  }
)

onMounted(() => {
  if (props.visible) loadInitial()
})

onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.tool-btn {
  @apply px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200;
}
.tool-btn-active {
  @apply border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300;
}
</style>
