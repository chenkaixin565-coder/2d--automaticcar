<template>
  <div class="flex flex-col h-screen overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
    <!-- 顶部栏 -->
    <header class="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 z-20 shrink-0">
      <div class="flex items-center gap-2">
        <h1 class="text-base md:text-lg font-semibold truncate">智能巡检机器人二维仿真系统</h1>
        <span class="hidden sm:inline px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">V1.0</span>
        <span class="px-2 py-0.5 text-xs rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300">离线仿真</span>
      </div>
      <ThemeToggle :is-dark="isDark" @toggle="toggleTheme" />
    </header>

    <!-- 状态横幅 -->
    <div class="shrink-0 px-4 py-1 text-[10px] md:text-xs text-center bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-b border-blue-100 dark:border-blue-900/40">
      仿真模式（本地）：所有逻辑运行在浏览器中，无外部网络请求
    </div>

    <!-- 主体布局 -->
    <main class="flex-1 relative flex flex-col md:flex-row overflow-hidden">
      <!-- 地图区域 -->
      <div
        ref="mapContainerRef"
        class="flex-1 relative min-h-0 p-2 md:p-3"
      >
        <MapCanvas
          :map="map"
          :robot="robot"
          :visited-trail="visitedTrail"
          :playback-snapshot="playbackSnapshot"
          :scale="scale"
          :offset="offset"
          :edit-mode="editMode"
          :is-dark="isDark"
          @view-change="onViewChange"
          @edit-obstacle="onEditObstacle"
          @set-goal="onSetGoal"
          @set-start="onSetStart"
          @set-charge="onSetCharge"
          @hover="hoverCell = $event"
        />

        <!-- 地图缩放按钮 -->
        <div class="absolute bottom-3 left-3 flex flex-col gap-1.5 z-20">
          <button
            type="button"
            class="map-tool-btn"
            aria-label="放大"
            @click="zoomIn"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14" /></svg>
          </button>
          <button
            type="button"
            class="map-tool-btn"
            aria-label="缩小"
            @click="zoomOut"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /></svg>
          </button>
          <button
            type="button"
            class="map-tool-btn"
            aria-label="适配屏幕"
            @click="fitMap"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8V4h4M4 16v4h4M20 8V4h-4M20 16v4h-4" /></svg>
          </button>
        </div>

        <!-- 移动端抽屉开关（旧入口，保留作为详情抽屉触发） -->
        <button
          type="button"
          class="md:hidden absolute top-3 right-3 z-30 px-2.5 py-1.5 rounded-lg bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-xs shadow-sm"
          @click="drawerOpen = !drawerOpen"
        >
          {{ drawerOpen ? '收起' : '详情' }}
        </button>
      </div>

      <!-- 桌面端右侧面板 -->
      <aside class="hidden md:flex w-[400px] flex-col gap-3 p-3 border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 overflow-y-auto">
        <ControlPanel
          :robot="robot"
          :patrol-status="patrolStatus"
          :edit-mode="editMode"
          :map-goals="map.goals"
          @move="onMove"
          @reset="onReset"
          @start-patrol="onStartPatrol"
          @stop-patrol="onStopPatrol"
          @set-edit-mode="editMode = $event"
          @clear-goals="onClearGoals"
          @remove-goal="onRemoveGoal"
        />
        <Joystick class="hidden" @move="onMove" />
        <StatusDashboard :robot="robot" :temperature-history="temperatureHistory" />
        <PlaybackBar
          :snapshots="snapshots"
          :current-index="playbackIndex"
          :is-playing="playbackPlaying"
          @seek="playbackIndex = $event"
          @play="startPlayback"
          @pause="stopPlayback"
        />
        <AlertList :anomalies="anomalies" @clear="onClearAlerts" @export="onExportAlerts" />
      </aside>

      <!-- 移动端底部快捷控制条 -->
      <MobileControls
        class="md:hidden shrink-0"
        :robot="robot"
        :patrol-status="patrolStatus"
        :edit-mode="editMode"
        :detail-open="drawerOpen"
        @move="onMove"
        @reset="onReset"
        @start-patrol="onStartPatrol"
        @stop-patrol="onStopPatrol"
        @set-edit-mode="editMode = $event"
        @fit-map="fitMap"
        @toggle-detail="drawerOpen = !drawerOpen"
      />

      <!-- 移动端详情抽屉 -->
      <div
        v-show="drawerOpen"
        class="md:hidden absolute bottom-[11.5rem] left-2 right-2 z-40 max-h-[55vh] overflow-y-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl"
      >
        <div class="w-10 h-1.5 mx-auto my-2 rounded-full bg-gray-300 dark:bg-gray-700" />
        <div class="flex flex-col gap-3 p-3 pb-6">
          <StatusDashboard :robot="robot" :temperature-history="temperatureHistory" />
          <PlaybackBar
            :snapshots="snapshots"
            :current-index="playbackIndex"
            :is-playing="playbackPlaying"
            @seek="playbackIndex = $event"
            @play="startPlayback"
            @pause="stopPlayback"
          />
          <AlertList :anomalies="anomalies" @clear="onClearAlerts" @export="onExportAlerts" />
        </div>
      </div>
    </main>

    <!-- 新告警 Toast -->
    <div class="fixed top-14 right-3 z-50 flex flex-col gap-2 pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto max-w-xs px-4 py-3 rounded-lg shadow-lg border-l-4 text-sm bg-white dark:bg-gray-900"
          :class="toastClass(toast.type)"
        >
          <div class="font-medium">{{ toast.title }}</div>
          <div class="text-gray-600 dark:text-gray-300">{{ toast.message }}</div>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：应用主布局与业务编排
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 负责组装地图画布、控制面板、状态仪表盘、告警列表与回放组件，
 * 并通过 RobotService 与本地仿真器交互。
 */

