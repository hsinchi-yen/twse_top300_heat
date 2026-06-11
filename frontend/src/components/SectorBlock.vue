<template>
  <div class="sector-block">
    <div class="sector-header">
      <span class="sector-name">{{ sector.name }}</span>
      <span class="sector-count">{{ sector.stocks.length }} 檔</span>
    </div>
    <div class="sector-cells">
      <div
        v-for="stock in sector.stocks"
        :key="stock.stock_id"
        class="stock-slot"
      >
        <StockCell
          :stock="stock"
          :mode="mode"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import StockCell from './StockCell.vue'

defineProps({
  sector: { type: Object, required: true },
  mode: { type: String, default: 'turnover' },
})
</script>

<style scoped>
.sector-block {
  background: var(--sector-bg);
  border: 1px solid var(--sector-border);
  border-radius: 8px;
  padding: 0.55rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.sector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.sector-name {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--sector-name-color);
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sector-count {
  font-size: 0.66rem;
  color: var(--sector-count-color);
  white-space: nowrap;
}

.sector-cells {
  --cell-size: clamp(72px, 4.9vw, 96px);
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--cell-size), var(--cell-size)));
  grid-auto-rows: var(--cell-size);
  gap: 4px;
  align-content: start;
}

.stock-slot {
  width: var(--cell-size);
  height: var(--cell-size);
}

@media (max-width: 1366px), (max-height: 768px) {
  .sector-cells {
    --cell-size: clamp(64px, 4.1vw, 86px);
  }

  .sector-name {
    font-size: 0.7rem;
  }

  .sector-count {
    font-size: 0.62rem;
  }
}
</style>
