<template>
  <div class="flex flex-col gap-4 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">控制面板</h2>
      <span
        class="px-2 py-0.5 text-xs font-medium rounded-full"
        :class="modeClass"
      >
        {{ robot.mode }}
      </span>
    </div>

    <!-- 手动控制 -->
    <div class="grid grid-cols-3 gap-2 w-max mx-auto">
      <div />
      <button
        type="button"
        class="control-btn"
        aria-label="前进"
        @click="emitMove(0, -1)"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
      </button>
      <div />
      <button
        type="button"
        class="control-btn"
        aria-label="左转"
        @click="emitMove(-1, 0)"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
      </button>
      <button
        type="button"
        class="control-btn bg-gray-100 dark:bg-gray-800"
        aria-label="复位"
        @click="$emit('reset')"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></svg>
      </button>
      <button
        type="button"
        class="control-btn"
        aria-label="右转"
        @click="emitMove(1, 0)"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
      </button>
      <div />
      <button
        type="button"
        class="control-btn"
        aria-label="后退"
        @click="emitMove(0, 1)"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7" /></svg>
      </button>
      <div />
    </div>
    <p class="text-xs text-center text-gray-500 dark:text-gray-400">支持键盘 WASD / 方向键</p>

    <!-- 编辑模式 -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="mode in editModes"
        :key="mode.key"
        type="button"
        class="px-3 py-1.5 text-xs rounded-lg border transition-colors"
        :class="editMode === mode.key ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'"
        @click="$emit('set-edit-mode', mode.key)"
      >
        {{ mode.label }}
      </button>
    </div>

    <!-- 目标点标号开关：标号点地图 / 不标号点地图 -->
    <label class="flex items-center justify-between gap-2 px-1 cursor-pointer select-none">
      <span class="text-xs text-gray-600 dark:text-gray-300">目标点标号</span>
      <button
        type="button"
        role="switch"
        :aria-checked="showGoalNumbers ? 'true' : 'false'"
        class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
        :class="showGoalNumbers ? 'bg-primary-600' : 'bg-gray-300 dark:bg-gray-700'"
        @click="$emit('toggle-goal-numbers')"
      >
        <span
          class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
          :class="showGoalNumbers ? 'translate-x-[1.15rem]' : 'translate-x-[0.15rem]'"
        />
      </button>
    </label>

    <!-- 自动巡检 -->
    <div class="space-y-2">
      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="patrolStatus.running"
          @click="$emit('start-patrol')"
        >
          开始巡检
        </button>
        <button
          type="button"
          class="flex-1 px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
          :disabled="!patrolStatus.running"
          @click="$emit('stop-patrol')"
        >
          停止巡检
        </button>
      </div>
      <div v-if="patrolStatus.running" class="space-y-1">
        <div class="flex justify-between text-xs text-gray-600 dark:text-gray-300">
          <span>进度</span>
          <span>{{ patrolStatus.progress }}%</span>
        </div>
        <div class="h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
          <div
            class="h-full bg-primary-500 transition-all"
            :style="{ width: `${patrolStatus.progress}%` }"
          />
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400">
          剩余路径段：{{ patrolStatus.path_remain }}
        </p>
      </div>
    </div>

    <!-- 一键排障 -->
    <div class="space-y-2">
      <button
        type="button"
        class="w-full px-3 py-2 text-sm font-medium rounded-lg border transition-colors flex items-center justify-center gap-2"
        :class="robot.mode === 'blocked'
          ? 'border-red-500 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/50'
          : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'"
        @click="$emit('resolve-fault')"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" /></svg>
        一键排障
      </button>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        机器人被障碍卡住时，自动清除前方障碍并恢复正常控制
      </p>
      <!-- 空电状态：引导用户确认后搬回初始点 -->
      <button
        v-if="robot.mode === 'empty'"
        type="button"
        class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 flex items-center justify-center gap-2"
        @click="$emit('carry-home')"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><path d="M9 22V12h6v10" /></svg>
        机器人没有电了，搬回初始点
      </button>
    </div>

    <!-- 内置地图 -->
    <div class="space-y-2">
      <h3 class="text-sm font-medium text-gray-800 dark:text-gray-200">内置地图</h3>
      <div class="flex flex-col gap-1.5">
        <button
          v-for="preset in MAP_PRESETS"
          :key="preset.key"
          type="button"
          class="flex items-center justify-between gap-2 px-3 py-2 text-xs rounded-lg border transition-colors text-left"
          :class="mapPreset === preset.key
            ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
            : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'"
          @click="$emit('select-preset', preset.key)"
        >
          <span class="min-w-0">
            <span class="font-medium">{{ preset.name }}</span>
            <span class="ml-1 text-gray-500 dark:text-gray-400">{{ preset.description }}</span>
          </span>
          <svg v-if="mapPreset === preset.key" class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
        </button>
      </div>
      <p class="text-xs text-gray-500 dark:text-gray-400">切换后机器人自动复位到新地图起点</p>
    </div>

    <!-- 地图导入导出 -->
    <div class="space-y-2">
      <h3 class="text-sm font-medium text-gray-800 dark:text-gray-200">地图导入导出</h3>
      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="$emit('export-map')"
        >
          导出地图
        </button>
        <button
          type="button"
          class="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="triggerImport"
        >
          导入地图
        </button>
        <!-- 隐藏的文件选择框，由"导入地图"按钮触发 -->
        <input
          ref="fileInputRef"
          type="file"
          accept=".json,application/json"
          class="hidden"
          @change="onFileChange"
        >
      </div>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        导出当前地图为 JSON 文件；导入时自动校验结构，成功后机器人复位
      </p>
    </div>

    <!-- 机器人形象 -->
    <div class="space-y-2">
      <h3 class="text-sm font-medium text-gray-800 dark:text-gray-200">机器人形象</h3>
      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="triggerAvatarUpload"
        >
          上传形象
        </button>
        <button
          v-if="hasAvatar"
          type="button"
          class="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="$emit('avatar-change', null)"
        >
          恢复默认
        </button>
        <input
          ref="avatarInputRef"
          type="file"
          accept="image/*"
          class="hidden"
          @change="onAvatarFileChange"
        >
      </div>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        支持 PNG / JPG / SVG，不超过 2MB；图片仅保存在本地浏览器
      </p>
    </div>

    <!-- 巡检点列表 -->
    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-medium text-gray-800 dark:text-gray-200">巡检点</h3>
        <button
          type="button"
          class="text-xs text-red-500 hover:text-red-600"
          @click="$emit('clear-goals')"
        >
          清空
        </button>
      </div>
      <div v-if="mapGoals.length === 0" class="text-xs text-gray-500 dark:text-gray-400">
        点击“设置巡检点”后在地图上添加
      </div>
      <ul v-else class="flex flex-wrap gap-2">
        <li
          v-for="(goal, index) in mapGoals"
          :key="`${goal[0]},${goal[1]}`"
          class="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300"
        >
          <span>{{ index + 1 }}. [{{ goal[0] }}, {{ goal[1] }}]</span>
          <button type="button" class="hover:text-red-500" @click="$emit('remove-goal', index)">×</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：控制面板
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 提供手动方向控制、地图编辑模式切换、自动巡检启停与巡检点管理。
 */