import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { SimulatedService } from './services/index.js'
import ThemeToggle from './components/ThemeToggle.vue'
import MapCanvas from './components/MapCanvas.vue'
import ControlPanel from './components/ControlPanel.vue'
import Joystick from './components/Joystick.vue'
import StatusDashboard from './components/StatusDashboard.vue'
import AlertList from './components/AlertList.vue'
import PlaybackBar from './components/PlaybackBar.vue'
import MobileControls from './components/MobileControls.vue'

const SETTINGS_KEY = 'irm_settings_v1'

// 初始化数据服务层
const service = new SimulatedService()
const map = reactive(service.getMap())
service.updateMap(map)

// 视图状态
const robot = ref({
  x: map.start[0],
  y: map.start[1],
  theta: 0,
  battery: 100,
  speed: 0,
  mode: 'manual',
  path: [],
  sensors: { front: null, left: null, right: null, temperature: 35 },
})
const visitedTrail = ref([])
const patrolStatus = ref(service.getPatrolStatus())
const anomalies = ref(service.getAnomalies())
const temperatureHistory = ref([])
const snapshots = ref([])
const hoverCell = ref(null)

// 地图视图
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
const editMode = ref('pan')
const mapContainerRef = ref(null)

// 主题
const isDark = ref(false)

// 移动端抽屉
const drawerOpen = ref(false)

// 回放
const playbackIndex = ref(0)
const playbackPlaying = ref(false)
let playbackTimer = null
const playbackSnapshot = computed(() => {
  if (snapshots.value.length === 0) return null
  return snapshots.value[playbackIndex.value] || snapshots.value[snapshots.value.length - 1]
})

// Toast
const toasts = ref([])
let toastId = 0

let unsubscribeState = null
let unsubscribeEvent = null

onMounted(() => {
  loadTheme()
  fitMap()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('resize', handleResize)
  window.addEventListener('orientationchange', handleResize)

  unsubscribeState = service.onState((frame) => {
    robot.value = frame.data
    visitedTrail.value = service.getVisitedTrail()
    patrolStatus.value = service.getPatrolStatus()
    temperatureHistory.value.push(frame.data.sensors.temperature)
    if (temperatureHistory.value.length > 300) {
      temperatureHistory.value.shift()
    }
  })

  unsubscribeEvent = service.onEvent((frame) => {
    if (frame.type === 'anomaly') {
      anomalies.value = service.getAnomalies()
      addToast(frame.data.type, frame.data.message)
    } else if (frame.type === 'notice') {
      if (frame.data.message && frame.data.message.includes('已完成')) {
        snapshots.value = service.getSnapshots()
      }
      addToast('notice', frame.data.message)
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('orientationchange', handleResize)
  if (unsubscribeState) unsubscribeState()
  if (unsubscribeEvent) unsubscribeEvent()
  stopPlayback()
})

// --------------------------------------------------------------------------
// 主题与持久化
// --------------------------------------------------------------------------

function loadTheme() {
  try {
    const settings = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}')
    isDark.value = settings.dark || false
  } catch {
    isDark.value = false
  }
  applyTheme()
}

function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme()
  try {
    const settings = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}')
    settings.dark = isDark.value
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
  } catch (error) {
    console.warn('主题设置保存失败：', error)
  }
}

