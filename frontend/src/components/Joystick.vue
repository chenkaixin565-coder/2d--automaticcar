<template>
  <div class="flex flex-col items-center gap-2">
    <div
      ref="baseRef"
      class="relative w-32 h-32 rounded-full border-2 border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 touch-none select-none"
      @pointerdown="handlePointerDown"
      @pointermove="handlePointerMove"
      @pointerup="handlePointerUp"
      @pointerleave="handlePointerUp"
    >
      <div
        class="absolute top-1/2 left-1/2 w-12 h-12 -mt-6 -ml-6 rounded-full bg-primary-500 shadow-md transition-transform"
        :style="knobStyle"
      />
    </div>
    <span class="text-xs text-gray-500 dark:text-gray-400">虚拟摇杆</span>
  </div>
</template>

<script setup>
/**
 * 组件功能：移动端虚拟摇杆
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 在触摸屏上提供方向控制，持续按住时会以固定间隔向父组件发送方向指令。
 */

import { ref, computed, onUnmounted } from 'vue'

const emit = defineEmits(['move'])

const baseRef = ref(null)
const active = ref(false)
const dx = ref(0)
const dy = ref(0)
let emitInterval = null

const knobStyle = computed(() => ({
  transform: `translate(${dx.value * 30}px, ${dy.value * 30}px)`,
}))

function handlePointerDown(event) {
  event.preventDefault()
  active.value = true
  updateDirection(event)
  emitMove()
  emitInterval = setInterval(emitMove, 200)
}

function handlePointerMove(event) {
  if (!active.value) return
  event.preventDefault()
  updateDirection(event)
}

function handlePointerUp(event) {
  if (!active.value) return
  event.preventDefault()
  active.value = false
  dx.value = 0
  dy.value = 0
  if (emitInterval) {
    clearInterval(emitInterval)
    emitInterval = null
  }
}

function updateDirection(event) {
  const rect = baseRef.value.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  const rawDx = event.clientX - centerX
  const rawDy = event.clientY - centerY
  const distance = Math.sqrt(rawDx * rawDx + rawDy * rawDy)
  const maxDistance = rect.width / 2

  if (distance > maxDistance) {
    const ratio = maxDistance / distance
    dx.value = rawDx * ratio / maxDistance
    dy.value = rawDy * ratio / maxDistance
  } else {
    dx.value = rawDx / maxDistance
    dy.value = rawDy / maxDistance
  }
}

function emitMove() {
  const threshold = 0.3
  let moveDx = 0
  let moveDy = 0
  if (Math.abs(dx.value) > threshold) {
    moveDx = dx.value > 0 ? 1 : -1
  }
  if (Math.abs(dy.value) > threshold) {
    moveDy = dy.value > 0 ? 1 : -1
  }
  if (moveDx !== 0 || moveDy !== 0) {
    emit('move', { dx: moveDx, dy: moveDy })
  }
}

onUnmounted(() => {
  if (emitInterval) {
    clearInterval(emitInterval)
  }
})
</script>
