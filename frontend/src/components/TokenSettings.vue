<template>
  <div class="token-wrapper">
    <button
      class="token-btn"
      :class="{ 'token-set': hasToken }"
      @click="togglePanel"
      title="FinMind Token 設定"
    >
      🔑
    </button>

    <div v-if="open" class="token-panel">
      <div class="token-panel-header">
        <span class="panel-title">FinMind Token</span>
        <button class="btn-close" @click="closePanel">✕</button>
      </div>

      <div class="token-status-row">
        <span class="token-status">{{ maskedToken }}</span>
      </div>

      <input
        v-model="inputValue"
        class="token-input"
        type="password"
        placeholder="貼上 FinMind token..."
        autocomplete="off"
      />

      <div class="token-actions">
        <button class="btn-save" @click="saveToken">儲存</button>
        <button v-if="hasToken" class="btn-clear" @click="clearToken">清除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { fetchScores } from '../composables/useScoreData'

const STORAGE_KEY = 'finmind_token'

const open = ref(false)
const inputValue = ref('')
const storedToken = ref(localStorage.getItem(STORAGE_KEY) || '')

const hasToken = computed(() => !!storedToken.value)

const maskedToken = computed(() => {
  if (!storedToken.value) return '未設定'
  return storedToken.value.slice(0, 8) + '****'
})

function togglePanel() {
  open.value = !open.value
  if (open.value) inputValue.value = ''
}

function closePanel() {
  open.value = false
}

function saveToken() {
  const val = inputValue.value.trim()
  if (!val) return
  localStorage.setItem(STORAGE_KEY, val)
  storedToken.value = val
  open.value = false
  fetchScores()
}

function clearToken() {
  localStorage.removeItem(STORAGE_KEY)
  storedToken.value = ''
  open.value = false
  fetchScores()
}
</script>

<style scoped>
.token-wrapper {
  position: relative;
  display: inline-block;
}

.token-btn {
  background: transparent;
  border: 1px solid #444;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  font-size: 1rem;
  padding: 2px 6px;
  line-height: 1;
}

.token-btn.token-set {
  border-color: #4caf8a;
  color: #4caf8a;
}

.token-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  background: #1e1e1e;
  border: 1px solid #444;
  border-radius: 6px;
  padding: 10px 12px;
  width: 280px;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}

.token-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.panel-title {
  font-size: 0.78rem;
  color: #aaa;
  font-weight: 600;
}

.btn-close {
  background: transparent;
  border: none;
  color: #888;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0;
}

.token-status-row {
  margin-bottom: 8px;
}

.token-status {
  font-size: 0.72rem;
  color: #777;
  font-family: monospace;
}

.token-input {
  width: 100%;
  background: #111;
  border: 1px solid #555;
  border-radius: 4px;
  color: #ddd;
  font-size: 0.75rem;
  padding: 5px 8px;
  box-sizing: border-box;
  margin-bottom: 8px;
}

.token-actions {
  display: flex;
  gap: 8px;
}

.btn-save,
.btn-clear {
  flex: 1;
  border: 1px solid #555;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.72rem;
  padding: 4px 0;
}

.btn-save {
  background: #2a4a3a;
  color: #4caf8a;
  border-color: #4caf8a;
}

.btn-clear {
  background: #3a2a2a;
  color: #cf6679;
  border-color: #cf6679;
}
</style>
