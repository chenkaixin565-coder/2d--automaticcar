<template>
  <div class="flex flex-col gap-2.5 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
        <svg class="w-4 h-4 text-primary-600 dark:text-primary-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.4L12 15l-1.9-4.6L5.5 9l4.6-1.4z" />
          <path d="M18 15l.9 2.1L21 18l-2.1.9L18 21l-.9-2.1L15 18l2.1-.9z" />
        </svg>
        智能指令
      </h2>
      <span
        class="px-2 py-0.5 text-[10px] rounded-full"
        :class="backend
          ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300'
          : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'"
      >
        {{ backend ? '后端解析' : '离线规则' }}
      </span>
    </div>

    <!-- 对话记录 -->
    <div
      v-if="entries.length > 0"
      ref="listRef"
      class="flex flex-col gap-1.5 max-h-44 overflow-y-auto pr-1"
    >
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="rounded-lg px-2.5 py-1.5 text-xs leading-relaxed"
        :class="entry.role === 'user'
          ? 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 self-end max-w-[90%]'
          : entry.ok
            ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-800 dark:text-emerald-200 border border-emerald-100 dark:border-emerald-900/40'
            : 'bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 border border-amber-100 dark:border-amber-900/40'"
      >
        <div>{{ entry.message }}</div>
        <div v-if="entry.tool" class="mt-0.5 text-[10px] opacity-70 font-mono">
          {{ entry.tool }}<span v-if="entry.latency !== undefined"> · {{ entry.latency }}ms</span>
          <span v-if="entry.source === 'llm'"> · 本地大模型</span>
          <span v-else-if="entry.source === 'rule-fallback'"> · 规则兜底</span>
        </div>
      </div>
    </div>

    <!-- 二次确认 -->
    <div
      v-if="pending"
      class="rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/20 p-2 space-y-1.5"
    >
      <p class="text-xs text-amber-700 dark:text-amber-300">{{ pending.message }}</p>
      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
          :disabled="busy"
          @click="confirmPending"
        >
          确认执行
        </button>
        <button
          type="button"
          class="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          :disabled="busy"
          @click="pending = null"
        >
          取消
        </button>
      </div>
    </div>

    <!-- 输入框 -->
    <form class="flex gap-1.5" @submit.prevent="send()">
      <input
        v-model="text"
        type="text"
        maxlength="200"
        class="flex-1 min-w-0 px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 text-gray-800 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
        placeholder="说一句话，例如：去 5,5 巡检"
        aria-label="自然语言指令"
        :disabled="busy"
      >
      <button
        type="submit"
        class="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="busy || text.trim().length === 0"
      >
        {{ busy ? '…' : '发送' }}
      </button>
    </form>

    <!-- 示例 -->
    <div class="flex flex-wrap gap-1">
      <button
        v-for="example in examples"
        :key="example"
        type="button"
        class="px-2 py-0.5 text-[10px] rounded-full border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200"
        :disabled="busy"
        @click="send(example)"
      >
        {{ example }}
      </button>
    </div>
    <p class="text-[10px] text-gray-400 dark:text-gray-500 leading-snug">
      只支持白名单动作：规划 / 巡检 / 停止 / 回充 / 移动 / 清障 / 改格子 / 复位 / 新建地图。
      清障、改图、复位会先要求确认。
    </p>
  </div>
</template>

<script setup>
/**
 * 组件功能：自然语言指令面板（V2.3.0 Agent）
 * 作者：智能巡检机器人二维仿真系统 V2.3.0 前端开发组
 * 日期：2026-10-30
 * 版本：V2.3.0
 *
 * 把用户的一句话交给数据服务层：后端模式走 /api/v1/agent/command，
 * 离线模式走本地规则解析器。组件本身不关心解析细节，只负责展示
 * "听成了什么工具、执行了没有、结果是什么"。
 */

import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  /** 数据服务实例（SimulatedService / RemoteService）。 */
  service: { type: Object, required: true },
  /** 是否连接了后端（仅用于角标文案）。 */
  backend: { type: Boolean, default: false },
})

const emit = defineEmits(['notify', 'map-updated'])

/** 输入框内容。 */
const text = ref('')
/** 请求进行中。 */
const busy = ref(false)
/** 待确认的破坏性操作：{ text, message }。 */
const pending = ref(null)
/** 对话记录（最多保留 6 条）。 */
const entries = ref([])
/** 记录容器引用，用于自动滚到底部。 */
const listRef = ref(null)
let entryId = 0

/** 示例指令：结合当前是否连后端给出不同提示。 */
const examples = computed(() =>
  props.backend
    ? ['去 5,5 巡检', '回充电点', '现在状态怎么样']
    : ['去 5,5 巡检', '把 3,4 的障碍清掉', '现在状态怎么样']
)

/**
 * 追加一条对话记录并滚动到底部。
 *
 * @param {Object} entry - { role, message, ok, tool, source, latency }。
 */
async function pushEntry(entry) {
  entries.value.push({ id: (entryId += 1), ...entry })
  if (entries.value.length > 6) entries.value.splice(0, entries.value.length - 6)
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

/**
 * 发送一条指令。
 *
 * @param {string} [raw] - 指定文本（点击示例时使用），缺省取输入框内容。
 */
async function send(raw) {
  const content = (raw === undefined ? text.value : raw).trim()
  if (!content || busy.value) return

  text.value = ''
  pending.value = null
  busy.value = true
  await pushEntry({ role: 'user', message: content, ok: true })

  try {
    const result = await props.service.sendAgentCommand(content, false)
    await applyResult(content, result)
  } catch (error) {
    await pushEntry({
      role: 'agent',
      message: `指令执行失败：${error && error.message ? error.message : '未知错误'}`,
      ok: false,
    })
    emit('notify', { type: 'stuck', message: '智能指令执行失败，请检查后端连接或操作密钥' })
  } finally {
    busy.value = false
  }
}

/**
 * 处理服务层返回的 Agent 结果：待确认的挂起，其余直接展示。
 *
 * @param {string} content - 原始指令。
 * @param {Object} result - 服务层返回体。
 */
async function applyResult(content, result) {
  if (!result) return
  if (result.need_confirm) {
    pending.value = { text: content, message: result.message }
    return
  }
  await pushEntry({
    role: 'agent',
    message: result.message,
    ok: Boolean(result.ok),
    tool: result.tool,
    source: result.source,
    latency: result.latency_ms,
  })
  if (result.executed && result.ok) {
    emit('notify', { type: 'notice', message: result.message })
    await syncMap()
  }
}

/**
 * 指令可能改了地图（清障 / 改格子 / 新建地图），执行后向服务层重新拉一份，
 * 交给 App 覆盖本地响应式地图；否则离线模式下新建地图后画布还停在旧图。
 */
async function syncMap() {
  if (typeof props.service.fetchMap !== 'function') return
  try {
    const fresh = await props.service.fetchMap()
    if (fresh && fresh.grid) emit('map-updated', fresh)
  } catch (error) {
    console.warn('Agent 指令后刷新地图失败：', error)
  }
}

/**
 * 确认执行挂起的破坏性操作。
 */
async function confirmPending() {
  if (!pending.value || busy.value) return
  const { text: content } = pending.value
  pending.value = null
  busy.value = true
  try {
    const result = await props.service.sendAgentCommand(content, true)
    await applyResult(content, result)
  } catch (error) {
    await pushEntry({
      role: 'agent',
      message: `确认执行失败：${error && error.message ? error.message : '未知错误'}`,
      ok: false,
    })
  } finally {
    busy.value = false
  }
}
</script>
