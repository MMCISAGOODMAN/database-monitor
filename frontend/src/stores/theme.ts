/**
 * 主题状态管理（深色 / 浅色切换）
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  const saved = localStorage.getItem('theme') as ThemeMode | null
  // v2.1 默认浅色灰白主题
  const mode = ref<ThemeMode>(saved === 'dark' ? 'dark' : 'light')

  function applyTheme(theme: ThemeMode) {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function setTheme(theme: ThemeMode) {
    mode.value = theme
  }

  watch(mode, (v) => applyTheme(v), { immediate: true })

  return { mode, toggle, setTheme }
})
