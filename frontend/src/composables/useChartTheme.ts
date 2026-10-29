/**
 * ECharts 主题色读取（跟随深色/浅色切换）
 */
import { useThemeStore } from '@/stores/theme'
import { computed } from 'vue'

function getCssVar(name: string, fallback: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

export function useChartTheme() {
  const themeStore = useThemeStore()

  const colors = computed(() => ({
    cyan: getCssVar('--accent-cyan', '#3d5a80'),
    blue: getCssVar('--accent-blue', '#4a6fa5'),
    purple: getCssVar('--accent-purple', '#5c6b7a'),
    orange: getCssVar('--accent-orange', '#b45309'),
    red: getCssVar('--accent-red', '#b91c1c'),
    label: getCssVar('--chart-label', '#6b7280'),
    bg: getCssVar('--bg-primary', '#f5f6f8'),
    border: getCssVar('--border-color', 'rgba(31,41,55,0.1)'),
    isDark: themeStore.mode === 'dark',
  }))

  return { colors, themeStore }
}
