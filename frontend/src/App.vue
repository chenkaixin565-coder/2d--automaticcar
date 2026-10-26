<template>
  <div class="flex flex-col h-screen overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
    <!-- 顶部栏 -->
    <header class="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 z-20 shrink-0">
      <div class="flex items-center gap-2">
        <h1 class="text-base md:text-lg font-semibold truncate">智能巡检机器人二维仿真系统</h1>
        <span class="hidden sm:inline px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">V2.2.1</span>
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

    <!-- 告警 Toast（V2.0）：改为悬浮层，不占文档流，弹出时地图不会被顶下去 -->
    <div
      class="fixed top-[4.5rem] left-1/2 -translate-x-1/2 z-50 flex flex-col gap-1.5 w-[calc(100%-1rem)] max-w-sm pointer-events-none"
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
          :show-trail="showTrail"
          :pending="pendingCells"
          @view-change="onViewChange"
          @fit="fitMap"
          @edit-cell="onEditCell"
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
          ({{ hoverCell.x }}, {{ hoverCell.y }}) ·
          <span :class="hoverInfo.passable ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'">{{ hoverCellType }}</span>
          <span v-if="!hoverInfo.passable" class="text-red-500"> · 不可通行</span>
          <span v-if="hoverInfo.cost !== null" class="text-gray-500 dark:text-gray-400"> · 到达耗电 {{ hoverInfo.cost }}%</span>
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
          :show-trail="showTrail"
          :pending-count="pendingCells.length"
          @toggle-trail="onToggleTrail"
          @new-map="onOpenNewMap"
          @restart="onRestart"
          @clear-nearest="onClearNearest"
          @open-library="onOpenLibrary"
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
          :pending-count="pendingCells.length"
          @plan-route="onPlanRoute"
          @clear-nearest="onClearNearest"
          @execute-plan-clear="onExecutePlanClear"
          @cancel-plan="onCancelPlan"
          @start-patrol="onStartPatrol"
          @clear-blocked="onClearBlockedObstacle"
        />
        <Joystick class="hidden" @move="onMove" />
        <StatusDashboard
          :robot="robot"
          :temperature-history="temperatureHistory"
          :show-temperature="showTemperature"
          @toggle-temperature="toggleTemperature"
        />
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
        @open-library="onOpenLibrary"
      />

      <!-- 移动端详情：可拖动浮窗（V2.1） -->
      <DraggablePanel
        :visible="drawerOpen"
        title="更多详情"
        :width="340"
        @close="drawerOpen = false"
      >
        <div class="flex flex-col gap-3 max-h-[30vh] overflow-y-auto pr-1">
          <RoutePlanPanel
            :plan="routePlan"
            :map-goals="map.goals"
            :patrol-status="patrolStatus"
            :robot="robot"
            :pending-count="pendingCells.length"
            @plan-route="onPlanRoute"
            @clear-nearest="onClearNearest"
            @execute-plan-clear="onExecutePlanClear"
            @cancel-plan="onCancelPlan"
            @start-patrol="onStartPatrol"
            @clear-blocked="onClearBlockedObstacle"
          />
          <StatusDashboard
            :robot="robot"
            :temperature-history="temperatureHistory"
            :show-temperature="showTemperature"
            @toggle-temperature="toggleTemperature"
          />
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
      </DraggablePanel>
    </main>

    <!-- 路线预览浮层（V2.1）：可拖动、可最小化，不会被告警遮挡 -->
    <PlanPreviewCard
      :plan="routePlan"
      :battery="robot.battery"
      @start="onPlanStart"
      @cancel="onPlanCancel"
    />

    <!-- 地图库（V2.1）：保存 / 切换 / 导入导出 / 新建 -->
    <MapLibraryModal
      :visible="showLibrary"
      :current-map="map"
      :cloud-base="cloudBase"
      @close="showLibrary = false"
      @loaded="onLoadMap"
      @notify="(msg) => addToast('notice', msg)"
      @open-designer="onOpenDesigner"
    />

    <!-- 地图设计器（V2.1）：全屏大画布，自己设计障碍与屏障 -->
    <MapDesigner
      :visible="showDesigner"
      :initial-map="designerInitial"
      @close="showDesigner = false"
      @save="onDesignerSave"
    />

    <!-- 操作密钥（V2.2.0）：后端开启鉴权时弹出 -->
    <AuthModal
      :visible="showAuth"
      :message="authMessage"
      :readonly="authReadonly"
      @submit="onAuthSubmit"
      @close="showAuth = false"
    />

    <!-- 巡检遇阻决策弹窗（V2.0）：停在障碍前一格后询问是否清除 -->
    <ObstacleDialog
      :visible="!!blockedCell"
      :cell="blockedCell ? blockedCell.cell : null"
      :battery="robot.battery"
      :clear-cost="5"
      @decide="onBlockedDecision"
    />

    <!-- 新建地图弹窗（V2.0） -->
    <NewMapModal
      :visible="showNewMapModal"
      @confirm="onNewMapConfirm"
      @dismiss="showNewMapModal = false"
    />

    <!-- 空电弹窗（V2.0）：优先自动返航，到不了才需要用户搬回 -->
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
import ObstacleDialog from './components/ObstacleDialog.vue'
import NewMapModal from './components/NewMapModal.vue'
import PlanPreviewCard from './components/PlanPreviewCard.vue'
import MapLibraryModal from './components/MapLibraryModal.vue'
import MapDesigner from './components/MapDesigner.vue'
import AuthModal from './components/AuthModal.vue'
import DraggablePanel from './components/DraggablePanel.vue'
import { saveLocal } from './services/mapLibrary.js'
import { astar } from './services/astar.js'

