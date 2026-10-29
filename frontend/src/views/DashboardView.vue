<template>
  <!-- 监控大屏主视图 -->
  <div class="dashboard" :class="{ fullscreen: isFullscreen }">
    <!-- 顶部标题栏 -->
    <header class="dashboard-header">
      <div class="header-left">
        <h1 class="dashboard-title">数据库监控大屏</h1>
        <span class="header-time">{{ currentTime }}</span>
      </div>
      <div class="header-right">
        <div class="toolbar-group">
          <select v-model="refreshInterval" class="toolbar-select" @change="onRefreshChange">
            <option :value="5">刷新 5s</option>
            <option :value="10">刷新 10s</option>
            <option :value="30">刷新 30s</option>
          </select>
          <ThemeToggle />
          <button class="toolbar-btn icon-only" :title="isFullscreen ? '退出全屏' : '全屏'" @click="toggleFullscreen">
            <el-icon><component :is="isFullscreen ? 'Close' : 'FullScreen'" /></el-icon>
          </button>
          <button v-if="isAdmin" class="toolbar-btn" @click="$router.push('/manage')">
            <el-icon><Setting /></el-icon>管理
          </button>
          <button v-if="isAdmin" class="toolbar-btn" @click="$router.push('/manage?tab=instances')">
            对比
          </button>
          <button class="toolbar-btn" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>退出
          </button>
        </div>
        <span class="status-pill" :class="{ online: wsConnected }">
          {{ wsConnected ? '实时连接' : '连接断开' }}
        </span>
      </div>
    </header>

    <!-- KPI 卡片区 -->
    <section class="kpi-section">
      <KPICard label="监控总数 / 异常" :value="kpi.total_instances" :trend="kpi.total_instances_trend"
        icon="Monitor" icon-color="#3d5a80" />
      <KPICard label="平均 QPS" :value="kpi.avg_qps" :trend="kpi.avg_qps_trend"
        icon="TrendCharts" icon-color="#4a6fa5" />
      <KPICard label="总连接数" :value="kpi.total_connections" :trend="kpi.total_connections_trend"
        icon="Connection" icon-color="#5c6b7a" />
      <KPICard label="今日告警" :value="kpi.today_alerts" :trend="kpi.today_alerts_trend"
        icon="Bell" icon-color="#b45309" />
      <KPICard label="系统健康度" :value="kpi.health_score" unit="%" :trend="kpi.health_score_trend"
        icon="CircleCheck" icon-color="#3d5a80" />
    </section>

    <!-- 无数据引导 -->
    <div v-if="isEmpty" class="empty-guide glass-card">
      <el-icon :size="48" color="#3d5a80"><Monitor /></el-icon>
      <h3>暂无监控数据</h3>
      <p>系统尚未配置数据库实例，或采集器还未完成首次采集。</p>
      <el-button v-if="isAdmin" type="primary" @click="$router.push('/manage')">前往添加实例</el-button>
      <p class="empty-tip">Docker 部署会自动注册 PostgreSQL 和 Redis 演示实例，请刷新页面或等待 30 秒。</p>
    </div>

    <!-- 中间三栏区域 -->
    <section class="main-section">
      <div class="col-left"><InstanceList /></div>
      <div class="col-center"><TrendChart /></div>
      <div class="col-right"><AlertPanel /></div>
    </section>

    <!-- 底部：热力图 + 告警统计 -->
    <section class="bottom-section">
      <div class="bottom-left"><TreemapChart /></div>
      <div class="bottom-right"><AlertStatsChart /></div>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 监控大屏主视图
 * 1920x1080 自适应布局，暗色主题
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import { useDashboardStore } from '@/stores/dashboard'
import { useWebSocket } from '@/composables/useWebSocket'
import KPICard from '@/components/KPICard.vue'
import InstanceList from '@/components/InstanceList.vue'
import TrendChart from '@/components/TrendChart.vue'
import AlertPanel from '@/components/AlertPanel.vue'
import TreemapChart from '@/components/TreemapChart.vue'
import AlertStatsChart from '@/components/AlertStatsChart.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'

const router = useRouter()
const authStore = useAuthStore()
const store = useDashboardStore()

const kpi = computed(() => store.kpi)
const isAdmin = computed(() => authStore.role === 'admin')
const isEmpty = computed(() => store.instances.length === 0 && kpi.value.total_instances === 0)
const refreshInterval = computed({
  get: () => store.refreshInterval,
  set: (v) => { store.refreshInterval = v },
})

const currentTime = ref('')
const isFullscreen = ref(false)
let timeTimer: ReturnType<typeof setInterval> | null = null

// WebSocket 实时推送
const { connected: wsConnected } = useWebSocket('/ws/metrics', (msg) => {
  if (msg.type === 'metrics_update') {
    store.updateFromWebSocket(msg.data)
  }
})

useWebSocket('/ws/alerts', (msg) => {
  if (msg.type === 'alerts_update') {
    store.updateAlertsFromWebSocket(msg.data)
  }
})

onMounted(async () => {
  // 初始加载
  await Promise.all([
    store.fetchKPI(),
    store.fetchInstances(),
    store.fetchTreemap(),
    store.fetchAlerts(),
  ])

  // 默认选中第一个实例
  if (store.instances.length > 0) {
    store.selectedInstanceId = store.instances[0].id
  }

  // 时钟
  updateTime()
  timeTimer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeTimer) clearInterval(timeTimer)
})

function updateTime() {
  currentTime.value = dayjs().format('YYYY-MM-DD HH:mm:ss')
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

function onRefreshChange() {
  // WebSocket 已处理实时刷新，此处可用于 HTTP 轮询备用
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped lang="scss">
.dashboard {
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-rows: 60px 110px 1fr 220px;
  gap: 12px;
  padding: 12px 16px;
  background:
    linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-elevated) 100%);

  &.fullscreen {
    padding: 8px;
  }
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dashboard-title {
  font-size: 22px;
  font-weight: 700;
  background: linear-gradient(90deg, var(--title-gradient-from), var(--title-gradient-to));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.header-time {
  font-size: 13px;
  color: var(--text-secondary);
  margin-left: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kpi-section {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.main-section {
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  gap: 12px;
  min-height: 0;
}

.col-left, .col-center, .col-right {
  min-height: 0;
  overflow: hidden;
}

.bottom-section {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 12px;
  min-height: 0;
}

.bottom-left, .bottom-right {
  min-height: 0;
  overflow: hidden;
}

.empty-guide {
  grid-row: 2 / 4;
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  z-index: 10;

  h3 { color: var(--accent-cyan); font-size: 20px; }
  p { color: var(--text-secondary); font-size: 14px; }
  .empty-tip { font-size: 12px; opacity: 0.7; }
}
</style>
