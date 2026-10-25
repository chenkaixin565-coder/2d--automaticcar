<template>
  <div class="flex flex-col h-screen overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
    <!-- 顶部栏 -->
    <header class="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 z-20 shrink-0">
      <div class="flex items-center gap-2">
        <h1 class="text-base md:text-lg font-semibold truncate">智能巡检机器人二维仿真系统</h1>
        <span class="hidden sm:inline px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">V1.2</span>
        <span class="px-2 py-0.5 text-xs rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300">{{ dataModeLabel }}</span>
      </div>
      <ThemeToggle :is-dark="isDark" @toggle="toggleTheme" />
    </header>

    <!-- 状态横幅 -->
    <div
      class="shrink-0 px-4 py-1 text-[10px] md:text-xs text-center border-b bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-100 dark:border-blue-900/40"
    >
      {{ bannerText }}
    </div>

    <!-- 新告警 Toast：移动端为文档流内布局（夹在横幅与地图之间，绝不遮挡地图）；
         桌面端悬浮右上角（仪表盘常规模式） -->
    <div
      class="shrink-0 px-2 pt-1.5 flex flex-col gap-1.5 pointer-events-none md:fixed md:top-14 md:right-3 md:z-50 md:px-0 md:pt-0"
    >
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto max-w-full md:max-w-xs px-3 md:px-4 py-2 md:py-3 rounded-lg shadow-lg border-l-4 text-xs md:text-sm bg-white dark:bg-gray-900"
          :class="toastClass(toast.type)"
        >
          <div class="font-medium">{{ toast.title }}</div>
          <div class="text-gray-600 dark:text-gray-300">{{ toast.message }}</div>
        </div>
      </TransitionGroup>
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
          :robot-avatar="robotAvatar"
          :route-plan="routePlan"
          :show-goal-numbers="showGoalNumbers"
          :patrol-blocked-cell="patrolBlockedCell"
          @view-change="onViewChange"
          @edit-obstacle="onEditObstacle"
          @clear-obstacle="onClearObstacle"
          @set-goal="onSetGoal"
          @set-start="onSetStart"
          @set-charge="onSetCharge"
          @hover="hoverCell = $event"
        />

        <!-- 悬停格详情徽标（详情表面化：坐标与格子类型直接显示在地图上） -->
        <div
          v-if="hoverCell"
          class="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 px-2.5 py-1 rounded-md bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300 shadow-sm pointer-events-none whitespace-nowrap"
        >
          [{{ hoverCell.x }}, {{ hoverCell.y }}] · {{ hoverCellType }}
        </div>

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
          :map-preset="mapPresetKey"
          :has-avatar="!!robotAvatar"
          :show-goal-numbers="showGoalNumbers"
          @move="onMove"
          @reset="onReset"
          @resolve-fault="onResolveFault"
          @select-preset="onSelectPreset"
          @export-map="onExportMap"
          @import-map="onImportMap"
          @import-error="onImportError"
          @avatar-change="onAvatarChange"
          @avatar-error="onAvatarError"
          @start-patrol="onStartPatrol"
          @stop-patrol="onStopPatrol"
          @set-edit-mode="editMode = $event"
          @clear-goals="onClearGoals"
          @remove-goal="onRemoveGoal"
          @toggle-goal-numbers="onToggleGoalNumbers"
          @carry-home="onCarryHomePrompt"
        />
        <RoutePlanPanel
          :plan="routePlan"
          :map-goals="map.goals"
          :patrol-status="patrolStatus"
          :robot="robot"
          @plan-route="onPlanRoute"
          @execute-plan-clear="onExecutePlanClear"
          @cancel-plan="onCancelPlan"
          @start-patrol="onStartPatrol"
          @clear-blocked="onClearBlockedObstacle"
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
        @resolve-fault="onResolveFault"
        @start-patrol="onStartPatrol"
        @stop-patrol="onStopPatrol"
        @set-edit-mode="editMode = $event"
        @fit-map="fitMap"
        @toggle-detail="drawerOpen = !drawerOpen"
        @open-plan="drawerOpen = true"
      />

      <!-- 移动端详情抽屉 -->
      <div
        v-show="drawerOpen"
        class="md:hidden absolute bottom-[11.5rem] left-2 right-2 z-40 max-h-[55vh] overflow-y-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl"
      >
        <div class="w-10 h-1.5 mx-auto my-2 rounded-full bg-gray-300 dark:bg-gray-700" />
        <div class="flex flex-col gap-3 p-3 pb-6">
          <RoutePlanPanel
            :plan="routePlan"
            :map-goals="map.goals"
            :patrol-status="patrolStatus"
            :robot="robot"
            @plan-route="onPlanRoute"
            @execute-plan-clear="onExecutePlanClear"
            @cancel-plan="onCancelPlan"
            @start-patrol="onStartPatrol"
            @clear-blocked="onClearBlockedObstacle"
          />
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

    <!-- 空电搬回确认弹窗（V1.2） -->
    <EmptyBatteryModal
      :visible="showEmptyModal"
      @confirm="onCarryHomeConfirm"
      @dismiss="showEmptyModal = false"
    />
  </div>
