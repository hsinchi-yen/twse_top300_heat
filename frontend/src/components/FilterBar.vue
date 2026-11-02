<template>
  <div class="filter-bar">
    <div class="filter-row">
      <slot name="lead" />

      <button
        v-for="p in PRESETS"
        :key="p.key"
        class="chip-btn preset-btn"
        :class="{ active: currentPreset === p.key }"
        :title="describe(p.conditions)"
        @click="onPreset(p.key)"
      >{{ p.label }}</button>

      <button
        class="chip-btn custom-toggle"
        :class="{ active: showCustom || (filters.active.length && !currentPreset) }"
        :aria-expanded="showCustom"
        @click="showCustom = !showCustom"
      >自訂 {{ showCustom ? '▴' : '▾' }}</button>

      <button
        v-if="filters.sector"
        class="chip-btn active sector-chip"
        :aria-label="`移除族群篩選 ${filters.sector}`"
        @click="filters.setSector('')"
      >{{ filters.sector }} ×</button>

      <span v-if="filters.active.length || filters.sector" class="filter-count num">符合 {{ matched }} / {{ total }}</span>
      <button v-if="filters.active.length" class="chip-btn filter-clear" @click="filters.clear()">清除</button>

      <span class="filter-spacer" />
      <slot name="trail" />
    </div>

    <div v-if="showCustom" class="filter-row filter-custom">
      <button
        v-for="(cond, key) in CONDITIONS"
        :key="key"
        :data-cond="key"
        class="chip-btn cond-btn"
        :class="{ active: filters.active.includes(key) }"
        :aria-pressed="filters.active.includes(key)"
        @click="filters.toggle(key)"
      >{{ cond.label }}</button>
    </div>

    <p v-else-if="filters.active.length" class="filter-hint">{{ describe(filters.active) }}</p>
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

const describe = (keys) => keys.map(k => CONDITIONS[k]?.label).filter(Boolean).join(' ＋ ')

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
  gap: 6px;
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

.filter-count {
  margin-left: 4px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.filter-clear { border-style: dashed; }
.filter-spacer { flex: 1; min-width: 8px; }

.filter-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .filter-row :deep(.chip-btn) { min-height: 36px; }
}
</style>
