<template>
  <div class="mode-toggle">
    <!-- 模式切換 -->
    <button
      id="btn-volume"
      :class="['toggle-btn', mode === 'volume' ? 'active' : '']"
      @click="emit('mode-change', 'volume')"
    >
      成交量 TOP 480
    </button>
    <button
      id="btn-turnover"
      :class="['toggle-btn', mode === 'turnover' ? 'active' : '']"
      @click="emit('mode-change', 'turnover')"
    >
      週轉率 TOP 480
    </button>
    <button
      id="btn-etf"
      :class="['toggle-btn', 'toggle-btn--etf', mode === 'etf' ? 'active' : '']"
      @click="emit('mode-change', 'etf')"
    >
      ETF 週轉率
    </button>
    <button
      id="btn-buy-score"
      :class="['toggle-btn', 'toggle-btn--score', mode === 'buy_score' ? 'active' : '']"
      @click="emit('mode-change', 'buy_score')"
    >
      買進評分
    </button>

    <!-- 分隔線 -->
    <span class="divider" />

    <!-- 格子大小切換（桌機 > 1024px）-->
    <div v-if="!isMobile && !isTablet" class="grid-size-group" title="卡片大小">
      <button
        v-for="n in [6, 5, 4]"
        :key="n"
        :class="['size-btn', gridSize === n ? 'active' : '']"
        @click="emit('grid-size-change', n)"
      >{{ n }}×{{ n }}</button>
    </div>

    <!-- 密度切換（平板 769–1024px）-->
    <div v-else-if="isTablet" class="grid-size-group tablet-density-group" title="每頁卡片數">
      <button
        v-for="d in ['3x4', '4x4']"
        :key="d"
        :class="['size-btn', tabletDensity === d ? 'active' : '']"
        @click="emit('tablet-density-change', d)"
      >{{ d }}</button>
    </div>

    <!-- 密度切換（手機 ≤ 768px）-->
    <div v-else class="grid-size-group density-group" title="每頁卡片數">
      <button
        v-for="d in ['2x2', '2x3', '3x3']"
        :key="d"
        :class="['size-btn', mobileDensity === d ? 'active' : '']"
        @click="emit('density-change', d)"
      >{{ d }}</button>
    </div>
  </div>
</template>

<script setup>
import { useBreakpoint } from '../composables/useBreakpoint'

const props = defineProps({
  mode:          { type: String,  required: true },
  gridSize:      { type: Number,  default: 6 },
  mobileDensity: { type: String,  default: '2x3' },
  tabletDensity: { type: String,  default: '3x4' },
})
const emit = defineEmits(['mode-change', 'grid-size-change', 'density-change', 'tablet-density-change'])

const { isMobile, isTablet } = useBreakpoint()
</script>

<style scoped>
.mode-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow-x: auto;
  scrollbar-width: none;
}
.mode-toggle::-webkit-scrollbar { display: none; }

.toggle-btn {
  padding: 0.3rem 1rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--border-subtle);
  color: color-mix(in srgb, var(--accent) 40%, transparent);
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  flex-shrink: 0;
}

.toggle-btn:hover {
  border-color: var(--border-strong);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  box-shadow: 0 0 10px color-mix(in srgb, var(--accent) 15%, transparent);
}

.toggle-btn.active {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: 0 0 14px color-mix(in srgb, var(--accent) 35%, transparent),
              inset 0 0 8px color-mix(in srgb, var(--accent) 8%, transparent);
}

/* ETF button — amber accent */
.toggle-btn--etf {
  border-color: color-mix(in srgb, var(--accent-etf) 20%, transparent);
  color: color-mix(in srgb, var(--accent-etf) 45%, transparent);
  background: color-mix(in srgb, var(--accent-etf) 4%, transparent);
}

.toggle-btn--etf:hover {
  border-color: color-mix(in srgb, var(--accent-etf) 55%, transparent);
  color: var(--accent-etf);
  background: color-mix(in srgb, var(--accent-etf) 8%, transparent);
  box-shadow: 0 0 10px color-mix(in srgb, var(--accent-etf) 18%, transparent);
}

.toggle-btn--etf.active {
  background: color-mix(in srgb, var(--accent-etf) 12%, transparent);
  border-color: var(--accent-etf);
  color: var(--accent-etf);
  box-shadow: 0 0 14px color-mix(in srgb, var(--accent-etf) 38%, transparent),
              inset 0 0 8px color-mix(in srgb, var(--accent-etf) 8%, transparent);
}

/* 買進評分 button — score accent */
.toggle-btn--score {
  border-color: color-mix(in srgb, var(--accent-score) 20%, transparent);
  color: color-mix(in srgb, var(--accent-score) 45%, transparent);
  background: color-mix(in srgb, var(--accent-score) 4%, transparent);
}

.toggle-btn--score:hover {
  border-color: color-mix(in srgb, var(--accent-score) 55%, transparent);
  color: var(--accent-score);
  background: color-mix(in srgb, var(--accent-score) 8%, transparent);
  box-shadow: 0 0 10px color-mix(in srgb, var(--accent-score) 18%, transparent);
}

.toggle-btn--score.active {
  background: color-mix(in srgb, var(--accent-score) 12%, transparent);
  border-color: var(--accent-score);
  color: var(--accent-score);
  box-shadow: 0 0 14px color-mix(in srgb, var(--accent-score) 38%, transparent),
              inset 0 0 8px color-mix(in srgb, var(--accent-score) 8%, transparent);
}

.divider {
  width: 1px;
  height: 1.4rem;
  background: var(--border-default);
  flex-shrink: 0;
}

/* 格子大小 / 密度 群組 */
.grid-size-group {
  display: flex;
  gap: 3px;
  background: var(--border-subtle);
  border: 1px solid var(--border-default);
  border-radius: 4px;
  padding: 2px;
  flex-shrink: 0;
}

.size-btn {
  padding: 0.18rem 0.55rem;
  border-radius: 3px;
  border: none;
  background: transparent;
  color: color-mix(in srgb, var(--accent) 38%, transparent);
  font-size: 0.68rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.size-btn:hover {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}
.size-btn.active {
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  color: var(--accent);
  box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 25%, transparent);
}

/* Tablet density group uses ETF accent to differentiate from desktop grid-size */
.tablet-density-group .size-btn {
  color: color-mix(in srgb, var(--accent-etf) 38%, transparent);
}
.tablet-density-group .size-btn:hover {
  color: var(--accent-etf);
  background: color-mix(in srgb, var(--accent-etf) 10%, transparent);
}
.tablet-density-group .size-btn.active {
  background: color-mix(in srgb, var(--accent-etf) 16%, transparent);
  color: var(--accent-etf);
  box-shadow: 0 0 6px color-mix(in srgb, var(--accent-etf) 25%, transparent);
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

@media (max-width: 640px) {
  .toggle-btn {
    padding: 0.25rem 0.55rem;
    font-size: 0.65rem;
    letter-spacing: 0.03em;
  }
  .size-btn {
    padding: 0.2rem 0.5rem;
    font-size: 0.65rem;
    min-height: 32px;
  }
}
</style>
