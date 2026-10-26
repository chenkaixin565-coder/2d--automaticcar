<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed z-[70] rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl"
      :style="{ left: `${pos.x}px`, top: `${pos.y}px`, width: `${width}px` }"
    >
      <!-- 拖动条：按住这里可以拖到屏幕任意位置 -->
      <div
        class="flex items-center justify-between gap-2 px-3 py-2 rounded-t-xl bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 cursor-move select-none touch-none"
        @pointerdown="startDrag"
      >
        <div class="flex items-center gap-2 min-w-0">
          <slot name="icon" />
          <span class="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{{ title }}</span>
        </div>
        <div class="flex items-center gap-1">
          <button
            type="button"
            class="px-1.5 py-0.5 text-xs rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500"
            :title="minimized ? '展开' : '收起'"
            @pointerdown.stop
            @click="minimized = !minimized"
          >
            {{ minimized ? '▢' : '—' }}
          </button>
          <button
            type="button"
            class="px-1.5 py-0.5 text-xs rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500"
            title="关闭"
            @pointerdown.stop
            @click="$emit('close')"
          >
            ✕
          </button>
        </div>
      </div>
      <div v-show="!minimized" class="p-3">
        <slot />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：可拖动浮层（V2.1）
 * 作者：智能巡检机器人二维仿真系统 V2.1 前端开发组
 * 日期：2026-10-27
 * 版本：V2.1
 *
 * 用于"规划预览""移动端详情"等需要悬浮且能随手挪开的窗口。
 * 按住标题栏拖动，位置限制在视口内；可最小化为只剩标题栏。
 */

import { onMounted, reactive, ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: Number, default: 320 },
})

defineEmits(['close'])

const minimized = ref(false)
const pos = reactive({ x: 0, y: 0 })
const dragOffset = reactive({ x: 0, y: 0 })

/** 把位置限制在可视区域内，避免拖出屏幕后找不回来。 */
function clamp() {
  const maxX = Math.max(8, window.innerWidth - props.width - 8)
  const maxY = Math.max(8, window.innerHeight - 80)
  pos.x = Math.min(Math.max(8, pos.x), maxX)
  pos.y = Math.min(Math.max(8, pos.y), maxY)
}

/** 初始位置：桌面靠右下，手机靠底部居中。 */
function resetPosition() {
  if (window.innerWidth < 768) {
    pos.x = Math.max(8, (window.innerWidth - props.width) / 2)
    pos.y = Math.max(80, window.innerHeight * 0.42)
  } else {
    // 桌面端默认靠左下：不挡右侧控制面板，也不压住地图中央的路线
    pos.x = 24
    pos.y = Math.max(96, window.innerHeight - 380)
  }
  clamp()
}

function startDrag(event) {
  event.preventDefault()
  dragOffset.x = event.clientX - pos.x
  dragOffset.y = event.clientY - pos.y
  window.addEventListener('pointermove', onDrag)
  window.addEventListener('pointerup', stopDrag, { once: true })
}

function onDrag(event) {
  pos.x = event.clientX - dragOffset.x
  pos.y = event.clientY - dragOffset.y
  clamp()
}

function stopDrag() {
  window.removeEventListener('pointermove', onDrag)
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      minimized.value = false
      resetPosition()
    }
  }
)

onMounted(() => {
  if (props.visible) resetPosition()
})
</script>
