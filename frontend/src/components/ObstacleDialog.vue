<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" />
      <div
        class="relative w-full max-w-sm rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5 shadow-2xl"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="blocked-title"
      >
        <div class="flex items-center gap-2">
          <span class="flex items-center justify-center w-9 h-9 rounded-full bg-orange-100 text-orange-600 dark:bg-orange-900/40 dark:text-orange-400">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 9v4M12 17h.01" /><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
            </svg>
          </span>
          <h3 id="blocked-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">
            {{ isChargeUnreachable ? '无法返回充电点' : (isUnreachable ? '无法到达巡检点' : '巡检受阻') }}
          </h3>
        </div>

        <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">
          <template v-if="isChargeUnreachable">
            电量不足，返航路线又被挡住了，机器人无法自行回到充电点
            <span v-if="goal" class="font-mono">[{{ goal[0] }}, {{ goal[1] }}]</span>。
            请用「擦除」清掉挡路障碍（擦除不耗电），清完后会自动继续返航。
          </template>
          <template v-else-if="isUnreachable && !cell">
            到巡检点 <span v-if="goal" class="font-mono">[{{ goal[0] }}, {{ goal[1] }}]</span> 没有可行路线：
            它被<strong>固定屏障或地图边界</strong>完全围住了，清掉普通障碍也打不通。
            请跳过这个点，或到「擦除」模式清掉屏障。
          </template>
          <template v-else-if="isUnreachable">
            到巡检点 <span v-if="goal" class="font-mono">[{{ goal[0] }}, {{ goal[1] }}]</span> 没有可行路线，
            机器人停在原地等你决定。
          </template>
          <template v-else>
            机器人已停在障碍前一格<span v-if="cell">（前方 <span class="font-mono">[{{ cell[0] }}, {{ cell[1] }}]</span>）</span>，
            需要你决定怎么处理。
          </template>
        </p>

        <ul v-if="!isChargeUnreachable && !(isUnreachable && !cell)" class="mt-2 text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <li v-if="isUnreachable">· 清除：扣 {{ clearCost }}% 电量拆掉 {{ cellCount || 1 }} 处障碍，重新规划后继续</li>
          <li v-else>· 清除：扣 {{ clearCost }}% 电量，原地清除后继续巡检</li>
          <li>· 跳过：保留障碍并记入"待清障"，跳过当前巡检点</li>
          <li>· 停止：结束本次巡检，回到手动模式</li>
        </ul>

        <ul v-if="isUnreachable && !cell" class="mt-2 text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <li>· 跳过：放弃这个巡检点，继续下一个</li>
          <li>· 擦除：停止巡检并切到「擦除」模式，手动拆掉屏障</li>
        </ul>

        <p class="mt-2 text-xs" :class="battery < clearCost ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'">
          当前电量 {{ battery.toFixed(1) }}%{{ battery < clearCost ? `，不足 ${clearCost}%，无法清除` : '' }}
        </p>

        <div class="mt-4 flex flex-col gap-2">
          <template v-if="isChargeUnreachable">
            <button
              type="button"
              class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700"
              @click="$emit('decide', 'erase')"
            >
              去擦除挡路障碍
            </button>
            <button
              type="button"
              class="w-full px-3 py-2 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              @click="$emit('decide', 'stop')"
            >
              停止返航
            </button>
          </template>
          <template v-else-if="isUnreachable && !cell">
            <button
              type="button"
              class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="!canSkip"
              :title="canSkip ? '跳过这个巡检点，继续下一个' : '后面没有可达的巡检点了'"
              @click="$emit('decide', 'skip')"
            >
              跳过这个巡检点
            </button>
            <p v-if="!canSkip" class="text-xs text-amber-600 dark:text-amber-400">
              后面的巡检点都被挡住，跳过也没用；请先清理或停止巡检。
            </p>
            <button
              type="button"
              class="w-full px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
              @click="$emit('decide', 'edit-barriers')"
            >
              停止巡检并去擦除屏障
            </button>
            <button
              type="button"
              class="w-full px-3 py-2 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              @click="$emit('decide', 'stop')"
            >
              停止巡检
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-orange-600 text-white hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="battery < clearCost || cellCount === 0"
              @click="$emit('decide', 'clear')"
            >
              清除{{ isUnreachable ? `这 ${cellCount} 处障碍并重新规划` : '此处障碍' }}（-{{ clearCost }}%）并继续
            </button>
            <button
              type="button"
              class="w-full px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="!canSkip"
              :title="canSkip ? '跳过并把这些障碍记入待清障' : '后面没有可达的巡检点了'"
              @click="$emit('decide', 'skip')"
            >
              跳过并记入待清障
            </button>
            <p v-if="!canSkip" class="text-xs text-amber-600 dark:text-amber-400">
              后面的巡检点都被挡住，跳过也到不了；请先清理或停止巡检。
            </p>
            <button
              type="button"
              class="w-full px-3 py-2 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              @click="$emit('decide', 'stop')"
            >
              停止巡检
            </button>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：巡检遇阻决策弹窗（V2.0）
 * 作者：智能巡检机器人二维仿真系统 V2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.0
 *
 * 巡检停在障碍前一格后弹出，提供三种决策：
 *   clear = 清除该障碍并继续巡检（扣 5% 电量）
 *   skip  = 跳过当前巡检点，把障碍记入待清障记录
 *   stop  = 结束本次巡检
 */

import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  cell: {
    type: Array,
    default: null,
  },
  /** 阻碍原因：obstacle / barrier / unreachable（V2.3.1）。 */
  reason: {
    type: String,
    default: '',
  },
  /** 不可达时的目标巡检点坐标（V2.3.1）。 */
  goal: {
    type: Array,
    default: null,
  },
  battery: {
    type: Number,
    default: 100,
  },
  clearCost: {
    type: Number,
    default: 5,
  },
  // 本次需要清除几处（V2.5.4：可能是一整批，比如目标四周被石头围住）
  cellCount: {
    type: Number,
    default: 0,
  },
  // 跳过是否还有意义：后面没有可达巡检点时置 false（V2.6.0）
  canSkip: {
    type: Boolean,
    default: true,
  },
})

/** 目标完全不可达时换一套文案：不是"前方挡路"，而是"整条路被封死"。 */
const isUnreachable = computed(() => props.reason === 'unreachable')
/** V2.5：返航路线被封死，只能人工搬回或结束返航。 */
const isChargeUnreachable = computed(() => props.reason === 'charge_unreachable')

defineEmits(['decide'])
</script>
