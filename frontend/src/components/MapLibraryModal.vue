<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[65] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="$emit('close')" />
      <div
        class="relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl"
        role="dialog"
        aria-modal="true"
      >
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-base font-semibold">地图库</h3>
          <button type="button" class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
        </div>

        <!-- 顶部动作条 -->
        <div class="px-4 py-3 flex flex-wrap items-center gap-2 border-b border-gray-100 dark:border-gray-800">
          <button type="button" class="btn-primary" @click="saveCurrent">保存当前地图</button>
          <button type="button" class="btn-ghost" @click="$emit('open-designer', { blank: true })">新建并设计</button>
          <button type="button" class="btn-ghost" @click="$emit('open-designer', { blank: false })">编辑当前地图</button>
          <button type="button" class="btn-ghost" @click="triggerImport">导入 JSON</button>
          <button type="button" class="btn-ghost" @click="exportCurrent">导出当前地图</button>
          <input ref="fileRef" type="file" accept=".json,application/json" class="hidden" @change="onImport">
        </div>

        <!-- 标签 -->
        <div class="px-4 pt-3 flex gap-1">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            class="px-3 py-1.5 text-xs rounded-lg border"
            :class="active === tab.key
              ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
              : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'"
            :disabled="tab.key === 'cloud' && !cloudBase"
            :title="tab.key === 'cloud' && !cloudBase ? '当前是离线模式，连接后端后可用' : ''"
            @click="switchTab(tab.key)"
          >
            {{ tab.label }}<span class="ml-1 text-[10px] opacity-70">{{ tab.key === 'local' ? localItems.length : cloudItems.length }}</span>
          </button>
        </div>

        <!-- 列表 -->
        <div class="flex-1 overflow-y-auto px-4 py-3 space-y-2">
          <p v-if="loading" class="text-xs text-gray-400">加载中…</p>
          <p v-else-if="items.length === 0" class="text-xs text-gray-400 py-6 text-center">
            还没有保存的地图。点「保存当前地图」把现在的布局存下来，或「新建并设计地图」从空白开始画。
          </p>

          <div
            v-for="item in items"
            :key="item.id"
            class="flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 dark:border-gray-700"
          >
            <!-- 缩略图 -->
            <canvas :ref="(el) => setThumb(el, item)" class="w-16 h-11 rounded bg-gray-50 dark:bg-gray-800 shrink-0" />
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <input
                  v-if="editingId === item.id"
                  v-model="editingName"
                  class="px-1.5 py-0.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent w-40"
                  @keyup.enter="commitRename(item)"
                  @blur="commitRename(item)"
                >
                <span v-else class="text-sm font-medium truncate">{{ item.name }}</span>
                <button
                  v-if="editingId !== item.id"
                  type="button"
                  class="text-[11px] text-gray-400 hover:text-primary-600"
                  @click="startRename(item)"
                >
                  重命名
                </button>
              </div>
              <div class="text-[11px] text-gray-500 dark:text-gray-400">
                {{ item.width }}×{{ item.height }} · {{ item.goals || 0 }} 个巡检点 · {{ item.updated_at }}
                <span v-if="item.cloud" class="ml-1 text-[10px] px-1 rounded bg-blue-50 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300">云端</span>
              </div>
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              <button type="button" class="btn-xs-primary" @click="loadItem(item)">载入</button>
              <button type="button" class="btn-xs" @click="exportItem(item)">导出</button>
              <button type="button" class="btn-xs-danger" @click="removeItem(item)">删除</button>
            </div>
          </div>
        </div>

        <div class="px-4 py-2 border-t border-gray-100 dark:border-gray-800 text-[11px] text-gray-400">
          本机库存在浏览器里（换设备看不到）；云端库需要连接后端，任何设备都能取。
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 组件功能：地图库（V2.1）
 * 作者：智能巡检机器人二维仿真系统 V2.1 前端开发组
 * 日期：2026-10-27
 * 版本：V2.1
 *
 * 统一管理"保存 / 载入 / 重命名 / 删除 / 导入 / 导出 / 新建"，
 * 分本机库（localStorage）和云端库（后端 /api/v1/maps）两个来源。
 */

import { computed, ref, watch } from 'vue'
import { validateMap, exportMap } from '../utils/mapIO.js'
import {
  listLocal,
  saveLocal,
  removeLocal,
  renameLocal,
  listCloud,
  saveCloud,
  loadCloud,
  removeCloud,
} from '../services/mapLibrary.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  currentMap: { type: Object, required: true },
  // 后端基地址：空字符串表示同源后端；null 表示当前为离线模式
  cloudBase: { type: String, default: null },
})

const emit = defineEmits(['close', 'loaded', 'notify', 'open-designer'])

const tabs = [
  { key: 'local', label: '本机库' },
  { key: 'cloud', label: '云端库' },
]
const active = ref('local')
const localItems = ref([])
const cloudItems = ref([])
const loading = ref(false)
const editingId = ref(null)
const editingName = ref('')
const fileRef = ref(null)

const items = computed(() => (active.value === 'local' ? localItems.value : cloudItems.value))

