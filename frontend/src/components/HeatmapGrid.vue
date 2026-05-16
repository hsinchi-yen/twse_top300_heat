<template>
  <div class="heatmap-grid">
    <div v-if="loading" class="state-msg">⏳ 載入中...</div>
    <div v-else-if="error" class="state-msg error">⚠️ {{ error }}</div>
    <div v-else-if="sectors.length === 0" class="state-msg">暫無資料</div>
    <div v-else class="sectors-layout">
      <SectorBlock
        v-for="sector in sectors"
        :key="sector.name"
        :sector="sector"
      />
    </div>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import SectorBlock from './SectorBlock.vue'

const store = useStockStore()
const { sectors, loading, error } = storeToRefs(store)
</script>

<style scoped>
.heatmap-grid {
  width: 100%;
  flex: 1;
  overflow-y: auto;
}

.sectors-layout {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-content: flex-start;
}

.state-msg {
  color: #aaa;
  font-size: 1rem;
  padding: 2rem;
  text-align: center;
}

.state-msg.error {
  color: #ef5350;
}
</style>
