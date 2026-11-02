/**
 * filterStore.js — active 篩選條件 (per-viewer convenience → localStorage).
 * Storage can be blocked / corrupted; any failure falls back to "no filter".
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { CONDITIONS, PRESETS } from '../utils/stockFilters'

const STORAGE_KEY = 'stock_filters'

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(raw) ? raw.filter(k => k in CONDITIONS) : []
  } catch {
    return []
  }
}

function save(active) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(active))
  } catch {
    // storage unavailable (private mode / quota) — filter still works for this session
  }
}

export const useFilterStore = defineStore('filters', () => {
  const active = ref(load())
  // Set by the overview's sector rows; a one-off drill-down, so it is not persisted.
  const sector = ref('')

  function set(keys) {
    active.value = keys.filter(k => k in CONDITIONS)
    save(active.value)
  }

  function toggle(key) {
    set(active.value.includes(key) ? active.value.filter(k => k !== key) : [...active.value, key])
  }

  function applyPreset(presetKey) {
    const preset = PRESETS.find(p => p.key === presetKey)
    if (preset) set([...preset.conditions])
  }

  function clear() {
    set([])
  }

  function setSector(name) {
    sector.value = name
  }

  return { active, sector, toggle, applyPreset, clear, setSector }
})