function refreshLocal() {
  localItems.value = listLocal()
}

async function refreshCloud() {
  if (!props.cloudBase && props.cloudBase !== '') return
  loading.value = true
  try {
    const list = await listCloud(props.cloudBase || '')
    cloudItems.value = list.map((item) => ({ ...item, cloud: true }))
  } catch (error) {
    emit('notify', `云端地图列表读取失败：${error.message}`)
    cloudItems.value = []
  } finally {
    loading.value = false
  }
}

function switchTab(key) {
  active.value = key
  if (key === 'cloud') refreshCloud()
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      refreshLocal()
      active.value = 'local'
      editingId.value = null
      if (props.cloudBase !== null) refreshCloud()
    }
  }
)

/** 保存当前地图（本机必存，有后端时同时存云端）。 */
async function saveCurrent() {
  const name = window.prompt('给这张地图起个名字（同名会覆盖）', `地图 ${new Date().toLocaleDateString()}`)
  if (name === null) return
  const clean = name.trim() || '未命名地图'
  saveLocal(clean, props.currentMap)
  refreshLocal()
  if (props.cloudBase !== null) {
    try {
      await saveCloud(props.cloudBase || '', clean, props.currentMap)
      refreshCloud()
      emit('notify', `已保存到本机与云端：${clean}`)
    } catch (error) {
      emit('notify', `已存到本机；云端保存失败：${error.message}`)
    }
  } else {
    emit('notify', `已保存到本机：${clean}`)
  }
}

/** 载入某个条目。 */
async function loadItem(item) {
  try {
    let map = item.map
    if (!map && item.cloud) {
      const full = await loadCloud(props.cloudBase || '', item.id)
      map = full
    }
    const check = validateMap(map)
    if (!check.ok) {
      emit('notify', `载入失败：${check.error}`)
      return
    }
    emit('loaded', check.map)
  } catch (error) {
    emit('notify', `载入失败：${error.message}`)
  }
}

function startRename(item) {
  editingId.value = item.id
  editingName.value = item.name
}

async function commitRename(item) {
  const name = editingName.value.trim()
  editingId.value = null
  if (!name || name === item.name) return
  if (item.cloud) {
    try {
      await saveCloud(props.cloudBase || '', name, item.map || (await loadCloud(props.cloudBase || '', item.id)).map, item.id)
      refreshCloud()
    } catch (error) {
      emit('notify', `重命名失败：${error.message}`)
    }
  } else {
    renameLocal(item.id, name)
    refreshLocal()
  }
}

async function removeItem(item) {
  if (!window.confirm(`删除地图「${item.name}」？此操作不可撤销。`)) return
  if (item.cloud) {
    try {
      await removeCloud(props.cloudBase || '', item.id)
      refreshCloud()
    } catch (error) {
      emit('notify', `删除失败：${error.message}`)
    }
  } else {
    removeLocal(item.id)
    refreshLocal()
  }
}

function exportItem(item) {
  let map = item.map
  if (!map) {
    emit('notify', '云端条目请先载入后再导出')
    return
  }
  exportMap(map, item.name)
}

function exportCurrent() {
  exportMap(props.currentMap, 'current-map')
}

function triggerImport() {
  fileRef.value && fileRef.value.click()
}

/** 导入 JSON：先校验，再保存到本机库并载入。 */
async function onImport(event) {
  const file = event.target.files && event.target.files[0]
  event.target.value = ''
  if (!file) return
  try {
    const text = await file.text()
    const parsed = JSON.parse(text)
    const check = validateMap(parsed)
    if (!check.ok) {
      emit('notify', `导入失败：${check.error}`)
      return
    }
    const name = file.name.replace(/\.json$/i, '')
    saveLocal(name, check.map)
    refreshLocal()
    emit('loaded', check.map)
    emit('notify', `已导入并载入：${name}`)
  } catch (error) {
    emit('notify', `导入失败：${error.message}`)
  }
}

/** 绘制条目缩略图（16x11 的小方块图）。 */
function setThumb(el, item) {
  if (!el || !item.map) return
  const map = item.map
  const ctx = el.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  el.width = 64 * dpr
  el.height = 44 * dpr
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, 64, 44)
  const cw = 64 / map.width
  const ch = 44 / map.height
  for (let y = 0; y < map.height; y += 1) {
    for (let x = 0; x < map.width; x += 1) {
      const v = map.grid[y][x]
      if (v === 0) continue
      ctx.fillStyle = v === 2 ? '#0f172a' : '#94a3b8'
      ctx.fillRect(x * cw, y * ch, Math.ceil(cw), Math.ceil(ch))
    }
  }
}
</script>

<style scoped>
.btn-primary {
  @apply px-3 py-1.5 text-xs font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700;
}
.btn-ghost {
  @apply px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800;
}
.btn-xs {
  @apply px-2 py-1 text-[11px] rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800;
}
.btn-xs-primary {
  @apply px-2 py-1 text-[11px] rounded bg-primary-600 text-white hover:bg-primary-700;
}
.btn-xs-danger {
  @apply px-2 py-1 text-[11px] rounded border border-red-200 text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:text-red-400;
}
</style>
