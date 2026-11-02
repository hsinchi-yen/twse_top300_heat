<template>
  <div class="pager">
    <span class="pager-range num">{{ start + 1 }}–{{ end }} / {{ count }}</span>
    <div class="pager-controls">
      <button class="icon-btn page-btn page-prev" :disabled="page === 0" aria-label="上一頁" @click="emit('update:page', page - 1)">
        <Icon name="left" />
      </button>
      <span class="pager-page num">{{ page + 1 }} / {{ total }}</span>
      <button class="icon-btn page-btn page-next" :disabled="page >= total - 1" aria-label="下一頁" @click="emit('update:page', page + 1)">
        <Icon name="right" />
      </button>
    </div>
    <slot />
  </div>
</template>

<script setup>
import Icon from './Icon.vue'

defineProps({
  page:  { type: Number, required: true },
  total: { type: Number, required: true },
  start: { type: Number, required: true },
  end:   { type: Number, required: true },
  count: { type: Number, required: true },
})
const emit = defineEmits(['update:page'])
</script>

<style scoped>
.pager {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  min-height: 34px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.pager-range { color: var(--text-muted); }

.pager-controls {
  display: flex;
  align-items: center;
  gap: 2px;
  margin: 0 auto;
}

.pager-page { min-width: 52px; text-align: center; }

@media (max-width: 768px) {
  .pager :deep(.page-btn) { width: 44px; height: 44px; }
}
</style>