const SETTINGS_KEY = 'irm_settings_v1'

/** 目标点标号开关的持久化键名（V1.2：标号点地图 / 不标号点地图）。 */
const GOAL_NUMBERS_KEY = 'irm_goal_numbers_v1'

/** 尾迹显示开关的持久化键名（V2.0：默认隐藏）。 */
const TRAIL_KEY = 'irm_show_trail_v1'

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
// 尾迹是否显示（V2.0：默认隐藏，可手动开启）
const showTrail = ref(false)
// 温度面板是否显示（V2.0：默认隐藏）
const showTemperature = ref(false)
// 新建地图弹窗
const showNewMapModal = ref(false)
// 巡检遇阻决策（V2.0）：{ cell: [x, y] } 或 null
const blockedCell = ref(null)
// 待清障记录（V2.0），来自 state 帧
const pendingCells = ref([])
// 地图库 / 地图设计器（V2.1）
const showLibrary = ref(false)
const showDesigner = ref(false)
// 操作密钥弹窗（V2.2.0）
const showAuth = ref(false)
const authMessage = ref('')
const authReadonly = ref(false)
// 设计器打开时的初始地图：null 表示从空白开始（V2.1）
const designerInitial = ref(null)

/** 云端地图库地址：后端模式取服务基地址，离线模式为 null（禁用云端页签）。 */
const cloudBase = computed(() => (usingBackend.value && service.baseUrl !== undefined ? service.baseUrl : null))

// 地图视图
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
const editMode = ref('nav')
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

/**
 * 悬停格的附加信息（V2.0）：是否可通行、从机器人当前位置到达该格的理论耗电。
 * 耗电按"每格 0.2%"估算；不可通行或不可达时为 null。
 */
