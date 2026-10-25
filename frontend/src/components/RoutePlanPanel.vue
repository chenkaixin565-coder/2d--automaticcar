<template>
  <div class="flex flex-col gap-3 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">路线规划</h2>
      <span
        v-if="plan"
        class="px-2 py-0.5 text-xs font-medium rounded-full"
        :class="planStatusClass"
      >
        {{ planStatusLabel }}
      </span>
    </div>

    <!-- 未规划：选择目标 + 一键规划 -->
    <div v-if="!plan" class="space-y-2">
      <label class="block text-xs font-medium text-gray-600 dark:text-gray-300">规划目标（点击地图上的蓝色巡检点或在此选择）</label>
      <div v-if="mapGoals.length > 0" class="flex flex-wrap gap-1.5">
        <button
          v-for="(goal, index) in mapGoals"
          :key="`${goal[0]},${goal[1]}`"
          type="button"
          class="px-2.5 py-1.5 text-xs rounded-lg border transition-colors"
          :class="selectedGoalIndex === index
            ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
            : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300'"
          @click="selectedGoalIndex = index"
        >
          {{ index + 1 }}. [{{ goal[0] }}, {{ goal[1] }}]
        </button>
      </div>
      <p v-else class="text-xs text-gray-500 dark:text-gray-400">
        当前地图没有巡检点，请切换到“巡检点”编辑模式后在地图上添加
      </p>
      <button
        type="button"
        class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        :disabled="mapGoals.length === 0"
        @click="emitPlanRoute"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4.5 8-11a8 8 0 1 0-16 0c0 6.5 8 11 8 11z" /><circle cx="12" cy="11" r="3" /></svg>
        一键规划路线
      </button>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        按理论最短路径规划（可穿越普通障碍），自动计算移动与清障耗电，决定可清障个数
      </p>
    </div>

    <!-- 已规划：路线详情与操作 -->
    <div v-else class="space-y-3">
      <dl class="grid grid-cols-2 gap-y-1.5 gap-x-3 text-xs">
        <dt class="text-gray-500 dark:text-gray-400">目标点</dt>
        <dd class="text-right font-medium text-gray-800 dark:text-gray-200">[{{ plan.goal[0] }}, {{ plan.goal[1] }}]</dd>
        <dt class="text-gray-500 dark:text-gray-400">全程</dt>
        <dd class="text-right font-medium text-gray-800 dark:text-gray-200">{{ plan.path.length - 1 }} 格</dd>
        <dt class="text-gray-500 dark:text-gray-400">路径障碍</dt>
        <dd class="text-right font-medium text-gray-800 dark:text-gray-200">
          {{ plan.obstacles.length }} 处<span v-if="plan.clearable.length < plan.obstacles.length" class="text-amber-600 dark:text-amber-400">（预算内 {{ plan.clearable.length }} 处）</span>
        </dd>
        <dt class="text-gray-500 dark:text-gray-400">移动耗电</dt>
        <dd class="text-right font-medium text-gray-800 dark:text-gray-200">{{ plan.move_cost.toFixed(1) }}%</dd>
        <dt class="text-gray-500 dark:text-gray-400">清障耗电</dt>
        <dd class="text-right font-medium text-gray-800 dark:text-gray-200">
          {{ plan.clearable.length }} × {{ plan.clear_unit_cost.toFixed(0) }}% = {{ plan.clear_cost.toFixed(1) }}%
        </dd>
        <dt class="text-gray-500 dark:text-gray-400">预计总耗电</dt>
        <dd class="text-right font-medium text-gray-800 dark:text-gray-200">
          {{ plan.total_cost.toFixed(1) }}%
          <span class="text-gray-400 dark:text-gray-500">/ 规划时电量 {{ plan.battery.toFixed(0) }}%</span>
        </dd>
      </dl>

      <!-- 电力预算提示 -->
      <p v-if="!plan.reachable" class="text-xs text-red-600 dark:text-red-400">
        当前电量不足以移动到目标点，请先充电或就近清除障碍
      </p>
      <p v-else-if="!plan.enough" class="text-xs text-amber-600 dark:text-amber-400">
        电量不足以清除全部障碍：已按预算将前 {{ plan.clearable.length }} 处纳入清障计划（灰色空心标记处需充电后再处理）
      </p>

      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="plan.clearable.length === 0 || robot.mode === 'empty'"
          @click="$emit('execute-plan-clear')"
        >
          执行清障（{{ plan.clearable.length }} 处 · {{ plan.clear_cost.toFixed(0) }}%）
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
          @click="$emit('cancel-plan')"
        >
          取消
        </button>
      </div>
      <button
        type="button"
        class="w-full px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200 disabled:opacity-50"
        :disabled="patrolStatus.running"
        @click="$emit('start-patrol')"
      >
        开始巡检
      </button>

      <!-- 巡检受阻：不清障告警，仅提示可一键清除 -->
      <div
        v-if="patrolStatus.blocked_by"
        class="rounded-lg border border-orange-200 dark:border-orange-900/50 bg-orange-50 dark:bg-orange-900/20 p-2.5 space-y-1.5"
      >
        <p class="text-xs text-orange-700 dark:text-orange-300">
          巡检受阻：前方 [{{ patrolStatus.blocked_by[0] }}, {{ patrolStatus.blocked_by[1] }}] 有障碍，清除后继续巡检（不中断任务）
        </p>
        <button
          type="button"
          class="w-full px-2.5 py-1.5 text-xs font-medium rounded-lg bg-orange-600 text-white hover:bg-orange-700 disabled:opacity-50"
          :disabled="robot.mode === 'empty'"
          @click="$emit('clear-blocked')"
        >
          清除该障碍
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：一键路线规划面板（V1.2）
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 负责一键规划路线的目标选择、路线详情（路径长 / 待清障数 / 电力预算）
 * 与清障执行。规划结果由服务层计算并通过 state 帧的 plan 字段回传，
 * 地图画布据此绘制闪烁虚线与红色清障标记。
 */

import { ref, computed } from 'vue'

const props = defineProps({
  plan: {
    type: Object,
    default: null,
  },
  mapGoals: {
    type: Array,
    default: () => [],
  },
  patrolStatus: {
    type: Object,
    default: () => ({ running: false, blocked_by: null }),
  },
  robot: {
    type: Object,
    default: () => ({ mode: 'manual', battery: 100 }),
  },
})

const emit = defineEmits(['plan-route', 'execute-plan-clear', 'cancel-plan', 'start-patrol', 'clear-blocked'])

// 默认选中第一个巡检点作为规划目标
const selectedGoalIndex = ref(0)

const planStatusLabel = computed(() => {
  if (!props.plan) return ''
  if (!props.plan.reachable) return '电量不足'
  if (!props.plan.enough) return '预算受限'
  return '电量充足'
})

const planStatusClass = computed(() => {
  if (!props.plan) return ''
  if (!props.plan.reachable) return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (!props.plan.enough) return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
  return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
})

function emitPlanRoute() {
  const goal = props.mapGoals[selectedGoalIndex.value]
  if (goal) {
    emit('plan-route', [goal[0], goal[1]])
  }
}
</script>
