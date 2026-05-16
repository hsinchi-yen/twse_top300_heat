<template>
  <div class="mode-toggle">
    <!-- 模式切換 -->
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
    <button
      id="btn-etf"
      :class="['toggle-btn', 'toggle-btn--etf', mode === 'etf' ? 'active' : '']"
      @click="emit('mode-change', 'etf')"
    >
      ETF 週轉率
    </button>

    <!-- 分隔線 -->
    <span class="divider" />

    <!-- 格子大小切換 -->
    <div class="grid-size-group" title="卡片大小">
      <button
        v-for="n in [6, 5, 4]"
        :key="n"
        :class="['size-btn', gridSize === n ? 'active' : '']"
        @click="emit('grid-size-change', n)"
      >{{ n }}×{{ n }}</button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  mode:     { type: String,  required: true },
  gridSize: { type: Number,  default: 6 },
})
const emit = defineEmits(['mode-change', 'grid-size-change'])
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

/* ETF button — amber accent */
.toggle-btn--etf {
  border-color: rgba(255, 179, 0, 0.2);
  color: rgba(255, 179, 0, 0.45);
  background: rgba(255, 179, 0, 0.04);
}

.toggle-btn--etf:hover {
  border-color: rgba(255, 179, 0, 0.55);
  color: #ffb300;
  background: rgba(255, 179, 0, 0.08);
  box-shadow: 0 0 10px rgba(255, 179, 0, 0.18);
}

.toggle-btn--etf.active {
  background: rgba(255, 179, 0, 0.12);
  border-color: #ffb300;
  color: #ffb300;
  box-shadow: 0 0 14px rgba(255, 179, 0, 0.38), inset 0 0 8px rgba(255, 179, 0, 0.08);
}

.divider {
  width: 1px;
  height: 1.4rem;
  background: rgba(0, 229, 255, 0.15);
  flex-shrink: 0;
}

/* 格子大小群組 */
.grid-size-group {
  display: flex;
  gap: 3px;
  background: rgba(0, 229, 255, 0.03);
  border: 1px solid rgba(0, 229, 255, 0.12);
  border-radius: 4px;
  padding: 2px;
}

.size-btn {
  padding: 0.18rem 0.55rem;
  border-radius: 3px;
  border: none;
  background: transparent;
  color: rgba(0, 229, 255, 0.38);
  font-size: 0.68rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.size-btn:hover {
  color: #00e5ff;
  background: rgba(0, 229, 255, 0.1);
}
.size-btn.active {
  background: rgba(0, 229, 255, 0.16);
  color: #00e5ff;
  box-shadow: 0 0 6px rgba(0, 229, 255, 0.25);
}

@media (max-width: 1366px), (max-height: 768px) {
  .toggle-btn {
    padding: 0.2rem 0.65rem;
    font-size: 0.68rem;
  }
  .size-btn {
    padding: 0.14rem 0.42rem;
    font-size: 0.62rem;
  }
}
</style>
