<template>
  <DraggablePanel :visible="!!plan" title="路线预览" :width="330" @close="$emit('cancel')">
    <template #icon>
      <span class="w-2 h-2 rounded-full" :class="plan && plan.path.length === 0 ? 'bg-red-500' : 'bg-primary-500'" />
    </template>

    <div v-if="plan" class="space-y-3">
      <!-- 不可达：给出清障建议，而不是只弹一句提示 -->
      <template v-if="plan.path.length === 0">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-red-600 dark:text-red-400">无法到达</span>
          <span class="text-xs text-gray-500 dark:text-gray-400">
            目标 <span class="font-mono">[{{ plan.goal[0] }}, {{ plan.goal[1] }}]</span>
          </span>
        </div>
        <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
          {{ plan.message || '目标被障碍封死，当前没有可行路线。' }}
        </p>
        <button
          v-if="plan.suggestion"
          type="button"
          class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-orange-600 text-white hover:bg-orange-700"
          @click="$emit('clear-suggestion', plan.suggestion)"
        >
          清除 [{{ plan.suggestion[0] }}, {{ plan.suggestion[1] }}] 并重新规划（-{{ clearUnit }}%）
        </button>
        <p v-else class="text-[11px] text-gray-500 dark:text-gray-400">
          拆除单格障碍也无法打通；请编辑地图或换一个目标点。
        </p>
        <button
          type="button"
          class="w-full px-3 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
          @click="$emit('cancel')"
        >
          关闭
        </button>
      </template>

      <!-- 可达：显示预算与两种执行方式 -->
      <template v-else>
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
          <span v-if="plan.obstacles.length">
            闪烁虚线会穿过 {{ plan.obstacles.length }} 处障碍（红色标记）。可以清掉它们走直线，也可以直接绕行。
          </span>
          <span v-else>路线不经过障碍，可以直接出发。</span>
          <span v-if="!plan.reachable" class="text-red-500"> 电量不足以到达该目标。</span>
          <span v-else-if="!plan.enough" class="text-amber-600 dark:text-amber-400">
            电量只够清除前 {{ plan.clearable.length }} 处，其余可先绕行。
          </span>
        </div>

        <div v-if="plan.obstacles.length" class="flex flex-col gap-2">
          <button
            type="button"
            class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-orange-600 text-white hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!plan.reachable || plan.clearable.length === 0"
            @click="$emit('start', { mode: 'clear' })"
          >
            清除 {{ plan.clearable.length }} 处并前往（-{{ plan.clear_cost.toFixed(0) }}%）
          </button>
          <button
            type="button"
            class="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
            :disabled="!plan.reachable"
            @click="$emit('start', { mode: 'detour' })"
          >
            绕过障碍直接前往
          </button>
        </div>
        <button
          v-else
          type="button"
          class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
          :disabled="!plan.reachable"
          @click="$emit('start', { mode: 'direct' })"
        >
          前往该点（只巡这一个点）
        </button>

        <button
          type="button"
          class="w-full px-3 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
          @click="$emit('cancel')"
        >
          取消
        </button>
        <p class="text-[11px] text-gray-400 dark:text-gray-500">按住标题栏可拖动本窗口</p>
      </template>
    </div>
  </DraggablePanel>
</template>

<script setup>
/**
 * 组件功能：路线预览浮层（V2.3.1）
 * 作者：智能巡检机器人二维仿真系统 V2.3.1 前端开发组
 * 日期：2026-11-01
 * 版本：V2.3.1
 *
 * 点"预览规划路线"后出现：
 *   - 可达：显示路程 / 待清障 / 耗电，并给两种执行方式
 *     「清除障碍并前往」「绕过障碍直接前往」（只巡目标那一个点）；
 *   - 不可达：显示建议拆除的障碍格，可一键清除并重新规划。
 */

import { computed } from 'vue'
import DraggablePanel from './DraggablePanel.vue'

const props = defineProps({
  plan: { type: Object, default: null },
  battery: { type: Number, default: 100 },
})

defineEmits(['start', 'cancel', 'clear-suggestion'])

const statusLabel = computed(() => {
  if (!props.plan) return ''
  if (!props.plan.reachable) return '电量不足'
  if (!props.plan.enough) return '预算受限'
  return '电量充足'
})

const statusClass = computed(() => {
  if (!props.plan) return ''
  if (!props.plan.reachable) return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (!props.plan.enough) return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
  return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
})

/** 单处清障的耗电，用于按钮文案。 */
const clearUnit = computed(() => {
  const cost = props.plan && props.plan.clear_unit_cost
  return cost === undefined ? 5 : Math.round(cost)
})
</script>