function applyTheme() {
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

// --------------------------------------------------------------------------
// 视图控制
// --------------------------------------------------------------------------

const CELL_PIXELS = 40

function getContainerRect() {
  const container = mapContainerRef.value
  if (!container) return null
  return container.getBoundingClientRect()
}

function fitMap() {
  const rect = getContainerRect()
  if (!rect) return
  const mapW = map.width * CELL_PIXELS
  const mapH = map.height * CELL_PIXELS
  const padding = 24
  const scaleX = (rect.width - padding) / mapW
  const scaleY = (rect.height - padding) / mapH
  const newScale = Math.max(0.25, Math.min(scaleX, scaleY, 2.5))
  offset.value = {
    x: (rect.width - mapW * newScale) / 2,
    y: (rect.height - mapH * newScale) / 2,
  }
  scale.value = newScale
}

function handleResize() {
  // 延迟执行，等待旋转/Resize 完成
  setTimeout(() => fitMap(), 100)
}

function zoomIn() {
  const rect = getContainerRect()
  if (!rect) return
  const cx = rect.width / 2
  const cy = rect.height / 2
  applyZoom(cx, cy, scale.value * 1.25)
}

function zoomOut() {
  const rect = getContainerRect()
  if (!rect) return
  const cx = rect.width / 2
  const cy = rect.height / 2
  applyZoom(cx, cy, scale.value / 1.25)
}

function applyZoom(cx, cy, newScale) {
  const clamped = Math.max(0.25, Math.min(newScale, 3))
  const worldX = (cx - offset.value.x) / scale.value
  const worldY = (cy - offset.value.y) / scale.value
  offset.value = {
    x: cx - worldX * clamped,
    y: cy - worldY * clamped,
  }
  scale.value = clamped
}

function onViewChange(payload) {
  scale.value = payload.scale
  offset.value = payload.offset
}

// --------------------------------------------------------------------------
// 机器人控制
// --------------------------------------------------------------------------

function onMove(payload) {
  service.move(payload.dx, payload.dy)
}

function onReset() {
  service.reset()
  snapshots.value = []
  stopPlayback()
}

function handleKeyDown(event) {
  const keyMap = {
    ArrowUp: { dx: 0, dy: -1 },
    ArrowDown: { dx: 0, dy: 1 },
    ArrowLeft: { dx: -1, dy: 0 },
    ArrowRight: { dx: 1, dy: 0 },
    w: { dx: 0, dy: -1 },
    s: { dx: 0, dy: 1 },
    a: { dx: -1, dy: 0 },
    d: { dx: 1, dy: 0 },
  }
  const move = keyMap[event.key]
  if (move) {
    event.preventDefault()
    service.move(move.dx, move.dy)
  }
}

// --------------------------------------------------------------------------
// 巡检任务
// --------------------------------------------------------------------------

function onStartPatrol() {
  service.startPatrol(map.goals)
}

function onStopPatrol() {
  service.stopPatrol()
}

// --------------------------------------------------------------------------
// 地图编辑
// --------------------------------------------------------------------------

function onEditObstacle({ x, y, value }) {
  if (x < 0 || x >= map.width || y < 0 || y >= map.height) return
  map.grid[y][x] = value
  service.updateMap(map)
}

function onSetGoal({ x, y }) {
  if (map.grid[y][x] === 1) return
  const goals = map.goals
  const index = goals.findIndex((g) => g[0] === x && g[1] === y)
  if (index >= 0) {
    goals.splice(index, 1)
  } else {
    goals.push([x, y])
  }
  service.updateMap(map)
}

function onSetStart({ x, y }) {
  if (map.grid[y][x] === 1) return
  map.start = [x, y]
  service.updateMap(map)
}

function onSetCharge({ x, y }) {
  if (map.grid[y][x] === 1) return
  map.charge_point = [x, y]
  service.updateMap(map)
}

function onClearGoals() {
  map.goals = []
  service.updateMap(map)
}

function onRemoveGoal(index) {
  map.goals.splice(index, 1)
  service.updateMap(map)
}

// --------------------------------------------------------------------------
// 告警与回放
// --------------------------------------------------------------------------

function onClearAlerts() {
  service.clearAnomalies()
  anomalies.value = []
}

function onExportAlerts() {
  const data = JSON.stringify(service.getAnomalies(), null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `anomalies_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function startPlayback() {
  if (snapshots.value.length === 0) return
  playbackPlaying.value = true
  if (playbackTimer) clearInterval(playbackTimer)
  playbackTimer = setInterval(() => {
    if (playbackIndex.value < snapshots.value.length - 1) {
      playbackIndex.value += 1
    } else {
      stopPlayback()
    }
  }, 100)
}

function stopPlayback() {
  playbackPlaying.value = false
  if (playbackTimer) {
    clearInterval(playbackTimer)
    playbackTimer = null
  }
}

// --------------------------------------------------------------------------
// Toast
// --------------------------------------------------------------------------

const toastTitles = {
  low_battery: '低电量告警',
  obstacle: '障碍物告警',
  sensor_fault: '传感器异常',
  overheat: '过热告警',
  notice: '系统提示',
}

function addToast(type, message) {
  const id = toastId++
  toasts.value.push({ id, type, title: toastTitles[type] || type, message })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, 4000)
}

function toastClass(type) {
  const classes = {
    low_battery: 'border-orange-500',
    obstacle: 'border-red-500',
    sensor_fault: 'border-purple-500',
    overheat: 'border-yellow-500',
    notice: 'border-blue-500',
  }
  return classes[type] || 'border-gray-500'
}
</script>

<style>
.map-tool-btn {
  @apply flex items-center justify-center w-8 h-8 rounded-lg bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 active:bg-gray-100 dark:active:bg-gray-600 transition-colors;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
