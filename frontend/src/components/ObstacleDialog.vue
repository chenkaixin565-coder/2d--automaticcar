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
          <h3 id="blocked-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">巡检受阻</h3>
        </div>

        <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">
          机器人已停在障碍前一格<span v-if="cell">（前方 <span class="font-mono">[{{ cell[0] }}, {{ cell[1] }}]</span>）</span>，
          需要你决定怎么处理。
        </p>

        <ul class="mt-2 text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <li>· 清除：扣 5% 电量，原地清除后继续巡检</li>
          <li>· 跳过：保留障碍并记入"待清障"，跳过当前巡检点</li>
          <li>· 停止：结束本次巡检，回到手动模式</li>
        </ul>

        <p class="mt-2 text-xs" :class="battery < clearCost ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'">
          当前电量 {{ battery.toFixed(1) }}%{{ battery < clearCost ? '，不足 5%，无法清除' : '' }}
        </p>

        <div class="mt-4 flex flex-col gap-2">
          <button
            type="button"
            class="w-full px-3 py-2 text-sm font-medium rounded-lg bg-orange-600 text-white hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="battery < clearCost"
            @click="$emit('decide', 'clear')"
          >
            清除此处障碍（-5%）并继续
          </button>
          <button
            type="button"
            class="w-full px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
            @click="$emit('decide', 'skip')"
          >
            跳过并记入待清障
          </button>
          <button
            type="button"
            class="w-full px-3 py-2 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            @click="$emit('decide', 'stop')"
          >
            停止巡检
          </button>
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

defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  cell: {
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
})

defineEmits(['decide'])
</script>
