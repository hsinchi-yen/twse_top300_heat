<template>
  <div class="watchlist-container">
    <div v-if="wl.error" class="watch-error">
      ⚠ {{ wl.error }}
      <button class="watch-error-close" @click="wl.clearError()">×</button>
    </div>

    <div v-if="!wl.loaded" class="watchlist-empty">載入自選股…</div>
    <div v-else-if="wl.items.length === 0" class="watchlist-empty">
      尚未釘選股票：在成交量／週轉率／買進評分卡片右上角點 ☆（手機長按卡片）加入自選
    </div>

    <div v-else class="watch-grid">
      <article v-for="item in wl.items" :key="item.stock_id" class="watch-card">
        <div class="watch-cell">
          <StockCell
            v-if="item.quote"
            :stock="item.quote"
            mode="watchlist"
            :buy-score="scores[item.stock_id] ?? null"
            :scores-loaded="scoresLoaded"
            :scores-fetching="scoresFetching"
            :daily="signals[item.stock_id] ?? null"
            :market-open="marketOpen"
          />
          <div v-else class="watch-noquote">{{ item.stock_id }} 最新交易日無報價</div>
        </div>

        <div class="watch-meta">
          <input
            v-if="editing === item.stock_id"
            class="watch-note-input"
            :value="item.note"
            maxlength="500"
            placeholder="研究筆記／買進理由"
            @keydown.enter="saveNote(item.stock_id, $event.target.value)"
            @blur="saveNote(item.stock_id, $event.target.value)"
          />
          <span
            v-else
            class="watch-note"
            :class="{ 'is-empty': !item.note }"
            :title="item.note"
            @click="editing = item.stock_id"
          >{{ item.note || '＋ 寫筆記' }}</span>

          <button
            class="watch-btn watch-expand"
            :aria-expanded="expanded.has(item.stock_id)"
            @click="toggleExpand(item.stock_id)"
          >{{ expanded.has(item.stock_id) ? '收合' : '明細' }}</button>
          <button class="watch-btn watch-remove" title="移出自選" @click="wl.unpin(item.stock_id)">✕</button>
        </div>

        <ScoreDetail v-if="expanded.has(item.stock_id)" :stock-id="item.stock_id" class="watch-detail" />
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useWatchlistStore } from '../stores/watchlistStore'
import StockCell from './StockCell.vue'
import ScoreDetail from './ScoreDetail.vue'

const wl = useWatchlistStore()
const { scores, scoresLoaded, scoresFetching, signals, marketOpen } = storeToRefs(useStockStore())

const editing = ref('')
const expanded = ref(new Set())

function toggleExpand(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}

async function saveNote(id, note) {
  if (editing.value !== id) return
  editing.value = ''
  const current = wl.items.find(i => i.stock_id === id)
  if (current && current.note === note) return
  await wl.saveNote(id, note)
}
</script>

<style scoped>
.watchlist-container {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.watchlist-empty {
  color: var(--ctrl-state-color);
  text-align: center;
  padding: 4rem 1rem;
  font-size: 0.95rem;
}

.watch-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--ctrl-error-color);
  font-size: 0.8rem;
}
.watch-error-close {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1rem;
}

.watch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 10px;
  align-content: start;
}

.watch-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px;
  border-radius: 8px;
  background: var(--sector-bg);
  border: 1px solid var(--sector-border);
}

/* 自選卡片放大：大字級 + 固定高度讓所有列都看得到 */
.watch-cell {
  height: 150px;
}
.watch-cell :deep(.cell-name)     { font-size: 1.3rem; }
.watch-cell :deep(.cell-passrate) { font-size: 1.5rem; }
.watch-cell :deep(.cell-pct)      { font-size: 1.05rem; }
.watch-cell :deep(.cell-price)    { font-size: 1rem; }
.watch-cell :deep(.chip),
.watch-cell :deep(.cell-signal)   { font-size: 0.8rem; }

.watch-noquote {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--cell-empty-border);
  border-radius: 6px;
  color: var(--text-secondary);
}

.watch-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.watch-note {
  flex: 1;
  min-width: 0;
  font-size: 0.8rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: text;
}
.watch-note.is-empty { color: var(--text-secondary); }

.watch-note-input {
  flex: 1;
  min-width: 0;
  font-size: 0.8rem;
  padding: 2px 6px;
  background: var(--ctrl-search-bg);
  border: 1px solid var(--ctrl-search-focus-border);
  border-radius: 4px;
  color: var(--ctrl-search-color);
  outline: none;
}

.watch-btn {
  flex-shrink: 0;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--ctrl-page-btn-border);
  background: var(--ctrl-page-btn-bg);
  color: var(--ctrl-page-btn-color);
  cursor: pointer;
}
.watch-remove { color: var(--text-secondary); }

.watch-detail {
  border-top: 1px solid var(--sector-border);
  padding-top: 6px;
}

@media (max-width: 768px) {
  .watch-grid { grid-template-columns: 1fr; }
  .watch-btn  { min-height: 36px; min-width: 44px; }
}
</style>
