<template>
  <div
    class="stock-cell"
    :class="{ 'cell-highlighted': highlighted }"
    :data-tier="stock.color_tier"
    :data-signal="tintSignal ?? undefined"
    :style="cellStyle"
    :title="tooltip"
    @pointerdown="onPressStart"
    @pointermove="onPressMove"
    @contextmenu="pinnable && $event.preventDefault()"
    @pointerup="cancelPress"
    @pointercancel="cancelPress"
    @pointerleave="cancelPress"
  >
    <!-- 窄卡片：訊號改為左緣色條（container query 切換） -->
    <span v-if="signal" class="cell-signal-bar" :data-signal="signal" />

    <!-- 頂部：排名 + 題材 + 訊號徽章 -->
    <div class="cell-top">
      <span class="cell-rank num">#{{ stock.rank }}</span>
      <span class="cell-sector">{{ stock.sector }}</span>
      <span v-if="sigLabel" class="cell-signal" :data-signal="signal">{{ sigLabel }}</span>
      <button
        v-if="pinnable"
        class="cell-pin"
        :class="{ 'is-pinned': pinned }"
        :title="pinned ? '移出自選' : '加入自選'"
        :aria-pressed="pinned"
        @click.stop="emit('toggle-pin', stock.stock_id)"
      >{{ pinned ? '★' : '☆' }}</button>
    </div>

    <!-- 名稱 + 代號 -->
    <div class="cell-name">
      <span class="cell-name-text">{{ stock.name }}</span>
      <span class="cell-code num">{{ stock.stock_id }}</span>
    </div>

    <!-- 主指標：評分模式 = 通過率 + 進度條；其他模式 = 成交量 / 週轉率 -->
    <div class="cell-metric">
      <template v-if="scoreView && rate !== null">
        <span class="cell-passrate num">{{ Math.round(rate) }}%</span>
        <span class="cell-passbar"><span class="cell-passbar-fill" :style="{ width: `${rate}%` }" /></span>
      </template>
      <span v-else-if="!scoreView" class="cell-value num">{{ valueLabel }}</span>
      <span v-if="scoreLabel !== null" class="cell-score num">{{ scoreLabel }}</span>
    </div>

    <!-- 價格 +（評分模式）週轉率 + 漲跌幅 -->
    <div class="cell-bottom">
      <span class="cell-price num">{{ formatPrice(stock.close_price) }}</span>
      <span v-if="scoreView" class="cell-turnover num">{{ turnoverLabel }}</span>
      <span class="cell-pct num" :class="pctClass">{{ formatPct(stock.price_change_pct) }}</span>
    </div>

    <!-- 指標 chips：排雷 / 轉強 / 低估（買進評分）+ 法人 / 均線 / 量比 / 近高（每日盤後） -->
    <div v-if="chips.length" class="cell-chips">
      <span
        v-for="c in chips"
        :key="c.key"
        :data-chip="c.key"
        class="chip"
        :class="[`chip--${c.tone}`, { 'chip--keep': c.keepText, 'cell-fundamentals-badge': c.key === 'uptrend' }]"
        :title="c.title"
      ><span class="chip-icon">{{ c.icon }}</span><span class="chip-text">{{ c.text }}</span></span>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount } from 'vue'
import { tierToColor, tierToGlow } from '../utils/colorTier'
import { resolveSignal, signalLabel, passRate, scoreChips, dailyChips } from '../utils/signals'

const props = defineProps({
  stock:        { type: Object,  required: true },
  mode:         { type: String,  default: 'turnover' },
  highlighted:  { type: Boolean, default: false },
  buyScore:       { type: Object,  default: null },
  scoresLoaded:   { type: Boolean, default: false },
  scoresFetching: { type: Boolean, default: false },
  pinnable:       { type: Boolean, default: false },
  pinned:         { type: Boolean, default: false },
  daily:          { type: Object,  default: null },   // GET /api/signals entry
  marketOpen:     { type: Boolean, default: false },
})
const emit = defineEmits(['toggle-pin'])

