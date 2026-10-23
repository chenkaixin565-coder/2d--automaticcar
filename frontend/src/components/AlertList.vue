<template>
  <div class="flex flex-col gap-3 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 h-96">
    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">告警列表</h2>
      <div class="flex gap-2">
        <button
          type="button"
          class="text-xs px-2 py-1 rounded-md border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="$emit('export')"
        >
          导出 JSON
        </button>
        <button
          type="button"
          class="text-xs px-2 py-1 rounded-md text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
          @click="$emit('clear')"
        >
          清空
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto pr-1 space-y-2">
      <div v-if="anomalies.length === 0" class="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
        暂无异常事件
      </div>
      <div
        v-for="(item, index) in anomalies"
        :key="index"
        class="flex gap-3 p-3 rounded-lg border-l-4 text-sm"
        :class="typeClass(item.type)"
      >
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="font-medium">{{ typeLabel(item.type) }}</span>
            <span class="text-xs text-gray-500 dark:text-gray-400">{{ formatTime(item.time) }}</span>
          </div>
          <p class="text-gray-700 dark:text-gray-300 mt-0.5">{{ item.message }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            位置：[{{ item.position[0] }}, {{ item.position[1] }}]
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：告警列表
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 以时间线方式展示异常事件，支持清空与导出 JSON。
 */

defineProps({
  anomalies: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['clear', 'export'])

const typeLabels = {
  low_battery: '低电量',
  obstacle: '障碍物',
  sensor_fault: '传感器异常',
  overheat: '过热',
}

const typeClasses = {
  low_battery: 'border-orange-500 bg-orange-50 dark:bg-orange-900/20',
  obstacle: 'border-red-500 bg-red-50 dark:bg-red-900/20',
  sensor_fault: 'border-purple-500 bg-purple-50 dark:bg-purple-900/20',
  overheat: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
}

function typeLabel(type) {
  return typeLabels[type] || type
}

function typeClass(type) {
  return typeClasses[type] || 'border-gray-500 bg-gray-50 dark:bg-gray-800'
}

function formatTime(isoString) {
  const date = new Date(isoString)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>
