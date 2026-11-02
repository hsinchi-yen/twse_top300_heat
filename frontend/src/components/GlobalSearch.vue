<template>
  <div ref="root" class="global-search" role="search">
    <Icon name="search" :size="15" class="search-icon" />
    <input
      ref="input"
      v-model="query"
      class="search-input"
      type="search"
      placeholder="搜尋代號或名稱"
      aria-label="搜尋股票"
      autocomplete="off"
      role="combobox"
      :aria-expanded="open"
      aria-controls="search-results"
      @focus="focused = true"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="pick(results[cursor])"
      @keydown.esc="reset"
    />
    <kbd v-if="!query" class="search-kbd">/</kbd>

    <ul v-if="open" id="search-results" class="search-results" role="listbox">
      <li v-for="(s, i) in results" :key="s.stock_id" role="presentation">
        <button
          class="search-item"
          :class="{ active: i === cursor }"
          role="option"
          :aria-selected="i === cursor"
          @pointerenter="cursor = i"
          @click="pick(s)"
        >
          <span class="item-name">{{ s.name }}</span>
          <span class="item-code num">{{ s.stock_id }}</span>
          <span class="item-sector">{{ s.sector }}</span>
          <span class="item-pct num" :class="pctClass(s.price_change_pct)">{{ formatPct(s.price_change_pct) }}</span>
        </button>
      </li>
    </ul>
    <p v-else-if="focused && query.trim()" class="search-empty">
      找不到「{{ query.trim() }}」：搜尋範圍為成交量前 {{ MAX_STOCKS }} 檔與自選股
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useWatchlistStore } from '../stores/watchlistStore'
import { useUiStore } from '../stores/uiStore'
import { MAX_STOCKS } from '../constants'
import { formatPct, pctClass } from '../utils/format'
import Icon from './Icon.vue'

const MAX_RESULTS = 8

const { stockPool } = storeToRefs(useStockStore())
const wl = useWatchlistStore()
const ui = useUiStore()

const root = ref(null)
const input = ref(null)
const query = ref('')
const focused = ref(false)
const cursor = ref(0)

const searchable = computed(() => {
  const seen = new Set(stockPool.value.map(s => s.stock_id))
  const extras = wl.items.map(i => i.quote).filter(q => q && !seen.has(q.stock_id))
  return [...stockPool.value, ...extras]
})

const results = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return []
  // Exact and prefix code matches first: typing 2330 should land on 2330.
  const rank = (s) => {
    if (s.stock_id === q) return 0
    if (s.stock_id.startsWith(q)) return 1
    return s.name?.toLowerCase().startsWith(q) ? 2 : 3
  }
  return searchable.value
    .filter(s => s.stock_id.startsWith(q) || s.name?.toLowerCase().includes(q))
    .sort((a, b) => rank(a) - rank(b) || (a.rank ?? 9999) - (b.rank ?? 9999))
    .slice(0, MAX_RESULTS)
})

const open = computed(() => focused.value && results.value.length > 0)

watch(query, () => { cursor.value = 0 })

function move(delta) {
  const n = results.value.length
  if (n) cursor.value = (cursor.value + delta + n) % n
}

function reset() {
  query.value = ''
  focused.value = false
  input.value?.blur()
}

function pick(stock) {
  if (!stock) return
  ui.openStock(stock.stock_id)
  reset()
}

function onDocumentKey(e) {
  if (ui.selectedStockId || ui.guideOpen) return   // a dialog owns the keyboard
  const target = e.target
  const typing = target instanceof HTMLElement
    && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault()
    input.value?.focus()
  }
}

function onDocumentPointer(e) {
  if (root.value && !root.value.contains(e.target)) focused.value = false
}

onMounted(() => {
  document.addEventListener('keydown', onDocumentKey)
  document.addEventListener('pointerdown', onDocumentPointer)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocumentKey)
  document.removeEventListener('pointerdown', onDocumentPointer)
})
</script>

<style scoped>
.global-search {
  position: relative;
  display: flex;
  align-items: center;
  flex: 0 1 260px;
  min-width: 120px;
}

.search-icon {
  position: absolute;
  left: 9px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 34px;
  padding: 0 28px 0 30px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface-sunken);
  color: var(--text-primary);
  font-size: 0.8125rem;
  outline: none;
  transition: border-color 0.12s;
}
.search-input::placeholder { color: var(--text-muted); }
.search-input:focus { border-color: var(--accent); }
.search-input::-webkit-search-cancel-button { display: none; }

.search-kbd {
  position: absolute;
  right: 8px;
  padding: 0 5px;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 0.6875rem;
  pointer-events: none;
}

.search-results,
.search-empty {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 250;
  width: max(100%, 340px);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
  box-shadow: var(--shadow-lg);
}

.search-results { list-style: none; padding: 4px; }

.search-empty {
  padding: 10px 12px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.search-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 34px;
  padding: 0 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-primary);
  font-size: 0.8125rem;
  text-align: left;
}
.search-item.active { background: var(--hover-wash); }

.item-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.item-code { color: var(--text-muted); }
.item-sector { color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.item-pct { margin-left: auto; flex-shrink: 0; }

@media (max-width: 768px) {
  .global-search { flex: 1 1 0; min-width: 0; }
  .search-kbd { display: none; }
  .search-input { font-size: 1rem; }
  .search-results,
  .search-empty { width: 100%; }
}
</style>