// 手機長按 = 切換自選（桌機用右上角 ☆）
const LONG_PRESS_MS = 550
const PRESS_SLOP_PX = 10   // 超過即視為滑動換頁，不觸發長按
let pressTimer = null
let pressX = 0
let pressY = 0
function onPressStart(e) {
  if (!props.pinnable || e.pointerType === 'mouse') return
  cancelPress()
  pressX = e.clientX
  pressY = e.clientY
  pressTimer = setTimeout(() => {
    pressTimer = null
    emit('toggle-pin', props.stock.stock_id)
  }, LONG_PRESS_MS)
}
function onPressMove(e) {
  if (pressTimer && Math.hypot(e.clientX - pressX, e.clientY - pressY) > PRESS_SLOP_PX) cancelPress()
}
function cancelPress() {
  if (pressTimer) {
    clearTimeout(pressTimer)
    pressTimer = null
  }
}
onBeforeUnmount(cancelPress)

const signal = computed(() => (props.scoresLoaded ? resolveSignal(props.buyScore) : null))
const sigLabel = computed(() => (signal.value ? signalLabel(props.buyScore) : null))
const rate = computed(() => (props.scoresLoaded ? passRate(props.buyScore) : null))
// chips 列放不下時尾端會被裁掉 → 依重要性排序（排雷最先）
const CHIP_ORDER = ['risk', 'uptrend', 'value', 'inst', 'ma', 'vol', 'high']
const chips = computed(() => [
  ...(props.scoresLoaded ? scoreChips(props.buyScore) : []),
  ...dailyChips(props.daily, props.stock, props.marketOpen),
].sort((a, b) => CHIP_ORDER.indexOf(a.key) - CHIP_ORDER.indexOf(b.key)))

// 評分 / 自選視角：依訊號上色 + 通過率主指標；成交量 / 週轉率維持漲跌熱度
const scoreView = computed(() => props.mode === 'buy_score' || props.mode === 'watchlist')
const tintBySignal = scoreView
const tintSignal = computed(() => (tintBySignal.value ? signal.value : null))

const cellStyle = computed(() => {
  const ring = props.highlighted
    ? '0 0 28px 8px var(--cell-highlight-ring)'
    : '0 0 1px var(--cell-idle-ring)'
  const style = {}

  if (tintBySignal.value) {
    const s = tintSignal.value
    style.backgroundColor = s ? `var(--sig-${s}-bg)` : tierToColor('neutral')
    if (s) style.borderColor = `var(--sig-${s}-border)`
    style.boxShadow = ring
  } else {
    const tier = props.stock.color_tier
    style.backgroundColor = tierToColor(tier)
    style.boxShadow = `inset 0 0 16px ${tierToGlow(tier)}, ${ring}`
  }
  if (props.highlighted) style.borderColor = 'var(--accent)'
  return style
})

const valueLabel = computed(() => {
  if (props.mode === 'turnover') {
    const r = props.stock.turnover_rate
    return r != null ? `${r.toFixed(2)}%` : '—'
  }
  const v = props.stock.volume
  if (v == null) return '—'
  const zhang = Math.round(v / 1000)
  return zhang >= 10000
    ? `${(zhang / 10000).toFixed(1)}萬`
    : zhang >= 1000
      ? `${(zhang / 1000).toFixed(1)}K`
      : `${zhang}張`
})

// 週轉率（買進評分模式下，顯示於價格與漲跌幅之間）
const turnoverLabel = computed(() => {
  const r = props.stock.turnover_rate
  return r != null ? `${r.toFixed(2)}%` : '—'
})

// null    → never requested scores (show nothing)
// '...'   → fetch in progress, this stock not yet scored
// 'N/A'   → fetch complete, no score available for this stock
// '18/23' → scored; denominator = eligible_count (matches pass_rate), else max_score
const scoreLabel = computed(() => {
  if (!props.scoresLoaded) {
    return props.scoresFetching ? '...' : null
  }
  const s = props.buyScore
  if (!s || s.score == null || s.max_score === 0) {
    return props.scoresFetching ? '...' : 'N/A'
  }
  return `${s.score}/${s.eligible_count ?? s.max_score ?? 24}`
})

const tooltip = computed(() => {
  const s = props.stock
  const parts = [`#${s.rank} ${s.stock_id} ${s.name}`, s.sector, valueLabel.value]
  if (sigLabel.value) {
    parts.push(rate.value !== null ? `${sigLabel.value} 通過 ${rate.value}%` : sigLabel.value)
  }
  for (const c of chips.value) parts.push(c.title)
  return parts.filter(Boolean).join('｜')
})

const pctClass = computed(() => {
  const p = props.stock.price_change_pct
  if (p == null) return ''
  if (p > 0)  return 'pct-up'
  if (p < 0)  return 'pct-down'
  return 'pct-flat'
})