const hoverInfo = computed(() => {
  const cell = hoverCell.value
  const empty = { passable: true, cost: null }
  if (!cell) return empty
  const { x, y } = cell
  if (x < 0 || x >= map.width || y < 0 || y >= map.height) {
    return { passable: false, cost: null }
  }
  const passable = map.grid[y][x] === 0
  if (!passable) return { passable: false, cost: null }
  const result = astar(map.grid, [map.start[0], map.start[1]], [x, y])
  if (!result.path || result.path.length === 0) return { passable: true, cost: null }
  const from = [robot.value.x, robot.value.y]
  const route = astar(map.grid, from, [x, y])
  const steps = route.path && route.path.length > 0 ? route.path.length - 1 : null
  if (steps === null) return { passable: true, cost: null }
  return { passable: true, cost: (steps * 0.2).toFixed(1) }
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
  const snap = snapshots.value[playbackIndex.value] || snapshots.value[snapshots.value.length - 1]
  if (!snap) return null
  // V2.0：快照只保存尾迹长度，渲染时再切片，避免每帧深拷贝整条轨迹。
  if (snap.visitedTrail) return snap
  return { ...snap, visitedTrail: visitedTrail.value.slice(0, snap.trailLen || 0) }
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
  loadTrailSetting()
  fitMap()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('resize', handleResize)
  window.addEventListener('orientationchange', handleResize)

  unsubscribeState = service.onState((frame) => {
    robot.value = frame.data
    // 路线规划（预览）：无规划时帧内为 null
    routePlan.value = frame.data.plan || null
    visitedTrail.value = service.getVisitedTrail()
    // 远程模式下 patrol 由 state 帧携带；本地模式直接读服务
    patrolStatus.value = frame.data.patrol || service.getPatrolStatus()
    pendingCells.value = frame.data.pending || []
    blockedCell.value = frame.data.blocked ? { cell: frame.data.blocked.cell } : null
    if (showTemperature.value) {
      temperatureHistory.value.push(frame.data.sensors.temperature)
      if (temperatureHistory.value.length > 300) {
        temperatureHistory.value.shift()
      }
    }
  })

  // 连接可能在界面挂载前就因缺少密钥被拒绝，这里补读一次状态（V2.2.0）
  if (typeof service.getAuthState === 'function') {
    const auth = service.getAuthState()
    if (auth) {
      authReadonly.value = Boolean(auth.readonly)
      authMessage.value = auth.message || '需要操作密钥才能修改状态'
      showAuth.value = true
    }
  }

  unsubscribeEvent = service.onEvent((frame) => {
    if (frame.type === 'anomaly') {
      anomalies.value = service.getAnomalies()
      addToast(frame.data.type, frame.data.message)
    } else if (frame.type === 'blocked') {
      // 巡检遇阻：弹出三选一对话框（清除 / 跳过记录 / 停止）
      blockedCell.value = { cell: frame.data.cell }
      addToast('stuck', frame.data.message)
    } else if (frame.type === 'empty') {
      showEmptyModal.value = true
    } else if (frame.type === 'auth_required') {
      // 后端开启了 OPERATOR_KEY 或只读模式：提示输入密钥 / 告知只读
      authReadonly.value = Boolean(frame.data && frame.data.readonly)
      authMessage.value = (frame.data && frame.data.message) || '需要操作密钥才能修改状态'
      showAuth.value = true
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
  // 用户主动"适配地图"后，预览的还原点失效（否则关预览会把视角抢回去）
  viewBeforePreview = null
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
  service.reset(false)
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
  if (routePlan.value) {
    onPlanStart()
    return
  }
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
  // 手机端：预览浮层要独占视野，先把详情浮窗收起来
  if (window.innerWidth < 768) drawerOpen.value = false
}

/** 打开预览前保存的视角，关闭预览时还原（V2.1.1）。 */
let viewBeforePreview = null
/** 点"按此路线巡检"后不还原视角，避免刚出发就跳回原视野。 */
let keepViewOnPlanEnd = false

/**
 * 把视角带到路线附近：只保证"看得到整条路线"，不做夸张放大。
 *
 * V2.1.1 起：缩放上限为 90%，且不超过预览前缩放的 1.8 倍，
 * 短路线（包围盒只有两三格）不会再被放大到 200% 而看不出地图全貌。
 *
 * @param {number[][]} path - 路线坐标数组。
 */
function fitRoute(path) {
  if (!path || path.length === 0) return
  const rect = getContainerRect()
  if (!rect) return
  if (!viewBeforePreview) {
    viewBeforePreview = { scale: scale.value, offset: { ...offset.value } }
  }
  const xs = path.map((p) => p[0])
  const ys = path.map((p) => p[1])
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const w = (maxX - minX + 1) * CELL_PIXELS
  const h = (maxY - minY + 1) * CELL_PIXELS
  const padding = 60
  // 手机端预览卡片停在下方，路线尽量落在上半屏，避免被浮层压住
  const compact = rect.width < 768
  const availH = compact ? rect.height * 0.55 : rect.height
  const fitScale = Math.min((rect.width - padding) / w, (availH - padding) / h)
  // 上限：最多 90%；同时最多是原视角的 1.8 倍（至少 55%，保证小屏也看得清路线）
  const cap = Math.min(0.9, Math.max(0.55, viewBeforePreview.scale * 1.8))
  const s = Math.max(0.28, Math.min(fitScale, cap))
  const centerX = ((minX + maxX + 1) / 2) * CELL_PIXELS
  const centerY = ((minY + maxY + 1) / 2) * CELL_PIXELS
  const targetX = rect.width / 2
  const targetY = compact ? rect.height * 0.26 : rect.height / 2
  const mapW = map.width * CELL_PIXELS * s
  const mapH = map.height * CELL_PIXELS * s
  const rawY = targetY - centerY * s
  offset.value = {
    x: clampOffset(targetX - centerX * s, rect.width, mapW),
    // 手机端不夹纵向：卡片盖住下半屏，宁可地图下方留白，也要把路线顶到可见区域
    y: compact ? rawY : clampOffset(rawY, rect.height, mapH),
  }
  scale.value = s
}

/**
 * 限制平移量：地图比视口大时按边缘对齐，地图比视口小时居中，
 * 避免"路线居中了但地图被推到只剩一大片空白"。
 *
 * @param {number} value - 期望偏移。
 * @param {number} viewSize - 视口尺寸。
 * @param {number} contentSize - 地图渲染尺寸。
 * @returns {number} 修正后的偏移。
 */
function clampOffset(value, viewSize, contentSize) {
  if (contentSize <= viewSize) return (viewSize - contentSize) / 2
  return Math.min(0, Math.max(viewSize - contentSize, value))
}

/** 关闭预览时回到打开前的视角，避免"看完路线地图停在一个角落"。 */
function restoreViewBeforePreview() {
  if (!viewBeforePreview) return
  scale.value = viewBeforePreview.scale
  offset.value = { ...viewBeforePreview.offset }
  viewBeforePreview = null
}

// 规划结果一到就把视角带过去；预览结束后还原（除非是"按此路线巡检"）
watch(
  () => routePlan.value,
  (plan) => {
    if (plan && plan.path && plan.path.length > 1) {
      fitRoute(plan.path)
      return
    }
    if (!plan) {
      if (keepViewOnPlanEnd) {
        keepViewOnPlanEnd = false
        viewBeforePreview = null
        return
      }
      restoreViewBeforePreview()
    }
  }
)

/** 按预览路线开始巡检：把预览目标排到第一位，并收起预览。 */
function onPlanStart() {
  const plan = routePlan.value
  const goals = map.goals.map((g) => [g[0], g[1]])
  if (plan && plan.goal) {
    const index = goals.findIndex((g) => g[0] === plan.goal[0] && g[1] === plan.goal[1])
    if (index > 0) {
      const [target] = goals.splice(index, 1)
      goals.unshift(target)
    }
  }
  keepViewOnPlanEnd = true
  service.startPatrol(goals)
  service.cancelPlan()
}

/** 取消预览：清掉闪烁虚线与标记。 */
function onPlanCancel() {
  service.cancelPlan()
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

/**
 * 巡检遇阻决策（V2.0）：clear = 清除并继续；skip = 跳过并记入待清障；stop = 停止巡检。
 *
 * @param {'clear'|'skip'|'stop'} action - 决策动作。
 */
function onBlockedDecision(action) {
  blockedCell.value = null
  service.patrolDecision(action)
}

/** 一键清除待清障记录里离机器人最近的一处。 */
function onClearNearest() {
  service.clearNearestPending()
}

/** 重新开始：复位机器人但保留尾迹（V2.0）。 */
function onRestart() {
  service.restart()
  snapshots.value = []
  stopPlayback()
}

/**
 * 从地图库载入一张地图（V2.1）。
 *
 * @param {Object} loaded - 已通过校验的地图对象。
 */
function onLoadMap(loaded) {
  service.updateMap(loaded)
  Object.assign(map, service.getMap())
  mapPresetKey.value = null
  service.reset(false)
  snapshots.value = []
  stopPlayback()
  showLibrary.value = false
  fitMap()
  addToast('notice', '地图已载入')
}

/**
 * 提交操作密钥：写入 sessionStorage 并重连 WebSocket（V2.2.0）。
 *
 * @param {string} key - OPERATOR_KEY 明文。
 */
function onAuthSubmit(key) {
  if (typeof service.setOperatorKey !== 'function') {
    showAuth.value = false
    return
  }
  service.setOperatorKey(key)
  showAuth.value = false
  addToast('notice', '已设置操作密钥，正在重新连接…')
}

/** 打开地图库：移动端先收起详情浮窗，避免两层浮层叠在一起。 */
function onOpenLibrary() {
  drawerOpen.value = false
  showLibrary.value = true
}

/**
 * 打开地图设计器。
 *
 * @param {{blank: boolean}} [options] - blank=true 从空白图开始，否则编辑当前地图。
 */
function onOpenDesigner(options) {
  const blank = options && options.blank
  designerInitial.value = blank ? null : JSON.parse(JSON.stringify(map))
  showLibrary.value = false
  showDesigner.value = true
}

/**
 * 设计器保存：先存进本机地图库，再载入仿真。
 *
 * @param {{name: string, map: Object}} payload - 名称与地图。
 */
function onDesignerSave({ name, map: designed }) {
  saveLocal(name, designed)
  service.updateMap(designed)
  Object.assign(map, service.getMap())
  mapPresetKey.value = null
  service.reset(false)
  snapshots.value = []
  stopPlayback()
  showDesigner.value = false
  fitMap()
  addToast('notice', `地图「${name}」已保存到地图库并载入`)
}

/** 打开"新建地图"弹窗。 */
function onOpenNewMap() {
  showNewMapModal.value = true
}

/**
 * 确认新建地图：清空当前地图，只保留边界墙。
 *
 * @param {{width: number, height: number}} size - 新地图尺寸。
 */
function onNewMapConfirm({ width, height }) {
  showNewMapModal.value = false
  service.newMap(width, height)
  Object.assign(map, service.getMap())
  mapPresetKey.value = null
  snapshots.value = []
  stopPlayback()
  blockedCell.value = null
  pendingCells.value = []
  fitMap()
}

/** 尾迹显示开关（V2.0：默认隐藏）。 */
function onToggleTrail() {
  showTrail.value = !showTrail.value
  try {
    localStorage.setItem(TRAIL_KEY, showTrail.value ? '1' : '0')
  } catch (error) {
    console.warn('尾迹设置保存失败：', error)
  }
}

/** 读取尾迹开关设置。 */
function loadTrailSetting() {
  try {
    showTrail.value = localStorage.getItem(TRAIL_KEY) === '1'
  } catch {
    showTrail.value = false
  }
}

/** 温度面板显示开关（V2.0：默认隐藏）。 */
function toggleTemperature() {
  showTemperature.value = !showTemperature.value
  if (showTemperature.value) {
    temperatureHistory.value = []
  }
}

// --------------------------------------------------------------------------
// 地图编辑
// --------------------------------------------------------------------------

// 地图被手动编辑后即视为自定义地图，取消预设高亮
function markMapCustom() {
  mapPresetKey.value = null
}

/**
 * 编辑单个格子（V2.1）：障碍 / 固定屏障 / 擦除，都不消耗电量。
 *
 * @param {{x: number, y: number, value: 0|1|2}} payload - 格子坐标与目标值。
 */
function onEditCell({ x, y, value }) {
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

  // 擦除固定屏障需要二次确认（避免手滑把设计好的隔断擦掉）
  if (value === 0 && map.grid[y][x] === 2) {
    if (!window.confirm(`确认擦除固定屏障 (${x}, ${y})？`)) return
  }

  const isKeyCell =
    (map.start[0] === x && map.start[1] === y) ||
    (map.charge_point[0] === x && map.charge_point[1] === y) ||
    map.goals.some((g) => g[0] === x && g[1] === y)
  if (value !== 0 && isKeyCell) {
    addToast('notice', '该格是起点 / 充电点 / 巡检点，不能设为障碍或屏障')
    return
  }
  if (value !== 0 && robot.value.x === x && robot.value.y === y) {
    addToast('notice', '机器人正站在该格上，请先把它移开')
    return
  }

  map.grid[y][x] = value
  markMapCustom()
  service.setCell(x, y, value)
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
