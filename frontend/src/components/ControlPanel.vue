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
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 提供手动方向控制、地图编辑模式切换、自动巡检启停与巡检点管理。
 */

import { computed } from 'vue'

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
})

const emit = defineEmits([
  'move',
  'reset',
  'start-patrol',
  'stop-patrol',
  'set-edit-mode',
  'clear-goals',
  'remove-goal',
])

const editModes = [
  { key: 'pan', label: '平移' },
  { key: 'obstacle', label: '障碍' },
  { key: 'goal', label: '巡检点' },
  { key: 'start', label: '起点' },
  { key: 'charge', label: '充电点' },
]

const modeClass = computed(() => {
  const mode = props.robot.mode
  if (mode === 'patrol') return 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300'
  if (mode === 'charging') return 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300'
  if (mode === 'blocked') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
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