function formatPct(pct) {
  if (pct == null) return '—'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function formatPrice(p) {
  if (p == null || p === 0) return ''
  return p >= 100 ? p.toFixed(1) : p.toFixed(2)
}
</script>

<style scoped>
/* 字級下限 0.7rem（≈11px）：放不下的元素改為隱藏，不再縮字 */
.stock-cell {
  container-type: inline-size;
  width: 100%;
  height: 100%;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 2px;
  padding: 6px 8px 6px 10px;
  box-sizing: border-box;
  cursor: default;
  position: relative;
  overflow: hidden;
  border: 1px solid var(--cell-border-default);
  transition: filter 0.12s, transform 0.12s, border-color 0.12s;
  -webkit-touch-callout: none;
  user-select: none;
}

/* Top-left highlight sweep on hover */
.stock-cell::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  background: linear-gradient(135deg, var(--cell-hover-sweep) 0%, transparent 55%);
  opacity: 0;
  transition: opacity 0.15s;
  pointer-events: none;
}
.stock-cell:hover {
  filter: brightness(1.12);
  transform: scale(1.02);
  z-index: 10;
  border-color: var(--cell-hover-border);
}
.stock-cell:hover::before { opacity: 1; }

/* ── tier accent borders（漲跌熱度視角） ── */
.stock-cell[data-tier="deep_red"]:not([data-signal])    { border-color: var(--tier-dr-border); }
.stock-cell[data-tier="light_red"]:not([data-signal])   { border-color: var(--tier-lr-border); }
.stock-cell[data-tier="light_green"]:not([data-signal]) { border-color: var(--tier-lg-border); }
.stock-cell[data-tier="deep_green"]:not([data-signal])  { border-color: var(--tier-dg-border); }

/* 高風險避開：斜紋提示 */
.stock-cell[data-signal="avoid"] {
  background-image: repeating-linear-gradient(
    135deg, transparent 0 8px, var(--sig-avoid-stripe) 8px 12px
  );
}

/* ── 頂部列 ── */
.cell-top {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  min-width: 0;
}

.cell-rank {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--cell-rank-color);
  flex-shrink: 0;
}

.cell-sector {
  font-size: 0.7rem;
  color: var(--cell-sector-color);
  background: var(--cell-sector-bg);
  border: 1px solid var(--cell-sector-border);
  padding: 0 4px;
  border-radius: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex-shrink: 1;
}

.cell-signal {
  margin-left: auto;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;
  white-space: nowrap;
  flex-shrink: 0;
  color: var(--sig-neutral-fg);
  border: 1px solid var(--sig-neutral-border);
  background: var(--sig-badge-bg);
}
.cell-signal[data-signal="strong_buy"] {
  color: var(--sig-strong_buy-fg);
  border-color: var(--sig-strong_buy-border);
  box-shadow: 0 0 8px var(--sig-strong_buy-glow);
}
.cell-signal[data-signal="buy"]   { color: var(--sig-buy-fg);   border-color: var(--sig-buy-border); }
.cell-signal[data-signal="watch"] { color: var(--sig-watch-fg); border-color: var(--sig-watch-border); }
.cell-signal[data-signal="avoid"] { color: var(--sig-avoid-fg); border-color: var(--sig-avoid-border); }

/* 自選 ☆：未釘選時只在 hover 出現；已釘選常駐 ★ */
.cell-pin {
  flex-shrink: 0;
  margin-left: auto;
  background: none;
  border: none;
  padding: 0 2px;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  color: var(--cell-score-color);
  opacity: 0;
  transition: opacity 0.12s;
}
.cell-signal + .cell-pin { margin-left: 0; }
.cell-pin.is-pinned {
  opacity: 1;
  color: var(--sig-strong_buy-fg);
}
.stock-cell:hover .cell-pin,
.cell-pin:focus-visible { opacity: 1; }
@media (hover: none) {
  .cell-pin:not(.is-pinned) { display: none; }
}

.cell-signal-bar {
  display: none;
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--sig-neutral-fg);
}
.cell-signal-bar[data-signal="strong_buy"] { background: var(--sig-strong_buy-fg); }
.cell-signal-bar[data-signal="buy"]        { background: var(--sig-buy-fg); }
.cell-signal-bar[data-signal="watch"]      { background: var(--sig-watch-fg); }
.cell-signal-bar[data-signal="avoid"]      { background: var(--sig-avoid-fg); }

/* ── 名稱 + 代號 ── */
.cell-name {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  font-size: clamp(0.95rem, 1.4vw, 1.15rem);
  font-weight: 700;
  line-height: 1.2;
  color: var(--cell-name-color);
}

