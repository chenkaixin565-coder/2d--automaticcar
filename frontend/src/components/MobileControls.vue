<template>
  <div class="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3 safe-area-pb">
    <div class="flex items-center justify-between gap-3">
      <!-- 方向键 -->
      <div class="grid grid-cols-3 gap-1.5 shrink-0">
        <div />
        <button
          type="button"
          class="mctrl-btn"
          aria-label="前进"
          @click="emitMove(0, -1)"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
        </button>
        <div />
        <button
          type="button"
          class="mctrl-btn"
          aria-label="左转"
          @click="emitMove(-1, 0)"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        </button>
        <button
          type="button"
          class="mctrl-btn bg-gray-100 dark:bg-gray-800"
          aria-label="复位"
          @click="$emit('reset')"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></svg>
        </button>
        <button
          type="button"
          class="mctrl-btn"
          aria-label="右转"
          @click="emitMove(1, 0)"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
        </button>
        <div />
        <button
          type="button"
          class="mctrl-btn"
          aria-label="后退"
          @click="emitMove(0, 1)"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7" /></svg>
        </button>
        <div />
      </div>

      <!-- 编辑模式 + 巡检 -->
      <div class="flex-1 min-w-0 flex flex-col gap-2">
        <div class="flex gap-1 overflow-x-auto no-scrollbar">
          <button
            v-for="mode in editModes"
            :key="mode.key"
            type="button"
            class="shrink-0 px-2.5 py-1.5 text-[10px] rounded-md border transition-colors"
            :class="editMode === mode.key ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300'"
            @click="$emit('set-edit-mode', mode.key)"
          >
            {{ mode.label }}
          </button>
        </div>
        <div class="flex gap-2">
          <button
            type="button"
            class="flex-1 px-2 py-2 text-xs font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
            :disabled="patrolStatus.running"
            @click="$emit('start-patrol')"
          >
            开始巡检
          </button>
          <button
            type="button"
            class="flex-1 px-2 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 text-gray-700 dark:text-gray-200"
            :disabled="!patrolStatus.running"
            @click="$emit('stop-patrol')"
          >
            停止
          </button>
          <button
            type="button"
            class="flex-1 px-2 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
            @click="$emit('open-plan')"
          >
            规划路线
          </button>
        </div>
        <div class="flex gap-2">
          <button
            type="button"
            class="flex-1 px-2 py-1.5 text-xs rounded-lg border transition-colors"
            :class="robot.mode === 'blocked'
              ? 'border-red-500 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
              : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300'"
            @click="$emit('resolve-fault')"
          >
            排障
          </button>
          <button
            type="button"
            class="flex-1 px-2 py-1.5 text-xs rounded-lg border border-primary-200 dark:border-primary-800 text-primary-700 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20"
            title="保存 / 载入 / 导入导出 / 新建地图"
            @click="$emit('open-library')"
          >
            📚 地图库
          </button>
          <button
            type="button"
            class="flex-1 px-2 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
            @click="$emit('toggle-detail')"
          >
            {{ detailOpen ? '收起详情' : '更多详情' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：移动端底部快捷控制条
 * 作者：智能巡检机器人二维仿真系统 V1.2 前端开发组
 * 日期：2026-10-25
 * 版本：V1.2
 */

defineProps({
  robot: { type: Object, required: true },
  patrolStatus: { type: Object, required: true },
  editMode: { type: String, default: 'nav' },
  detailOpen: { type: Boolean, default: false },
})

const emit = defineEmits([
  'move',
  'reset',
  'resolve-fault',
  'start-patrol',
  'stop-patrol',
  'set-edit-mode',
  'fit-map',
  'toggle-detail',
  'open-plan',
  'open-library',
])

const editModes = [
  { key: 'obstacle', label: '障碍' },
  { key: 'barrier', label: '屏障' },
  { key: 'erase', label: '擦除' },
  { key: 'goal', label: '巡检点' },
  { key: 'start', label: '起点' },
  { key: 'charge', label: '充电' },
]

function emitMove(dx, dy) {
  emit('move', { dx, dy })
}
</script>

<style scoped>
.mctrl-btn {
  @apply flex items-center justify-center w-9 h-9 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200 active:bg-gray-100 dark:active:bg-gray-800 transition-colors;
}
.safe-area-pb {
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
}
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
