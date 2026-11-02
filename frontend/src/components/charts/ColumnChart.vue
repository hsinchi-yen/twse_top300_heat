<template>
  <figure ref="root" class="chart">
    <div
      class="chart-plot"
      tabindex="0"
      role="img"
      :aria-label="ariaLabel"
      @pointermove="onPointerMove"
      @pointerleave="active = null"
      @focus="active = values.length - 1"
      @blur="active = null"
      @keydown="onKey"
    >
      <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`">
        <g v-for="t in ticks" :key="t">
          <line class="grid" :class="{ baseline: t === 0 }" :x1="PAD.left" :x2="width - PAD.right" :y1="y(t)" :y2="y(t)" />
          <text class="axis-text num" :x="width - PAD.right + 6" :y="y(t) + 4">{{ format(t) }}</text>
        </g>

        <path
          v-for="bar in bars"
          :key="bar.i"
          class="column"
          :class="{ dim: active !== null && active !== bar.i }"
          :d="bar.d"
          :fill="bar.fill"
        />

        <text
          v-for="i in xTicks"
          :key="`x-${i}`"
          class="axis-text num"
          :x="center(i)"
          :y="height - 6"
          :text-anchor="i === 0 ? 'start' : i === values.length - 1 ? 'end' : 'middle'"
        >{{ shortDate(dates[i]) }}</text>
      </svg>

      <div v-if="active !== null" class="chart-tip" :style="tipStyle">
        <div class="tip-date num">{{ dates[active] }}</div>
        <div class="tip-row">
          <b class="num">{{ format(values[active]) }}</b>
          <span>{{ label }}</span>
        </div>
      </div>
    </div>

    <details class="chart-data">
      <summary>數據表</summary>
      <table>
        <thead><tr><th>日期</th><th>{{ label }}</th></tr></thead>
        <tbody>
          <tr v-for="row in tableRows" :key="row.date">
            <td class="num">{{ row.date }}</td>
            <td class="num">{{ format(row.value) }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </figure>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useChartWidth } from '../../composables/useChartWidth'
import { niceTicks, slotIndex, tickIndexes } from '../../utils/chartScale'
import { shortDate } from '../../utils/format'

const props = defineProps({
  dates:  { type: Array, required: true },
  values: { type: Array, required: true },
  label:  { type: String, required: true },
  height: { type: Number, default: 120 },
  format: { type: Function, default: (v) => (v == null ? '—' : String(v)) },
  // 'direction': above zero = up colour, below = down colour; 'neutral': one colour
  tone:   { type: String, default: 'neutral' },
})

const PAD = { top: 8, right: 52, bottom: 22, left: 2 }
const MAX_BAR = 24
const CORNER = 4
const TABLE_ROWS = 20

const { root, width } = useChartWidth()
const active = ref(null)
watch(() => props.dates, () => { active.value = null })

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const innerWidth = computed(() => Math.max(1, width.value - PAD.left - PAD.right))
const innerHeight = computed(() => Math.max(1, props.height - PAD.top - PAD.bottom))

const ticks = computed(() => {
  const numbers = props.values.filter(isNum)
  if (!numbers.length) return []
  // Always include the zero baseline the bars grow from.
  return niceTicks(Math.min(0, ...numbers), Math.max(0, ...numbers), 3)
})
const yMin = computed(() => ticks.value[0] ?? 0)
const yMax = computed(() => ticks.value[ticks.value.length - 1] ?? 1)
const xTicks = computed(() => tickIndexes(props.values.length))

function y(v) {
  const span = yMax.value - yMin.value || 1
  return PAD.top + (1 - (v - yMin.value) / span) * innerHeight.value
}

const slot = computed(() => innerWidth.value / Math.max(1, props.values.length))

function center(i) {
  return PAD.left + slot.value * (i + 0.5)
}

function columnPath(cx, barWidth, top, bottom, roundTop) {
  const left = cx - barWidth / 2
  const right = cx + barWidth / 2
  const r = Math.min(CORNER, barWidth / 2, Math.abs(bottom - top))
  // Round only the data end; the baseline end stays square.
  if (r < 1) return `M${left} ${top}H${right}V${bottom}H${left}Z`
  return roundTop
    ? `M${left} ${bottom}V${top + r}Q${left} ${top} ${left + r} ${top}H${right - r}Q${right} ${top} ${right} ${top + r}V${bottom}Z`
    : `M${left} ${top}V${bottom - r}Q${left} ${bottom} ${left + r} ${bottom}H${right - r}Q${right} ${bottom} ${right} ${bottom - r}V${top}Z`
}

const bars = computed(() => {
  const gap = slot.value > 4 ? 2 : 0.5
  const barWidth = Math.min(MAX_BAR, Math.max(0.75, slot.value - gap))
  const zero = y(0)
  const out = []
  props.values.forEach((v, i) => {
    if (!isNum(v) || v === 0) return
    const top = Math.min(y(v), zero)
    const bottom = Math.max(y(v), zero)
    const fill = props.tone === 'direction'
      ? (v > 0 ? 'var(--pct-up)' : 'var(--pct-down)')
      : 'var(--chart-neutral)'
    out.push({ i, fill, d: columnPath(center(i), barWidth, top, bottom, v > 0) })
  })
  return out
})

const ariaLabel = computed(() => {
  const n = props.values.length
  return `${props.label}，${props.dates[0] ?? ''} 至 ${props.dates[n - 1] ?? ''}，最新 ${props.format(props.values[n - 1])}。方向鍵可逐日查看。`
})

const tipStyle = computed(() => {
  const px = center(active.value)
  return px > width.value / 2
    ? { right: `${width.value - px + 10}px` }
    : { left: `${px + 10}px` }
})

const tableRows = computed(() => {
  const start = Math.max(0, props.values.length - TABLE_ROWS)
  return props.values.slice(start).map((value, i) => ({ date: props.dates[start + i], value })).reverse()
})

function onPointerMove(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const x = e.clientX - rect.left - slot.value / 2
  active.value = slotIndex(x, PAD.left, innerWidth.value - slot.value, props.values.length)
}

function onKey(e) {
  if (active.value === null) return
  const last = props.values.length - 1
  if (e.key === 'ArrowLeft') active.value = Math.max(0, active.value - 1)
  else if (e.key === 'ArrowRight') active.value = Math.min(last, active.value + 1)
  else return
  e.preventDefault()
}
</script>

<style src="./chart.css"></style>