.cell-name-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex-shrink: 1;
}

.cell-code {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--cell-code-color);
  flex-shrink: 0;
}

/* ── 主指標列 ── */
.cell-metric {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-shrink: 0;
}

.cell-passrate {
  font-size: 1.15rem;
  font-weight: 800;
  line-height: 1;
  color: var(--cell-name-color);
}
.stock-cell[data-signal] .cell-passrate { color: var(--sig-neutral-fg); }
.stock-cell[data-signal="strong_buy"] .cell-passrate { color: var(--sig-strong_buy-fg); }
.stock-cell[data-signal="buy"] .cell-passrate        { color: var(--sig-buy-fg); }
.stock-cell[data-signal="watch"] .cell-passrate      { color: var(--sig-watch-fg); }
.stock-cell[data-signal="avoid"] .cell-passrate      { color: var(--sig-avoid-fg); }

.cell-passbar {
  flex: 1;
  height: 5px;
  min-width: 24px;
  border-radius: 3px;
  background: var(--cell-bar-track);
  overflow: hidden;
}
.cell-passbar-fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: currentColor;
  color: var(--sig-neutral-fg);
}
.stock-cell[data-signal="strong_buy"] .cell-passbar-fill { color: var(--sig-strong_buy-fg); }
.stock-cell[data-signal="buy"] .cell-passbar-fill        { color: var(--sig-buy-fg); }
.stock-cell[data-signal="watch"] .cell-passbar-fill      { color: var(--sig-watch-fg); }
.stock-cell[data-signal="avoid"] .cell-passbar-fill      { color: var(--sig-avoid-fg); }

.cell-value {
  font-size: 0.8rem;
  color: var(--cell-value-color);
  white-space: nowrap;
}

.cell-score {
  margin-left: auto;
  font-size: 0.72rem;
  color: var(--cell-score-color);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 價格 + 週轉率 + 漲跌幅 ── */
.cell-bottom {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 4px;
  flex-shrink: 0;
}

.cell-price {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--cell-price-color);
  white-space: nowrap;
}

.cell-turnover {
  font-size: 0.72rem;
  color: var(--cell-value-color);
  white-space: nowrap;
}

.cell-pct {
  font-size: 0.9rem;
  font-weight: 700;
  white-space: nowrap;
}
.pct-up   { color: var(--pct-up); }
.pct-down { color: var(--pct-down); }
.pct-flat { color: var(--pct-flat); }

/* ── 指標 chips ── */
.cell-chips {
  display: flex;
  flex-wrap: nowrap;
  gap: 3px;
  overflow: hidden;
  flex-shrink: 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 0.7rem;
  line-height: 1.35;
  padding: 0 5px;
  border-radius: 3px;
  white-space: nowrap;
  background: var(--chip-bg);
  color: var(--chip-fg);
}
.chip--good { color: var(--chip-good-fg); }
.chip--soft { color: var(--chip-soft-fg); }
.chip--warn { color: var(--chip-warn-fg); background: var(--chip-warn-bg); }
.chip--up   { color: var(--pct-up); }
.chip--down { color: var(--pct-down); }

.cell-highlighted {
  animation: pulse-highlight 0.6s ease-in-out 3;
  z-index: 20;
}

@keyframes pulse-highlight {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.45; }
}

/* ── 窄卡片（6×6、手機 3×3）：chips 只留圖示，訊號改左緣色條 ── */
@container (max-width: 210px) {
  .chip:not(.chip--keep) .chip-text { display: none; }
  .cell-signal { display: none; }
  .cell-signal-bar { display: block; }
  .cell-sector { display: none; }
}

@container (max-width: 150px) {
  .cell-passbar { display: none; }
  .cell-turnover { display: none; }
}

@media (hover: none), (pointer: coarse), (prefers-reduced-motion: reduce) {
  .stock-cell {
    transition: none;
  }

  .stock-cell::before {
    display: none;
  }

  .stock-cell:hover {
    filter: none;
    transform: none;
    border-color: var(--cell-border-default);
  }
}

/* 矮螢幕：高度不足時先拿掉題材，保住字級 */
@media (max-height: 768px) {
  .stock-cell {
    padding: 4px 6px 4px 8px;
    gap: 1px;
  }

  .cell-sector {
    display: none;
  }

  .cell-name {
    font-size: clamp(0.85rem, 1.2vw, 1rem);
  }

  .cell-passrate {
    font-size: 1rem;
  }
}
</style>
