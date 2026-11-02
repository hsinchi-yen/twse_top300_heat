<template>
  <div class="score-detail">
    <p v-if="state === 'loading'" class="detail-msg">載入評分明細…</p>
    <p v-else-if="state === 'missing'" class="detail-msg">尚未評分（交易日後凌晨 03:00 評分或強制刷新後會納入）</p>
    <p v-else-if="state === 'error'" class="detail-msg detail-msg--error">明細暫時無法取得</p>

    <template v-else>
      <ul v-if="risks.length" class="risk-list">
        <li v-for="r in risks" :key="r.name" class="risk-item" :title="r.description">
          {{ r.name }} <span class="risk-val num">{{ r.value_label }}</span>
        </li>
      </ul>

      <div v-for="g in groups" :key="g.key" class="crit-group">
        <h4 class="crit-head">{{ g.title }} <span class="num">{{ g.items.length }}</span></h4>
        <ul>
          <li
            v-for="c in g.items"
            :key="c.id"
            class="crit"
            :class="`crit--${g.key}`"
            :title="c.threshold ? `門檻：${c.threshold}` : ''"
          >
            <span class="crit-mark">{{ g.mark }}</span>
            <span class="crit-label">{{ c.label }}</span>
            <span class="crit-val num">{{ c.value_label }}</span>
          </li>
        </ul>
      </div>
      <p class="detail-date">評分日 {{ date }}</p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const props = defineProps({
  stockId: { type: String, required: true },
})

const state = ref('loading')   // loading | ready | missing | error
const date = ref('')
const criteria = ref([])
const risks = ref([])

// 未通過放最前：深度思考者最需要先看到「哪裡不夠好」
const groups = computed(() => [
  { key: 'fail', title: '未通過', mark: '✗', items: criteria.value.filter(c => c.pass === false) },
  { key: 'pass', title: '通過',   mark: '✓', items: criteria.value.filter(c => c.pass === true) },
  { key: 'na',   title: '無資料／不適用', mark: '–', items: criteria.value.filter(c => c.pass == null) },
].filter(g => g.items.length))

onMounted(async () => {
  try {
    const res = await fetch(`${API_BASE}/api/scores/${props.stockId}`)
    if (res.status === 404) {
      state.value = 'missing'
      return
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    date.value = data.date ?? ''
    criteria.value = data.criteria ?? []
    risks.value = data.risk_criteria ?? []
    state.value = 'ready'
  } catch (err) {
    console.warn('[ScoreDetail] detail unavailable:', err.message)
    state.value = 'error'
  }
})
</script>

<style scoped>
.score-detail {
  font-size: 0.8125rem;
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-msg { color: var(--text-muted); }
.detail-msg--error { color: var(--pct-up); }

.risk-list,
.crit-group ul {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.risk-item {
  color: var(--chip-warn-fg);
  background: var(--chip-warn-bg);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
}
.risk-val { margin-left: 4px; opacity: 0.85; }

.crit-head {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 3px;
}

.crit {
  display: grid;
  grid-template-columns: 1.1em 1fr auto;
  gap: 6px;
  align-items: baseline;
}
.crit-mark { font-weight: 700; }
.crit--pass .crit-mark { color: var(--accent); }
.crit--fail .crit-mark { color: var(--warn); }
.crit--na              { color: var(--text-muted); }
.crit-val {
  color: var(--text-secondary);
  white-space: nowrap;
}

.detail-date {
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
