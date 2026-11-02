<template>
  <section class="pulse" aria-label="市場狀態">
    <div class="panel pulse-read" :data-read="read?.key">
      <span class="pulse-label">市場狀態</span>
      <template v-if="read">
        <strong class="read-title">{{ read.label }}</strong>
        <p class="read-text">{{ read.text }}</p>
      </template>
      <template v-else>
        <strong class="read-title">尚無判讀</strong>
        <p class="read-text">盤後指標尚未產生，交易日後凌晨 03:00 更新。</p>
      </template>
    </div>

    <div class="panel tile">
      <span class="pulse-label">上漲 / 下跌</span>
      <span class="tile-value">
        <span class="pct-up">{{ summary.advancers }}</span>
        <span class="tile-sep">/</span>
        <span class="pct-down">{{ summary.decliners }}</span>
      </span>
      <span class="breadth-bar" role="img" :aria-label="`上漲 ${summary.advancers} 家，下跌 ${summary.decliners} 家，平盤 ${summary.unchanged} 家`">
        <i class="seg seg--up" :style="{ flexGrow: summary.advancers }" />
        <i class="seg seg--flat" :style="{ flexGrow: summary.unchanged }" />
        <i class="seg seg--down" :style="{ flexGrow: summary.decliners }" />
      </span>
    </div>

    <div class="panel tile">
      <span class="pulse-label">中位數漲跌</span>
      <span class="tile-value" :class="pctClass(summary.medianChange)">{{ formatPct(summary.medianChange) }}</span>
      <span class="tile-note">{{ summary.total }} 檔的中間值</span>
    </div>

    <div class="panel tile">
      <span class="pulse-label">站上月線</span>
      <span class="tile-value">{{ pct(summary.pctAboveMa20) }}</span>
      <span class="tile-note">季線 {{ pct(summary.pctAboveMa60) }}</span>
    </div>

    <div class="panel tile">
      <span class="pulse-label">法人連買 / 連賣</span>
      <span class="tile-value">
        <span>{{ summary.instBuying ?? '—' }}</span>
        <span class="tile-sep">/</span>
        <span>{{ summary.instSelling ?? '—' }}</span>
      </span>
      <span class="tile-note">連續 3 日以上的檔數</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { marketRead } from '../../utils/analysis'
import { formatPct, pctClass } from '../../utils/format'

const props = defineProps({
  summary: { type: Object, required: true },
})

const read = computed(() => marketRead(props.summary))
const pct = (v) => (v == null ? '—' : `${Math.round(v)}%`)
</script>

<style scoped>
.pulse {
  display: grid;
  grid-template-columns: minmax(240px, 1.7fr) repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.pulse-read,
.tile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 12px 14px;
}

.pulse-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.read-title { font-size: 1.375rem; font-weight: 700; line-height: 1.25; }
.read-text { font-size: 0.8125rem; color: var(--text-secondary); }

.tile-value { font-size: 1.5rem; font-weight: 700; line-height: 1.25; white-space: nowrap; }
.tile-sep { margin: 0 4px; font-weight: 400; color: var(--text-muted); }
.tile-note { font-size: 0.75rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.breadth-bar {
  display: flex;
  gap: 2px;
  height: 6px;
  margin-top: 4px;
  overflow: hidden;
  border-radius: 3px;
}
.seg { display: block; min-width: 0; flex-basis: 0; }
.seg--up { background: var(--pct-up); }
.seg--down { background: var(--pct-down); }
.seg--flat { background: var(--chart-neutral); }

@media (max-width: 1100px) {
  .pulse { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pulse-read { grid-column: 1 / -1; }
}
</style>
