<template>
  <section v-if="rows.length" class="panel alerts">
    <h2 class="panel__title">自選警示</h2>
    <ul class="alert-list">
      <li v-for="row in rows" :key="row.stock.stock_id">
        <button class="alert-row" @click="ui.openStock(row.stock.stock_id)">
          <span class="alert-name">{{ row.stock.name }}</span>
          <span class="alert-code num">{{ row.stock.stock_id }}</span>
          <span class="alert-tags">
            <span v-for="a in row.alerts" :key="a.key" class="tag alert-tag" :data-alert="a.key">{{ a.label }}</span>
          </span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../../stores/stockStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { useUiStore } from '../../stores/uiStore'
import { watchAlerts } from '../../utils/analysis'

const { scores, signals } = storeToRefs(useStockStore())
const wl = useWatchlistStore()
const ui = useUiStore()

const rows = computed(() => wl.items
  .filter(item => item.quote)
  .map(item => ({
    stock: item.quote,
    alerts: watchAlerts({
      stock: item.quote,
      score: scores.value[item.stock_id],
      daily: signals.value[item.stock_id],
    }),
  }))
  .filter(row => row.alerts.length))
</script>

<style scoped>
.alerts {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 14px 8px 8px;
}
.alerts .panel__title { padding: 0 8px; }

.alert-list { list-style: none; }

.alert-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
  width: 100%;
  padding: 7px 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-primary);
  text-align: left;
}
.alert-row:hover { background: var(--hover-wash); }

.alert-name { font-size: 0.875rem; font-weight: 600; }
.alert-code { font-size: 0.75rem; color: var(--text-muted); }
.alert-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-left: auto; }
.alert-tag { background: var(--chip-warn-bg); color: var(--chip-warn-fg); }
</style>
