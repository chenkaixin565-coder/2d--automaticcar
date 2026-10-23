<template>
  <div v-if="snapshots.length > 0" class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-3">
    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">路径回放</h2>
      <span class="text-xs text-gray-500 dark:text-gray-400">{{ currentIndex + 1 }} / {{ snapshots.length }}</span>
    </div>
    <div class="flex items-center gap-3">
      <button
        type="button"
        class="play-pause-button flex items-center justify-center w-9 h-9 rounded-full bg-primary-600 text-white hover:bg-primary-700"
        :aria-label="isPlaying ? '暂停' : '播放'"
        @click="togglePlay"
      >
        <svg v-if="isPlaying" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg>
        <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
      </button>
      <input
        type="range"
        min="0"
        :max="snapshots.length - 1"
        :value="currentIndex"
        class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-600"
        @input="handleInput"
      >
      <span class="text-xs font-mono text-gray-600 dark:text-gray-300 w-16 text-right">{{ formatTime(currentTime) }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：路径回放控制条
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 在巡检结束后提供时间轴拖动与播放 / 暂停，用于回放机器人轨迹。
 */

import { computed } from 'vue'

const props = defineProps({
  snapshots: {
    type: Array,
    default: () => [],
  },
  currentIndex: {
    type: Number,
    default: 0,
  },
  isPlaying: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['seek', 'play', 'pause'])

const currentTime = computed(() => {
  const snapshot = props.snapshots[props.currentIndex]
  return snapshot ? snapshot.time : 0
})

function togglePlay() {
  emit(props.isPlaying ? 'pause' : 'play')
}

function handleInput(event) {
  emit('seek', Number(event.target.value))
}

function formatTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>