</template>

<script setup>
/**
 * 组件功能：应用主布局与业务编排
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 负责组装地图画布、控制面板、状态仪表盘、告警列表与回放组件，
 * 并通过 RobotService 与本地仿真器交互。
 */

import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { createRobotService } from './services/index.js'
import { exportMap } from './utils/mapIO.js'
import { isBoundaryCell } from './utils/mapBoundary.js'
import { getAvatar, setAvatar, clearAvatar } from './utils/robotAvatar.js'
import ThemeToggle from './components/ThemeToggle.vue'
import MapCanvas from './components/MapCanvas.vue'
import ControlPanel from './components/ControlPanel.vue'
import Joystick from './components/Joystick.vue'
import StatusDashboard from './components/StatusDashboard.vue'
import AlertList from './components/AlertList.vue'
import PlaybackBar from './components/PlaybackBar.vue'
import MobileControls from './components/MobileControls.vue'
import RoutePlanPanel from './components/RoutePlanPanel.vue'
import EmptyBatteryModal from './components/EmptyBatteryModal.vue'

const SETTINGS_KEY = 'irm_settings_v1'

/** 目标点标号开关的持久化键名（V1.2：标号点地图 / 不标号点地图）。 */
const GOAL_NUMBERS_KEY = 'irm_goal_numbers_v1'

// 数据源展示标签：后端连接成功显示"后端服务"，否则"离线仿真"
const dataModeLabel = computed(() => (usingBackend.value ? '后端服务' : '离线仿真'))

const bannerText = computed(() => {
  if (usingBackend.value) {
    return backendConnected.value
      ? '已接入后端仿真服务（FastAPI）：数据来自服务器'
      : '正在连接后端仿真服务，连接失败时请检查后端地址'
  }
  return '仿真模式（本地）：所有逻辑运行在浏览器中，无外部网络请求'
})

// 后端连接状态（仅 RemoteService 相关）
const backendConnected = ref(false)

// 初始化数据服务层：默认离线仿真；URL 带 ?backend= 时自动接入 FastAPI 后端。
// 界面组件无需感知数据来源，切换对组件透明（设计红线）。
const service = createRobotService()
const usingBackend = ref(!!service.isRemote)
const map = reactive(service.getMap())

// 当前内置地图预设标识（自定义地图为 null），用于控制台高亮
const mapPresetKey = ref(service.getPresetKey ? service.getPresetKey() : null)

// 机器人自定义形象（data URL），null 表示使用默认矢量绘制
const robotAvatar = ref(getAvatar())

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
// 一键路线规划结果（V1.2）：取自 state 帧的 plan 字段，本地/后端双模式一致
const routePlan = ref(null)
// 巡检目标点标号开关（V1.2：标号点地图 / 不标号点地图），localStorage 持久化
const showGoalNumbers = ref(true)
// 空电搬回确认弹窗显示状态（V1.2）
const showEmptyModal = ref(false)
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

// 悬停格详情：MapCanvas 悬停事件给出 {x, y} 或 null，
// hoverCellType 负责把坐标翻译成"起点 / 巡检点 N / 障碍"等人类可读类型。
const hoverCellType = computed(() => {
  const cell = hoverCell.value
  if (!cell) return ''
  const { x, y } = cell
  if (x < 0 || x >= map.width || y < 0 || y >= map.height) return '界外'
  if (robot.value.x === x && robot.value.y === y) return '机器人'
  if (map.start[0] === x && map.start[1] === y) return '起点'
  if (map.charge_point[0] === x && map.charge_point[1] === y) return '充电点'
  const goalIndex = map.goals.findIndex((g) => g[0] === x && g[1] === y)
  if (goalIndex >= 0) return `巡检点 ${goalIndex + 1}`
  if (map.grid[y][x] === 1) return '障碍'
  return '可通行'
})

// 移动端抽屉
const drawerOpen = ref(false)

// 巡检受阻格（V1.2）：巡检受阻且无法绕行时前方待清障障碍格，驱动地图标记
const patrolBlockedCell = computed(() => patrolStatus.value.blocked_by || null)

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

