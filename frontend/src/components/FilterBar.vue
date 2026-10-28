<template>
  <div class="filter-bar">
    <div class="filter-row">
      <button
        v-for="p in PRESETS"
        :key="p.key"
        class="preset-btn"
        :class="{ active: currentPreset === p.key }"
        :title="p.conditions.map(c => CONDITIONS[c].label).join(' ＋ ')"
        @click="onPreset(p.key)"
      >{{ p.label }}</button>

      <button
        class="custom-toggle"
        :class="{ active: showCustom || (filters.active.length && !currentPreset) }"
        :aria-expanded="showCustom"
        @click="showCustom = !showCustom"
      >自訂 {{ showCustom ? '▴' : '▾' }}</button>

      <template v-if="filters.active.length">
        <span class="filter-count num">符合 {{ matched }} / {{ total }}</span>
        <button class="filter-clear" @click="filters.clear()">清除</button>
      </template>
    </div>

    <div v-if="showCustom" class="filter-row filter-custom">
      <button
        v-for="(cond, key) in CONDITIONS"
        :key="key"
        :data-cond="key"
        class="cond-btn"
        :class="{ active: filters.active.includes(key) }"
        :aria-pressed="filters.active.includes(key)"
        @click="filters.toggle(key)"
      >{{ cond.label }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useFilterStore } from '../stores/filterStore'
import { CONDITIONS, PRESETS, presetFor } from '../utils/stockFilters'

defineProps({
  matched: { type: Number, default: 0 },
  total:   { type: Number, default: 0 },
})

const filters = useFilterStore()
const showCustom = ref(false)
const currentPreset = computed(() => (filters.active.length ? presetFor(filters.active) : null))

// 再點一次目前的組合 = 取消篩選
function onPreset(key) {
  if (currentPreset.value === key) filters.clear()
  else filters.applyPreset(key)
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
}
.filter-row::-webkit-scrollbar { display: none; }

.preset-btn,
.custom-toggle,
.cond-btn,
.filter-clear {
  flex-shrink: 0;
  font-size: 0.75rem;
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: var(--toggle-btn-muted-bg);
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.preset-btn:hover,
.custom-toggle:hover,
.cond-btn:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.preset-btn.active,
.cond-btn.active,
.custom-toggle.active {
  color: var(--sig-strong_buy-fg);
  border-color: var(--sig-strong_buy-border);
  background: var(--sig-strong_buy-bg);
  font-weight: 700;
}

.filter-count {
  font-size: 0.75rem;
  color: var(--text-primary);
  white-space: nowrap;
}

.filter-clear {
  border-style: dashed;
}

@media (max-width: 768px) {
  .preset-btn,
  .custom-toggle,
  .cond-btn,
  .filter-clear {
    font-size: 0.85rem;
    min-height: 36px;
  }
}
</style>
