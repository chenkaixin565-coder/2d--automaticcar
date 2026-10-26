<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <!-- 遮罩：点击不关闭，避免误触把机器人遗留在空电状态 -->
      <div class="absolute inset-0 bg-black/50" />
      <div
        class="relative w-full max-w-sm rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5 shadow-2xl"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="empty-battery-title"
      >
        <div class="flex items-center gap-2">
          <span class="flex items-center justify-center w-9 h-9 rounded-full bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="16" height="10" rx="2" /><path d="M22 11v2" /><path d="M6 11v2M10 11v2" /></svg>
          </span>
          <h3 id="empty-battery-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">电量耗尽</h3>
        </div>
        <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">
          机器人已经没有电了，请你将机器人搬回初始点
        </p>
        <p class="mt-1.5 text-xs text-gray-400 dark:text-gray-500">
          V2.0 起电量低于 20% 会自动返航充电；只有在充电点不可达、电量彻底耗尽时才会出现这个弹窗。
          选择“是”后将机器人送回初始点并恢复满电；选择“否”则留待后续处理（期间无法移动与清障）。
        </p>
        <div class="mt-4 flex gap-2">
          <button
            type="button"
            class="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700"
            @click="$emit('confirm')"
          >
            是
          </button>
          <button
            type="button"
            class="flex-1 px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
            @click="$emit('dismiss')"
          >
            否
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：空电搬回确认弹窗（V1.2）
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 *
 * 机器人电量耗尽时弹出：“机器人已经没有电了，请你将机器人搬回初始点”，
 * 用户选择“是”后才由服务层把机器人传送回起点并恢复满电；选择“否”仅关闭弹窗。
 */

defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['confirm', 'dismiss'])
</script>
