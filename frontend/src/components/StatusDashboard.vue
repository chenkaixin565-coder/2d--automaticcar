<template>
  <div class="flex flex-col gap-4 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
    <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">状态仪表盘</h2>

    <div class="grid grid-cols-2 gap-3 text-sm">
      <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
        <span class="text-gray-500 dark:text-gray-400">坐标</span>
        <div class="font-mono text-gray-900 dark:text-gray-100">{{ robot.x }}, {{ robot.y }}</div>
      </div>
      <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
        <span class="text-gray-500 dark:text-gray-400">朝向</span>
        <div class="font-mono text-gray-900 dark:text-gray-100">{{ thetaDegrees }}°</div>
      </div>
      <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
        <span class="text-gray-500 dark:text-gray-400">速度</span>
        <div class="font-mono text-gray-900 dark:text-gray-100">{{ robot.speed.toFixed(2) }} m/s</div>
      </div>
      <div class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
        <span class="text-gray-500 dark:text-gray-400">模式</span>
        <div class="font-medium text-gray-900 dark:text-gray-100">{{ robot.mode }}</div>
      </div>
    </div>

    <!-- 电量 -->
    <div class="space-y-1">
      <div class="flex justify-between text-xs">
        <span class="text-gray-600 dark:text-gray-300">电量</span>
        <span :class="batteryClass">{{ robot.battery.toFixed(1) }}%</span>
      </div>
      <div class="h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
        <div
          class="h-full rounded-full transition-all"
          :class="batteryBarClass"
          :style="{ width: `${Math.max(0, Math.min(100, robot.battery))}%` }"
        />
      </div>
    </div>

    <!-- 三向距离 -->
    <div class="grid grid-cols-3 gap-2">
      <div
        v-for="name in sensorNames"
        :key="name.key"
        class="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 text-center"
      >
        <div class="text-xs text-gray-500 dark:text-gray-400">{{ name.label }}</div>
        <div class="font-mono text-sm font-medium text-gray-900 dark:text-gray-100">
          {{ formatDistance(robot.sensors[name.key]) }}
        </div>
        <div class="h-1.5 mt-1 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            class="h-full bg-primary-500 rounded-full"
            :style="{ width: `${sensorPercent(robot.sensors[name.key])}%` }"
          />
        </div>
      </div>
    </div>

    <!-- 温度曲线 -->
    <div>
      <div class="flex justify-between text-xs mb-1">
        <span class="text-gray-600 dark:text-gray-300">温度趋势（最近 60 秒）</span>
        <span class="font-mono" :class="tempClass">{{ robot.sensors.temperature.toFixed(1) }}℃</span>
      </div>
      <canvas
        ref="chartRef"
        class="w-full h-24 rounded-lg bg-gray-50 dark:bg-gray-800"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 组件功能：状态仪表盘
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 展示机器人坐标、电量、模式、三向传感器距离以及最近 60 秒温度折线图。
 */

import { computed, watch, ref, onMounted } from 'vue'

const props = defineProps({
  robot: {
    type: Object,
    required: true,
  },
  temperatureHistory: {
    type: Array,
    default: () => [],
  },
})

const chartRef = ref(null)

const sensorNames = [
  { key: 'front', label: '前向' },
  { key: 'left', label: '左侧' },
  { key: 'right', label: '右侧' },
]

const thetaDegrees = computed(() => {
  let deg = (props.robot.theta * 180) / Math.PI
  deg = ((deg % 360) + 360) % 360
  return Math.round(deg)
})

const batteryClass = computed(() => {
  return props.robot.battery < 20 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-700 dark:text-gray-200'
})

const batteryBarClass = computed(() => {
  if (props.robot.battery < 20) return 'bg-red-500'
  if (props.robot.battery < 50) return 'bg-yellow-500'
  return 'bg-green-500'
})

const tempClass = computed(() => {
  return props.robot.sensors.temperature > 60 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-700 dark:text-gray-200'
})

function formatDistance(value) {
  if (value === null || value === undefined) return '>5m'
  return `${value.toFixed(2)}m`
}

function sensorPercent(value) {
  if (value === null || value === undefined) return 100
  return Math.min(100, (value / 5) * 100)
}

onMounted(() => drawChart())
watch(() => [props.temperatureHistory, props.robot.sensors.temperature], () => drawChart(), { deep: true })

function drawChart() {
  const canvas = chartRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.floor(rect.width * dpr))
  canvas.height = Math.max(1, Math.floor(rect.height * dpr))

  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.save()
  ctx.scale(dpr, dpr)

  const width = rect.width
  const height = rect.height
  const padding = { top: 8, right: 8, bottom: 16, left: 28 }
  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const data = props.temperatureHistory.length > 0 ? props.temperatureHistory : [35]
  const minTemp = 30
  const maxTemp = 70

  // 坐标轴
  ctx.strokeStyle = '#9ca3af'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(padding.left, padding.top)
  ctx.lineTo(padding.left, height - padding.bottom)
  ctx.lineTo(width - padding.right, height - padding.bottom)
  ctx.stroke()

  // Y 轴刻度
  ctx.fillStyle = '#6b7280'
  ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  for (const t of [30, 40, 50, 60, 70]) {
    const y = height - padding.bottom - ((t - minTemp) / (maxTemp - minTemp)) * chartH
    ctx.fillText(String(t), padding.left - 4, y)
  }

  // 温度折线
  ctx.strokeStyle = '#ef4444'
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  ctx.beginPath()
  data.forEach((value, index) => {
    const x = padding.left + (index / (Math.max(1, data.length - 1))) * chartW
    const y = height - padding.bottom - ((value - minTemp) / (maxTemp - minTemp)) * chartH
    if (index === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
  })
  ctx.stroke()

  // 60℃ 警示线
  const warnY = height - padding.bottom - ((60 - minTemp) / (maxTemp - minTemp)) * chartH
  ctx.strokeStyle = '#f87171'
  ctx.setLineDash([4, 4])
  ctx.beginPath()
  ctx.moveTo(padding.left, warnY)
  ctx.lineTo(width - padding.right, warnY)
  ctx.stroke()
  ctx.setLineDash([])

  ctx.restore()
}
</script>
