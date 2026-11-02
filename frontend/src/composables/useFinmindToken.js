/**
 * useFinmindToken.js — write-only FinMind token settings.
 * The token is sent to the backend once and never kept in the browser:
 * only {configured, hint} comes back.
 */

import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const URL = `${API_BASE}/api/settings/finmind-token`

export function useFinmindToken() {
  const status = ref({ configured: false, hint: null })
  const loading = ref(false)
  const error = ref('')

  async function call(method, body) {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch(URL, {
        method,
        ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
      })
      if (res.status === 422) {
        error.value = 'Token 格式不正確（不可為空、含空白或過長）'
        return false
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      status.value = await res.json()
      return true
    } catch {
      error.value = '無法連線到伺服器，請稍後再試'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    status, loading, error,
    load: () => call('GET'),
    save: (token) => call('PUT', { token: token.trim() }),
    remove: () => call('DELETE'),
  }
}
