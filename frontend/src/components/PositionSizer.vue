<template>
  <div class="sizer">
    <div class="sizer-inputs">
      <label class="field">
        <span>總資金（元）</span>
        <input v-model.number="prefs.capital" class="num" type="number" min="0" step="100000" inputmode="numeric" data-field="capital" />
      </label>
      <label class="field">
        <span>單筆最大虧損 %</span>
        <input v-model.number="prefs.riskPct" class="num" type="number" min="0" step="0.25" inputmode="decimal" data-field="riskPct" />
      </label>
      <label class="field">
        <span>單檔部位上限 %</span>
        <input v-model.number="prefs.maxPositionPct" class="num" type="number" min="0" step="5" inputmode="decimal" data-field="maxPositionPct" />
      </label>
      <label class="field">
        <span>預計進場價</span>
        <input v-model.number="entry" class="num" type="number" min="0" step="0.5" inputmode="decimal" data-field="entry" @input="entryEdited = true" />
      </label>
      <label class="field">
        <span>停損價<em v-if="stopHint">（{{ stopHint }}）</em></span>
        <input v-model.number="stop" class="num" type="number" min="0" step="0.5" inputmode="decimal" data-field="stop" @input="stopEdited = true" />
      </label>
    </div>

    <template v-if="result">
      <dl class="sizer-result">
        <div class="result-main">
          <dt>部位上限</dt>
          <dd class="num sizer-lots">{{ sizeLabel }}</dd>
        </div>
        <div>
          <dt>投入金額</dt>
          <dd class="num">{{ formatTwd(result.positionValue) }}<small>{{ result.positionPct }}%</small></dd>
        </div>
        <div>
          <dt>觸及停損虧損</dt>
          <dd class="num sizer-loss">{{ formatTwd(result.maxLoss) }}<small>{{ result.maxLossPct }}%</small></dd>
        </div>
        <div>
          <dt>來回交易成本</dt>
          <dd class="num">{{ formatTwd(result.roundTripCost) }}</dd>
        </div>
        <div>
          <dt>占 5 日均量</dt>
          <dd class="num">{{ result.participationPct === null ? '—' : `${result.participationPct}%` }}</dd>
        </div>
      </dl>
      <p class="sizer-basis">{{ result.limitedBy === 'cap' ? '受單檔上限限制' : '受單筆虧損限制' }}。跳空跌破時實際虧損可能超過此數字。</p>
      <ul v-if="result.warnings.length" class="sizer-warnings">
        <li v-for="w in result.warnings" :key="w.key" :data-warning="w.key">{{ w.text }}</li>
      </ul>
    </template>
    <p v-else class="sizer-invalid">請輸入資金、風險比例，以及低於進場價的停損價。</p>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { defaultStop, sizePosition } from '../utils/positionSizing'
import { formatTwd } from '../utils/format'

const props = defineProps({
  price:     { type: Number, default: null },
  ma60:      { type: Number, default: null },
  avgVolume: { type: Number, default: null },
})

const STORAGE_KEY = 'sizing_prefs'
const DEFAULTS = { capital: 1_000_000, riskPct: 1, maxPositionPct: 20 }

function loadPrefs() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')
    return { ...DEFAULTS, ...(stored && typeof stored === 'object' ? stored : {}) }
  } catch {
    return { ...DEFAULTS }
  }
}

const prefs = reactive(loadPrefs())
watch(prefs, () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch {
    // storage unavailable — settings still apply for this session
  }
})

const entry = ref(null)
const stop = ref(null)
const suggestion = ref(null)
const entryEdited = ref(false)
const stopEdited = ref(false)

// Quotes refresh every minute: what the user typed must not change under them.
function followQuote() {
  suggestion.value = defaultStop({ price: props.price, ma60: props.ma60 })
  if (!entryEdited.value) entry.value = props.price
  if (!stopEdited.value) stop.value = suggestion.value?.stop ?? null
}

// The parent keys this component per stock, so a new stock starts untouched.
followQuote()
watch(() => [props.price, props.ma60], followQuote)

const stopHint = computed(() => {
  if (!suggestion.value || stop.value !== suggestion.value.stop) return ''
  return suggestion.value.basis === 'ma60' ? '季線' : '-8%'
})

const result = computed(() => sizePosition({
  capital: prefs.capital,
  riskPct: prefs.riskPct,
  maxPositionPct: prefs.maxPositionPct,
  entry: entry.value,
  stop: stop.value,
  avgVolume: props.avgVolume,
}))

const sizeLabel = computed(() => {
  const r = result.value
  if (!r) return ''
  if (r.lots > 0) return `${r.lots} 張`
  return `${r.shares} 股`
})
</script>

<style scoped>
.sizer { display: flex; flex-direction: column; gap: 10px; }

.sizer-inputs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.field { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.field span { font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap; }
.field em { font-style: normal; color: var(--text-muted); }
.field input {
  width: 100%;
  height: 34px;
  padding: 0 8px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--surface-sunken);
  color: var(--text-primary);
  font-size: 0.875rem;
  outline: none;
}
.field input:focus { border-color: var(--accent); }

.sizer-result {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--surface-sunken);
}
.sizer-result dt { font-size: 0.75rem; color: var(--text-secondary); }
.sizer-result dd { font-size: 0.9375rem; font-weight: 600; }
.sizer-result small { margin-left: 6px; font-size: 0.75rem; font-weight: 400; color: var(--text-muted); }
.result-main { grid-column: 1 / -1; }
.result-main dd { font-size: 1.5rem; }
.sizer-loss { color: var(--pct-down); }

.sizer-basis { font-size: 0.75rem; color: var(--text-muted); }

.sizer-warnings {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8125rem;
  color: var(--chip-warn-fg);
}

.sizer-invalid { font-size: 0.8125rem; color: var(--text-muted); }

@media (max-width: 480px) {
  .sizer-inputs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
