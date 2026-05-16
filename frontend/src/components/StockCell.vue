<template>
  <div
    class="stock-cell"
    :style="{ backgroundColor: bgColor }"
    :title="`${stock.stock_id} ${stock.name} | 排名 #${stock.rank}`"
  >
    <div class="cell-id">{{ stock.stock_id }}</div>
    <div class="cell-name">{{ stock.name }}</div>
    <div class="cell-pct">{{ formatPct(stock.price_change_pct) }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { tierToColor } from '../utils/colorTier'

const props = defineProps({
  stock: { type: Object, required: true },
})

const bgColor = computed(() => tierToColor(props.stock.color_tier))

function formatPct(pct) {
  if (pct == null) return '—'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}
</script>

<style scoped>
.stock-cell {
  width: 80px;
  height: 70px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: default;
  transition: filter 0.15s, transform 0.15s;
  padding: 4px;
  box-sizing: border-box;
  border: 1px solid rgba(255,255,255,0.05);
}

.stock-cell:hover {
  filter: brightness(1.25);
  transform: scale(1.05);
  z-index: 1;
}

.cell-id {
  font-size: 0.65rem;
  color: rgba(255,255,255,0.6);
  font-weight: 500;
}

.cell-name {
  font-size: 0.7rem;
  color: #fff;
  font-weight: 700;
  text-align: center;
  line-height: 1.2;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-pct {
  font-size: 0.72rem;
  color: rgba(255,255,255,0.9);
  font-weight: 600;
  margin-top: 2px;
}
</style>
