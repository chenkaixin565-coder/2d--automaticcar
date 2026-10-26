<template>
  <DraggablePanel :visible="!!plan" title="路线预览" :width="330" @close="$emit('cancel')">
    <template #icon>
      <span class="w-2 h-2 rounded-full bg-primary-500" />
    </template>

    <div v-if="plan" class="space-y-3">
      <div class="text-xs text-gray-600 dark:text-gray-300">
        目标 <span class="font-mono">[{{ plan.goal[0] }}, {{ plan.goal[1] }}]</span>
        <span class="ml-2 px-1.5 py-0.5 rounded-full text-[10px]" :class="statusClass">{{ statusLabel }}</span>
      </div>

      <div class="grid grid-cols-3 gap-2 text-center">
        <div class="rounded-lg bg-gray-50 dark:bg-gray-800 py-2">
          <div class="text-[11px] text-gray-500">路程</div>
          <div class="text-sm font-semibold">{{ plan.path.length - 1 }} 格</div>
        </div>
        <div class="rounded-lg bg-gray-50 dark:bg-gray-800 py-2">
          <div class="text-[11px] text-gray-500">待清障</div>
          <div class="text-sm font-semibold">{{ plan.obstacles.length }} 处</div>
        </div>
        <div class="rounded-lg bg-gray-50 dark:bg-gray-800 py-2">
          <div class="text-[11px] text-gray-500">预计耗电</div>
          <div class="text-sm font-semibold">{{ plan.total_cost.toFixed(1) }}%</div>
        </div>
      </div>

      <div class="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">
        闪烁虚线为预览路线，红色标记为需要清除的障碍；当前电量 {{ battery.toFixed(1) }}%。
        <span v-if="!plan.reachable" class="text-red-500">电量不足以到达该目标。</span>
        <span v-else-if="!plan.enough" class="text-amber-600 dark:text-amber-400">
          电量只够清除前 {{ plan.clearable.length }} 处，其余需充电后再处理。
        </span>
      </div>

      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
          :disabled="!plan.reachable"
          @click="$emit('start')"
        >
          按此路线巡检
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="$emit('cancel')"
        >
          取消
        </button>
      </div>
      <p class="text-[11px] text-gray-400 dark:text-gray-500">按住标题栏可拖动本窗口</p>
    </div>
  </DraggablePanel>
</template>

<script setup>
/**
 * 组件功能：路线预览浮层（V2.1）
 * 作者：智能巡检机器人二维仿真系统 V2.1 前端开发组
 * 日期：2026-10-27
 * 版本：V2.1
 *
 * 点"预览规划路线"后出现：显示路程/待清障/耗电，可直接开始巡检或取消。
 * 浮层可拖动、可最小化，且层级高于告警 Toast，不会被挡住。
 */

import { computed } from 'vue'
import DraggablePanel from './DraggablePanel.vue'

const props = defineProps({
  plan: { type: Object, default: null },
  battery: { type: Number, default: 100 },
})

defineEmits(['start', 'cancel'])

const statusLabel = computed(() => {
  if (!props.plan) return ''
  if (!props.plan.reachable) return '不可达'
  if (!props.plan.enough) return '预算受限'
  return '电量充足'
})

const statusClass = computed(() => {
  if (!props.plan) return ''
  if (!props.plan.reachable) return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (!props.plan.enough) return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
  return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
})
</script>
