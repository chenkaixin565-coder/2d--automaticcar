<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="$emit('dismiss')" />
      <div
        class="relative w-full max-w-sm rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-map-title"
      >
        <div class="flex items-center gap-2">
          <span class="flex items-center justify-center w-9 h-9 rounded-full bg-primary-100 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" />
            </svg>
          </span>
          <h3 id="new-map-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">新建地图</h3>
        </div>

        <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">
          将清空当前地图（含障碍、巡检点与尾迹），只保留四周边界墙，机器人回到新起点。
        </p>

        <div class="mt-4 space-y-3">
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-300">尺寸预设</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="preset in presets"
              :key="preset.label"
              type="button"
              class="px-3 py-1.5 text-xs rounded-lg border transition-colors"
              :class="width === preset.width && height === preset.height
                ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300'"
              @click="applyPreset(preset)"
            >
              {{ preset.label }}
            </button>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-xs text-gray-500 dark:text-gray-400">宽（列）</span>
              <input
                v-model.number="width"
                type="number"
                min="10"
                max="60"
                class="mt-1 w-full px-2.5 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
            </label>
            <label class="block">
              <span class="text-xs text-gray-500 dark:text-gray-400">高（行）</span>
              <input
                v-model.number="height"
                type="number"
                min="10"
                max="60"
                class="mt-1 w-full px-2.5 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
            </label>
          </div>
          <p v-if="error" class="text-xs text-red-500">{{ error }}</p>
          <p v-else class="text-xs text-gray-400 dark:text-gray-500">允许范围 10×10 ~ 60×60 格</p>
        </div>

        <div class="mt-4 flex gap-2">
          <button
            type="button"
            class="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
            :disabled="!!error"
            @click="confirm"
          >
            创建空白地图
          </button>
          <button
            type="button"
            class="flex-1 px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
            @click="$emit('dismiss')"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：新建地图弹窗（V2.0）
 * 作者：智能巡检机器人二维仿真系统 V2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.0
 *
 * 选定尺寸后由服务层生成一张只有边界墙的空白地图，机器人复位到新起点，
 * 用户随后可用"障碍 / 巡检点 / 起点 / 充电点"模式自行绘制。
 */

import { computed, ref, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['confirm', 'dismiss'])

const MIN_SIZE = 10
const MAX_SIZE = 60

const presets = [
  { label: '小 20×12', width: 20, height: 12 },
  { label: '中 30×20', width: 30, height: 20 },
  { label: '大 40×28', width: 40, height: 28 },
]

const width = ref(30)
const height = ref(20)

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      width.value = 30
      height.value = 20
    }
  }
)

const error = computed(() => {
  const w = Number(width.value)
  const h = Number(height.value)
  if (!Number.isInteger(w) || !Number.isInteger(h)) return '宽高必须是整数'
  if (w < MIN_SIZE || w > MAX_SIZE || h < MIN_SIZE || h > MAX_SIZE) {
    return `宽高需在 ${MIN_SIZE} ~ ${MAX_SIZE} 之间`
  }
  return ''
})

function applyPreset(preset) {
  width.value = preset.width
  height.value = preset.height
}

function confirm() {
  if (error.value) return
  emit('confirm', { width: Number(width.value), height: Number(height.value) })
}
</script>
