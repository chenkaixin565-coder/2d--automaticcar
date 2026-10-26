<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="$emit('close')" />
      <div
        class="relative w-full max-w-sm rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
      >
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 id="auth-title" class="text-base font-semibold">
            {{ readonly ? '当前部署为只读模式' : '需要操作密钥' }}
          </h3>
        </div>
        <div class="p-4 space-y-3">
          <p class="text-sm text-gray-600 dark:text-gray-300">
            {{ readonly ? '该部署只允许查看状态，所有修改操作已被服务端拒绝。' : message }}
          </p>
          <template v-if="!readonly">
            <label class="block text-xs text-gray-500" for="operator-key">操作密钥（OPERATOR_KEY）</label>
            <input
              id="operator-key"
              v-model="key"
              type="password"
              autocomplete="off"
              class="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              placeholder="由部署方提供，仅保存在本标签页"
              @keyup.enter="submit"
            >
            <p class="text-[11px] text-gray-400">
              密钥只存在 sessionStorage，关闭标签页即失效；不会写进前端构建产物。
            </p>
          </template>
        </div>
        <div class="px-4 pb-4 flex gap-2 justify-end">
          <button
            type="button"
            class="px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
            @click="$emit('close')"
          >
            {{ readonly ? '知道了' : '仅浏览' }}
          </button>
          <button
            v-if="!readonly"
            type="button"
            class="px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
            :disabled="!key.trim()"
            @click="submit"
          >
            解锁操作
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：操作密钥输入弹窗（V2.2.0）
 * 作者：智能巡检机器人二维仿真系统 V2.2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.2.0
 *
 * 后端配置了 OPERATOR_KEY 后，写操作与 WebSocket 指令需要密钥。
 * 前端收到 401 / WS 4401 时弹出本窗口，密钥只存 sessionStorage。
 */

import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  message: { type: String, default: '该后端已开启操作鉴权，请填写密钥后重试。' },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['submit', 'close'])

const key = ref('')

watch(
  () => props.visible,
  (visible) => {
    if (visible) key.value = ''
  }
)

function submit() {
  const value = key.value.trim()
  if (!value) return
  emit('submit', value)
}
</script>
