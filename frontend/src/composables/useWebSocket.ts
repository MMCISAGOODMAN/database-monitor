/**
 * WebSocket 连接 composable
 * 用于实时指标和告警推送；支持指数退避重连
 */
import { onMounted, onUnmounted, ref } from 'vue'

export function useWebSocket(path: string, onMessage: (data: any) => void) {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let attempt = 0
  let disposed = false

  const BASE_DELAY_MS = 1000
  const MAX_DELAY_MS = 30000

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function scheduleReconnect() {
    if (disposed) return
    clearReconnectTimer()
    const delay = Math.min(BASE_DELAY_MS * Math.pow(2, attempt), MAX_DELAY_MS)
    attempt += 1
    reconnectTimer = setTimeout(connect, delay)
  }

  function connect() {
    if (disposed) return
    clearReconnectTimer()

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host

    try {
      ws = new WebSocket(`${protocol}//${host}${path}`)
    } catch {
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      connected.value = true
      attempt = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        onMessage(msg)
      } catch (e) {
        console.error('WebSocket 消息解析失败', e)
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  onMounted(() => connect())

  onUnmounted(() => {
    disposed = true
    clearReconnectTimer()
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
  })

  return { connected }
}