// 同类告警的节流表：后端高频异常帧（5Hz）若不做节流会叠层遮住地图，
// 这里按类型记录上次弹出时间，非系统提示类至少间隔 TOAST_COOLDOWN_MS 才再弹。
const TOAST_COOLDOWN_MS = 5000
const toastCooldowns = new Map()

// 边界墙编辑被拒提示的节流时间戳（涂抹边界时按 5 秒间隔提示一次）
let lastBoundaryNotice = 0

let unsubscribeState = null
let unsubscribeEvent = null

onMounted(() => {
  loadTheme()
  loadGoalNumbers()
  fitMap()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('resize', handleResize)
  window.addEventListener('orientationchange', handleResize)

  unsubscribeState = service.onState((frame) => {
    robot.value = frame.data
    // 路线规划（V1.2）：无规划时帧内为 null
    routePlan.value = frame.data.plan || null
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
      const msg = frame.data && frame.data.message ? frame.data.message : ''
      if (usingBackend.value) {
        if (msg.includes('已连接到后端')) backendConnected.value = true
        if (msg.includes('断开')) backendConnected.value = false
      }
      if (msg.includes('已完成')) {
        snapshots.value = service.getSnapshots()
      }
      addToast('notice', msg)
    }
  })

  // 后端模式下服务端地图才是权威来源：连接后拉取并同步进响应式地图，
  // 避免刷新页面后客户端默认地图与服务端实际地图不一致。
  if (usingBackend.value) {
    service.fetchMap().then((serverMap) => {
      Object.assign(map, serverMap)
      fitMap()
    })
  }
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
// 目标点标号开关（V1.2）
// --------------------------------------------------------------------------

function loadGoalNumbers() {
  try {
    const stored = localStorage.getItem(GOAL_NUMBERS_KEY)
    if (stored !== null) {
      showGoalNumbers.value = stored === '1'
    }
  } catch {
    showGoalNumbers.value = true
  }
}

function onToggleGoalNumbers() {
  showGoalNumbers.value = !showGoalNumbers.value
  try {
    localStorage.setItem(GOAL_NUMBERS_KEY, showGoalNumbers.value ? '1' : '0')
  } catch (error) {
    console.warn('目标点标号设置保存失败：', error)
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

// 卡住提示：机器人撞障进入 blocked 时弹出提示（toast 内部已按类型节流），
// 与地图抖动、控制台高亮按钮共同构成"撞障三连"反馈。
watch(
  () => robot.value.mode,
  (mode, prev) => {
    if (mode === 'blocked' && prev !== 'blocked') {
      addToast('stuck', '机器人被障碍物卡住，可点击“一键排障”清除前方障碍')
    }
    // 电量耗尽（V1.2）：弹出搬回确认弹窗，用户选择"是"后才送回初始点
    if (mode === 'empty' && prev !== 'empty') {
      showEmptyModal.value = true
    }
  }
)

function onMove(payload) {
  service.move(payload.dx, payload.dy)
}

function onReset() {
  service.reset()
  snapshots.value = []
  stopPlayback()
}

// 一键排障：由服务层执行（本地仿真或后端命令），结果以 notice 形式反馈。
function onResolveFault() {
  service.resolveFault()
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
// 一键路线规划与清障（V1.2）
// --------------------------------------------------------------------------

/**
 * 一键规划路线：服务层计算穿障最短路径与电力预算内的待清障目标，
 * 结果随 state 帧回传（routePlan），地图绘制闪烁虚线与红色标记。
 *
 * @param {number[]} goal - 目标巡检点 [x, y]。
 */
function onPlanRoute(goal) {
  service.planRoute(goal)
}

/** 按当前规划批量清除电力预算内的障碍。 */
function onExecutePlanClear() {
  service.executePlanClear()
}

/** 取消当前路线规划。 */
function onCancelPlan() {
  service.cancelPlan()
}

/**
 * 清障模式下点击地图障碍格：由服务层执行清除（边界墙 / 非障碍 / 空电会被拒绝并提示）。
 *
 * @param {Object} payload - { x, y } 障碍格坐标。
 */
function onClearObstacle({ x, y }) {
  service.clearObstacleAt([x, y])
}

/** 清除巡检受阻点（自动巡检发现障碍且无法绕行时的一键清障）。 */
function onClearBlockedObstacle() {
  const blocked = patrolStatus.value.blocked_by
  if (blocked) {
    service.clearObstacleAt([blocked[0], blocked[1]])
  }
}

/** 空电状态下的“搬回初始点”入口：先弹确认框，避免误触。 */
function onCarryHomePrompt() {
  showEmptyModal.value = true
}

/** 用户确认搬回：服务层把机器人传送回起点并恢复满电。 */
function onCarryHomeConfirm() {
  showEmptyModal.value = false
  service.carryBackHome()
}

// --------------------------------------------------------------------------
// 地图编辑
// --------------------------------------------------------------------------

// 地图被手动编辑后即视为自定义地图，取消预设高亮
function markMapCustom() {
  mapPresetKey.value = null
}

function onEditObstacle({ x, y, value }) {
  if (x < 0 || x >= map.width || y < 0 || y >= map.height) return
  // 真正的边界：最外环不可绘制也不可擦除
  if (isBoundaryCell(x, y, map.width, map.height)) {
    const now = Date.now()
    if (now - lastBoundaryNotice > 5000) {
      lastBoundaryNotice = now
      addToast('notice', '地图外围是固定边界墙：不可绘制、不可擦除，机器人也无法穿越')
    }
    return
  }
  map.grid[y][x] = value
  markMapCustom()
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
  markMapCustom()
  service.updateMap(map)
}

function onSetStart({ x, y }) {
  if (map.grid[y][x] === 1) return
  map.start = [x, y]
  markMapCustom()
  service.updateMap(map)
}

function onSetCharge({ x, y }) {
  if (map.grid[y][x] === 1) return
  map.charge_point = [x, y]
  markMapCustom()
  service.updateMap(map)
}

function onClearGoals() {
  map.goals = []
  markMapCustom()
  service.updateMap(map)
}

function onRemoveGoal(index) {
  map.goals.splice(index, 1)
  markMapCustom()
  service.updateMap(map)
}

/**
 * 切换内置地图：服务层整图替换并复位机器人，随后同步响应式地图、
 * 清理回放数据并按新尺寸适配视图。
 */
function onSelectPreset(key) {
  service.loadPreset(key)
  // 服务层可能替换了内部地图对象，这里把新字段同步进响应式包装
  Object.assign(map, service.getMap())
  mapPresetKey.value = key
  snapshots.value = []
  stopPlayback()
  fitMap()
}

/**
 * 导出当前地图为 JSON 文件。
 */
function onExportMap() {
  exportMap(service.getMap())
}

/**
 * 导入地图：整体替换、清除预设标识、复位机器人并适配视图。
 *
 * @param {Object} imported - 已通过结构校验的地图对象。
 */
function onImportMap(imported) {
  Object.assign(map, imported)
  mapPresetKey.value = null
  service.updateMap(map)
  // 机器人可能停在障碍格上，统一复位到新地图起点
  service.reset()
  snapshots.value = []
  stopPlayback()
  fitMap()
  addToast('notice', '地图导入成功，机器人已复位到起点')
}

/**
 * 地图导入失败提示（结构校验不通过或文件损坏）。
 *
 * @param {string} message - 失败原因。
 */
function onImportError(message) {
  addToast('notice', `地图导入失败：${message}`)
}

/**
 * 更换机器人形象：dataUrl 为 null 表示恢复默认矢量绘制。
 *
 * @param {string|null} dataUrl - 图片 data URL 或 null。
 */
function onAvatarChange(dataUrl) {
  if (dataUrl) {
    if (!setAvatar(dataUrl)) {
      addToast('notice', '形象保存失败：本地存储空间不足')
      return
    }
    addToast('notice', '机器人形象已更新')
  } else {
    clearAvatar()
    addToast('notice', '已恢复默认机器人形象')
  }
  robotAvatar.value = getAvatar()
}

/**
 * 形象上传失败提示（类型/大小不符或读取失败）。
 *
 * @param {string} message - 失败原因。
 */
function onAvatarError(message) {
  addToast('notice', `形象上传失败：${message}`)
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
  ml_anomaly: '工况异常',
  stuck: '卡住提示',
  notice: '系统提示',
}

function addToast(type, message) {
  // notice 类（系统提示）不过节流，其余告警类按类型节流防叠层
  if (type !== 'notice') {
    const now = Date.now()
    const last = toastCooldowns.get(type) || 0
    if (now - last < TOAST_COOLDOWN_MS) return
    toastCooldowns.set(type, now)
  }
  const id = toastId++
  toasts.value.push({ id, type, title: toastTitles[type] || type, message })
  // 最多同时显示 2 条，超出丢弃最旧，避免堆叠遮挡地图/面板
  const MAX_VISIBLE_TOASTS = 2
  if (toasts.value.length > MAX_VISIBLE_TOASTS) {
    toasts.value.splice(0, toasts.value.length - MAX_VISIBLE_TOASTS)
  }
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
    ml_anomaly: 'border-indigo-500',
    stuck: 'border-red-500',
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
