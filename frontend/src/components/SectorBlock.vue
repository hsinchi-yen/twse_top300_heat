<template>
  <div class="sector-block">
    <div class="sector-header">
      <span class="sector-name">{{ sector.name }}</span>
      <span class="sector-count">{{ sector.stocks.length }} 檔</span>
    </div>
    <div class="sector-cells">
      <StockCell
        v-for="stock in sector.stocks"
        :key="stock.stock_id"
        :stock="stock"
      />
    </div>
  </div>
</template>

<script setup>
import StockCell from './StockCell.vue'

defineProps({
  sector: { type: Object, required: true },
})
</script>

<style scoped>
.sector-block {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sector-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.sector-name {
  font-size: 0.85rem;
  font-weight: 700;
  color: #90caf9;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.sector-count {
  font-size: 0.72rem;
  color: #666;
}

.sector-cells {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
