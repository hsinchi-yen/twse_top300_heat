<template>
  <div class="mode-toggle">
    <button
      id="btn-volume"
      :class="['toggle-btn', mode === 'volume' ? 'active' : '']"
      @click="emit('mode-change', 'volume')"
    >
      成交量 TOP 300
    </button>
    <button
      id="btn-turnover"
      :class="['toggle-btn', mode === 'turnover' ? 'active' : '']"
      @click="emit('mode-change', 'turnover')"
    >
      週轉率 TOP 300
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  mode: { type: String, required: true },
})
const emit = defineEmits(['mode-change'])
</script>

<style scoped>
.mode-toggle {
  display: flex;
  gap: 0.5rem;
}

.toggle-btn {
  padding: 0.3rem 1rem;
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: 4px;
  background: rgba(0, 229, 255, 0.04);
  color: rgba(0, 229, 255, 0.4);
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover {
  border-color: rgba(0, 229, 255, 0.5);
  color: #00e5ff;
  background: rgba(0, 229, 255, 0.08);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.15);
}

.toggle-btn.active {
  background: rgba(0, 229, 255, 0.12);
  border-color: #00e5ff;
  color: #00e5ff;
  box-shadow: 0 0 14px rgba(0, 229, 255, 0.35), inset 0 0 8px rgba(0, 229, 255, 0.08);
}
</style>
