<template>
  <figure ref="root" class="chart">
    <figcaption v-if="series.length > 1" class="chart-legend">
      <span v-for="s in series" :key="s.key" class="legend-item">
        <i class="legend-key" :style="{ background: s.color }" />
        {{ s.label }}
        <b class="num">{{ format(lastValue(s)) }}</b>
      </span>
    </figcaption>

    <div
      class="chart-plot"
      tabindex="0"
      role="img"
      :aria-label="ariaLabel"
      @pointermove="onPointerMove"
      @pointerleave="active = null"
      @focus="active = dates.length - 1"
      @blur="active = null"
      @keydown="onKey"
    >
      <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`">
        <g v-for="t in ticks" :key="t">
          <line class="grid" :x1="PAD.left" :x2="width - PAD.right" :y1="y(t)" :y2="y(t)" />
          <text class="axis-text num" :x="width - PAD.right + 6" :y="y(t) + 4">{{ format(t) }}</text>
        </g>

        <path v-if="areaPath" class="area" :d="areaPath" :fill="series[0].color" />
        <path
          v-for="s in series"
          :key="s.key"
          class="line"
          :class="`line--${s.key}`"
          :d="pathOf(s)"
          :stroke="s.color"
        />

        <text
          v-for="i in xTicks"
          :key="`x-${i}`"
          class="axis-text num"
          :x="x(i)"
          :y="height - 6"
          :text-anchor="i === 0 ? 'start' : i === dates.length - 1 ? 'end' : 'middle'"
        >{{ shortDate(dates[i]) }}</text>

        <g v-if="active !== null">
          <line class="crosshair" :x1="x(active)" :x2="x(active)" :y1="PAD.top" :y2="height - PAD.bottom" />
          <template v-for="s in series" :key="`dot-${s.key}`">
            <circle
              v-if="isNum(s.values[active])"
              class="dot"
              :cx="x(active)"
              :cy="y(s.values[active])"
              r="4"
              :fill="s.color"
            />
          </template>
        </g>
      </svg>

      <div v-if="active !== null" class="chart-tip" :style="tipStyle">
        <div class="tip-date num">{{ dates[active] }}</div>
        <div v-for="s in series" :key="s.key" class="tip-row">
          <i class="tip-key" :style="{ background: s.color }" />
          <b class="num">{{ format(s.values[active]) }}</b>
          <span>{{ s.label }}</span>
        </div>
      </div>
    </div>

    <details class="chart-data">
      <summary>數據表</summary>
      <table>
        <thead>
          <tr><th>日期</th><th v-for="s in series" :key="s.key">{{ s.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in tableRows" :key="row.date">
            <td class="num">{{ row.date }}</td>
            <td v-for="(v, i) in row.values" :key="i" class="num">{{ format(v) }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </figure>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useChartWidth } from '../../composables/useChartWidth'
import { extent, linePath, niceTicks, slotIndex, tickIndexes } from '../../utils/chartScale'
import { shortDate } from '../../utils/format'

const props = defineProps({
  dates:  { type: Array, required: true },
  // [{key, label, color, values: (number|null)[]}] — one shared y-axis, always
  series: { type: Array, required: true },
  height: { type: Number, default: 200 },
  format: { type: Function, default: (v) => (v == null ? '—' : String(v)) },
  area:   { type: Boolean, default: false },
  title:  { type: String, default: '走勢圖' },
})

const PAD = { top: 8, right: 52, bottom: 22, left: 2 }
const TABLE_ROWS = 20

const { root, width } = useChartWidth()
const active = ref(null)
watch(() => props.dates, () => { active.value = null })

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const innerWidth = computed(() => Math.max(1, width.value - PAD.left - PAD.right))
const innerHeight = computed(() => Math.max(1, props.height - PAD.top - PAD.bottom))
const range = computed(() => extent(props.series.map(s => s.values)))
const ticks = computed(() => (range.value ? niceTicks(range.value[0], range.value[1]) : []))
const yMin = computed(() => ticks.value[0] ?? 0)
const yMax = computed(() => ticks.value[ticks.value.length - 1] ?? 1)
const xTicks = computed(() => tickIndexes(props.dates.length))

function x(i) {
  const n = props.dates.length
  return PAD.left + (n <= 1 ? innerWidth.value : (i / (n - 1)) * innerWidth.value)
}

function y(v) {
  const span = yMax.value - yMin.value || 1
  return PAD.top + (1 - (v - yMin.value) / span) * innerHeight.value
}

function pointsOf(s) {
  return s.values.map((v, i) => (isNum(v) ? { x: x(i), y: y(v) } : null))
}

function pathOf(s) {
  return linePath(pointsOf(s))
}

const areaPath = computed(() => {
  if (!props.area || !props.series.length) return ''
  const points = pointsOf(props.series[0]).filter(Boolean)
  if (points.length < 2) return ''
  const floor = (PAD.top + innerHeight.value).toFixed(1)
  return `${linePath(points)}L${points[points.length - 1].x.toFixed(1)} ${floor}L${points[0].x.toFixed(1)} ${floor}Z`
})

function lastValue(s) {
  for (let i = s.values.length - 1; i >= 0; i--) {
    if (isNum(s.values[i])) return s.values[i]
  }
  return null
}

const ariaLabel = computed(() => {
  const latest = props.series.map(s => `${s.label} ${props.format(lastValue(s))}`).join('，')
  return `${props.title}，${props.dates[0] ?? ''} 至 ${props.dates[props.dates.length - 1] ?? ''}，最新 ${latest}。方向鍵可逐日查看。`
})

const tipStyle = computed(() => {
  const px = x(active.value)
  return px > width.value / 2
    ? { right: `${width.value - px + 10}px` }
    : { left: `${px + 10}px` }
})

const tableRows = computed(() => {
  const start = Math.max(0, props.dates.length - TABLE_ROWS)
  return props.dates.slice(start).map((date, i) => ({
    date,
    values: props.series.map(s => s.values[start + i]),
  })).reverse()
})

function onPointerMove(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  active.value = slotIndex(e.clientX - rect.left, PAD.left, innerWidth.value, props.dates.length)
}

function onKey(e) {
  if (active.value === null) return
  const last = props.dates.length - 1
  if (e.key === 'ArrowLeft') active.value = Math.max(0, active.value - 1)
  else if (e.key === 'ArrowRight') active.value = Math.min(last, active.value + 1)
  else return
  e.preventDefault()
}
</script>

<style src="./chart.css"></style>
