<template>
  <div class="mode-toggle">
    <button
      id="btn-volume"
      :class="['toggle-btn', mode === 'volume' ? 'active' : '']"
      @click="emit('mode-change', 'volume')"
    >
      📊 成交量 Top 100
    </button>
    <button
      id="btn-turnover"
      :class="['toggle-btn', mode === 'turnover' ? 'active' : '']"
      @click="emit('mode-change', 'turnover')"
    >
      🔄 週轉率 Top 100
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  mode: { type: String, required: true }, // 'volume' | 'turnover'
})
const emit = defineEmits(['mode-change'])
</script>

<style scoped>
.mode-toggle {
  display: flex;
  gap: 0.75rem;
}

.toggle-btn {
  padding: 0.5rem 1.25rem;
  border: 1px solid #555;
  border-radius: 6px;
  background: #1e1e1e;
  color: #aaa;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover {
  border-color: #888;
  color: #fff;
}

.toggle-btn.active {
  background: #2a3f6f;
  border-color: #4a7fff;
  color: #fff;
  font-weight: 600;
}
</style>