import { computed, ref } from 'vue'
import { MAP_PRESETS } from '../services/mapPresets.js'
import { importMap } from '../utils/mapIO.js'
import { readAvatarFile } from '../utils/robotAvatar.js'

const props = defineProps({
  robot: {
    type: Object,
    required: true,
  },
  patrolStatus: {
    type: Object,
    required: true,
  },
  editMode: {
    type: String,
    default: 'pan',
  },
  mapGoals: {
    type: Array,
    default: () => [],
  },
  mapPreset: {
    type: String,
    default: null,
  },
  hasAvatar: {
    type: Boolean,
    default: false,
  },
  showGoalNumbers: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits([
  'move',
  'reset',
  'resolve-fault',
  'select-preset',
  'export-map',
  'import-map',
  'import-error',
  'avatar-change',
  'avatar-error',
  'start-patrol',
  'stop-patrol',
  'set-edit-mode',
  'clear-goals',
  'remove-goal',
  'toggle-goal-numbers',
  'carry-home',
])

// --------------------------------------------------------------------------
// 地图导入：隐藏 file input 的选择与解析
// --------------------------------------------------------------------------

const fileInputRef = ref(null)

function triggerImport() {
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
}

async function onFileChange(event) {
  const file = event.target.files && event.target.files[0]
  // 清空选择值，允许重复导入同一个文件
  event.target.value = ''
  if (!file) return
  try {
    const imported = await importMap(file)
    emit('import-map', imported)
  } catch (error) {
    emit('import-error', error.message || '未知错误')
  }
}

// --------------------------------------------------------------------------
// 机器人形象上传：隐藏 file input 的选择与校验
// --------------------------------------------------------------------------

const avatarInputRef = ref(null)

function triggerAvatarUpload() {
  if (avatarInputRef.value) {
    avatarInputRef.value.click()
  }
}

async function onAvatarFileChange(event) {
  const file = event.target.files && event.target.files[0]
  event.target.value = ''
  if (!file) return
  try {
    const dataUrl = await readAvatarFile(file)
    emit('avatar-change', dataUrl)
  } catch (error) {
    emit('avatar-error', error.message || '未知错误')
  }
}

const editModes = [
  { key: 'pan', label: '平移' },
  { key: 'obstacle', label: '障碍' },
  { key: 'goal', label: '巡检点' },
  { key: 'start', label: '起点' },
  { key: 'charge', label: '充电点' },
  { key: 'clear', label: '清障' },
]

const modeClass = computed(() => {
  const mode = props.robot.mode
  if (mode === 'patrol') return 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300'
  if (mode === 'charging') return 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300'
  if (mode === 'blocked') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (mode === 'empty') return 'bg-gray-800 text-white dark:bg-gray-200 dark:text-gray-800'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
})

function emitMove(dx, dy) {
  emit('move', { dx, dy })
}
</script>

<style scoped>
.control-btn {
  @apply flex items-center justify-center w-10 h-10 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors;
}
</style>
