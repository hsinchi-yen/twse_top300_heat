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
  background: var(--toggle-btn-muted-bg);
  color: var(--toggle-btn-muted-color);
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
  background: var(--toggle-btn-hover-bg);
  box-shadow: 0 0 10px var(--toggle-btn-hover-shadow);
}

.toggle-btn.active {
  background: var(--toggle-btn-active-bg);
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: 0 0 14px var(--toggle-btn-active-shadow),
              inset 0 0 8px var(--toggle-btn-hover-bg);
}

/* ETF button — amber accent */
.toggle-btn--etf {
  border-color: color-mix(in srgb, var(--accent-etf) 20%, transparent);
  color: var(--toggle-etf-muted-color);
  background: var(--toggle-etf-muted-bg);
}

.toggle-btn--etf:hover {
  border-color: color-mix(in srgb, var(--accent-etf) 55%, transparent);
  color: var(--accent-etf);
  background: var(--toggle-etf-hover-bg);
  box-shadow: 0 0 10px var(--toggle-etf-hover-shadow);
}

.toggle-btn--etf.active {
  background: var(--toggle-etf-active-bg);
  border-color: var(--accent-etf);
  color: var(--accent-etf);
  box-shadow: 0 0 14px var(--toggle-etf-active-shadow),
              inset 0 0 8px var(--toggle-etf-hover-bg);
}

/* 買進評分 button — score accent */
.toggle-btn--score {
  border-color: color-mix(in srgb, var(--accent-score) 20%, transparent);
  color: var(--toggle-score-muted-color);
  background: var(--toggle-score-muted-bg);
}

.toggle-btn--score:hover {
  border-color: color-mix(in srgb, var(--accent-score) 55%, transparent);
  color: var(--accent-score);
  background: var(--toggle-score-hover-bg);
  box-shadow: 0 0 10px var(--toggle-score-hover-shadow);
}

.toggle-btn--score.active {
  background: var(--toggle-score-active-bg);
  border-color: var(--accent-score);
  color: var(--accent-score);
  box-shadow: 0 0 14px var(--toggle-score-active-shadow),
              inset 0 0 8px var(--toggle-score-hover-bg);
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
  color: var(--size-btn-muted-color);
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
  background: var(--size-btn-hover-bg);
}
.size-btn.active {
  background: var(--size-btn-active-bg);
  color: var(--accent);
  box-shadow: 0 0 6px var(--size-btn-active-shadow);
}

/* Tablet density group uses ETF accent to differentiate from desktop grid-size */
.tablet-density-group .size-btn {
  color: var(--tablet-size-btn-muted-color);
}
.tablet-density-group .size-btn:hover {
  color: var(--accent-etf);
  background: var(--tablet-size-btn-hover-bg);
}
.tablet-density-group .size-btn.active {
  background: var(--tablet-size-btn-active-bg);
  color: var(--accent-etf);
  box-shadow: 0 0 6px var(--tablet-size-btn-active-shadow);
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
