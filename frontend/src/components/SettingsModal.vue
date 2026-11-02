<template>
  <div v-if="ui.settingsOpen" class="settings-layer">
    <div class="settings-scrim" @click="ui.closeSettings()" />
    <div ref="dialog" class="settings" role="dialog" aria-modal="true" aria-label="設定" tabindex="-1">
      <header class="settings-head">
        <h2>設定</h2>
        <button class="icon-btn" aria-label="關閉" @click="ui.closeSettings()"><Icon name="close" /></button>
      </header>

      <div class="settings-body">
        <section>
          <h3>FinMind Token</h3>
          <p class="hint">
            買進評分與每日籌碼需要 FinMind token。Token 只存放在伺服器，不會顯示、也不會存進瀏覽器。
          </p>

          <p class="status" :class="{ ok: status.configured }">
            <span class="dot" />
            <template v-if="status.configured">已設定<span v-if="status.hint" class="num"> {{ status.hint }}</span></template>
            <template v-else>未設定</template>
          </p>

          <form class="token-form" @submit.prevent="onSave">
            <label for="finmind-token">{{ status.configured ? '更換 Token' : '貼上 Token' }}</label>
            <input
              id="finmind-token"
              v-model="input"
              type="password"
              autocomplete="off"
              spellcheck="false"
              placeholder="貼上 FinMind token…"
            />
            <div class="actions">
              <button type="submit" class="btn-save" :disabled="loading">儲存</button>
              <button v-if="status.configured" type="button" class="btn-clear" :disabled="loading" @click="onRemove">移除</button>
            </div>
            <p v-if="error" class="msg err" role="alert">{{ error }}</p>
            <p v-else-if="saved" class="msg ok" role="status">{{ saved }}</p>
          </form>

          <p class="hint">儲存後於下一次評分作業生效；若要立即套用，可在總覽按「重新計算」。未設定時會使用伺服器環境變數 <code>FINMIND_TOKEN</code>。</p>
          <p class="hint warn">此設定無需登入，請僅在可信任的內部網路使用。</p>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, toRef, watch } from 'vue'
import { useUiStore } from '../stores/uiStore'
import { useDialog } from '../composables/useDialog'
import { useFinmindToken } from '../composables/useFinmindToken'
import Icon from './Icon.vue'

const ui = useUiStore()
const { dialog } = useDialog(toRef(ui, 'settingsOpen'), () => ui.closeSettings())
const { status, loading, error, load, save, remove } = useFinmindToken()

const input = ref('')
const saved = ref('')

watch(() => ui.settingsOpen, (open) => {
  input.value = ''
  if (open) {
    saved.value = ''
    load()
  }
})

async function onSave() {
  if (!input.value.trim()) return
  saved.value = ''
  if (await save(input.value)) {
    input.value = ''
    saved.value = 'Token 已儲存'
  }
}

async function onRemove() {
  saved.value = ''
  if (await remove()) saved.value = 'Token 已移除'
}
</script>

<style scoped>
.settings-layer {
  position: fixed;
  inset: 0;
  z-index: 330;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.settings-scrim { position: absolute; inset: 0; background: var(--scrim); }
.settings {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(460px, 100%);
  max-height: 84vh;
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  outline: none;
}
.settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px 20px;
  border-bottom: 1px solid var(--border-subtle);
}
.settings-head h2 { font-size: 1.125rem; font-weight: 700; }
.settings-body { overflow-y: auto; padding: 14px 20px 20px; font-size: 0.875rem; line-height: 1.6; color: var(--text-secondary); }
.settings-body h3 { margin-bottom: 4px; font-size: 0.9375rem; font-weight: 600; color: var(--text-primary); }
.hint { margin: 6px 0; font-size: 0.8125rem; }
.hint.warn { color: var(--text-muted); }
code { font-size: 0.75rem; }

.status { display: flex; align-items: center; gap: 6px; margin: 10px 0; font-weight: 600; color: var(--text-secondary); }
.status.ok { color: var(--text-primary); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); }
.status.ok .dot { background: var(--accent); }

.token-form { display: flex; flex-direction: column; gap: 6px; }
.token-form label { font-size: 0.8125rem; color: var(--text-secondary); }
.token-form input {
  min-height: 36px;
  padding: 0 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-primary);
  font-size: 0.875rem;
}
.token-form input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.actions { display: flex; gap: 8px; margin-top: 4px; }
.actions button {
  min-height: 34px;
  padding: 0 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  background: transparent;
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 500;
}
.actions .btn-save { background: var(--accent); border-color: var(--accent); color: #fff; }
.actions button:disabled { opacity: 0.5; }
.msg { margin: 2px 0 0; font-size: 0.8125rem; }
.msg.err { color: var(--pct-up); }
.msg.ok { color: var(--text-primary); }
</style>
