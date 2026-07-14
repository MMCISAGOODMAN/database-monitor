<template>
  <div class="detail-page">
    <header class="detail-header">
      <div class="header-left">
        <el-button @click="$router.back()" icon="ArrowLeft">返回大屏</el-button>
        <h2>{{ snapshot?.instance?.name || '实例详情' }}</h2>
        <span class="status-dot" :class="snapshot?.status"></span>
        <span v-if="dbType" class="db-type-tag">{{ dbType }}</span>
      </div>
      <ThemeToggle />
    </header>

    <div v-if="loading && !snapshot" class="state-tip">加载中…</div>
    <div v-else-if="loadError && !snapshot" class="state-tip error">{{ loadError }}</div>

    <div class="detail-grid" v-if="snapshot">
      <!-- 指标概览卡片 -->
      <div class="metric-cards">
        <div class="metric-card glass-card" v-for="m in metricCards" :key="m.key">
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-value">{{ formatMetric(m.key, m.suffix) }}</div>
        </div>
      </div>

      <!-- 指标趋势图 -->
      <div class="detail-card glass-card" v-for="metric in chartMetrics" :key="metric.name">
        <div class="card-title">{{ metric.label }}</div>
        <div :ref="(el) => setChartRef(metric.name, el as HTMLElement)" class="mini-chart"></div>
      </div>

      <!-- 慢查询列表（仅关系型） -->
      <div
        v-if="dbType === 'mysql' || dbType === 'postgresql'"
        class="detail-card glass-card slow-query-card"
      >
        <div class="card-title">慢查询记录（最近 {{ slowQueries.length }} 条）</div>
        <el-table :data="slowQueries" size="small" max-height="300" style="width: 100%">
          <el-table-column prop="query_time" label="耗时(s)" width="80" />
          <el-table-column prop="rows_examined" label="扫描行数" width="90" />
          <el-table-column prop="sql_text" label="SQL" show-overflow-tooltip />
        </el-table>
        <div v-if="slowQueries.length === 0" class="empty-tip">暂无慢查询数据</div>
      </div>

      <!-- 参数配置 -->
      <div class="detail-card glass-card params-card">
        <div class="card-title">实例参数</div>
        <div class="param-list">
          <div class="param-item" v-for="(v, k) in snapshot.params" :key="k">
            <span class="param-key">{{ k }}</span>
            <span class="param-val">{{ v }}</span>
          </div>
        </div>
      </div>

      <!-- 优化建议 -->
      <div class="detail-card glass-card suggestion-card">
        <div class="card-title">智能优化建议</div>
        <ul v-if="suggestions.length" class="suggestion-list">
          <li v-for="(s, i) in suggestions" :key="s.code || i">
            <div class="suggestion-head">
              <span class="severity-tag" :class="s.severity">{{ s.severity }}</span>
              <strong>{{ s.title }}</strong>
            </div>
            <p class="suggestion-advice">{{ s.advice }}</p>
            <p class="suggestion-meta" v-if="s.metric">
              {{ s.metric }} = {{ formatNum(s.value) }}（阈值 {{ s.threshold }}）
            </p>
          </li>
        </ul>
        <div v-else class="empty-tip">当前运行状态良好，暂无优化建议</div>
      </div>

      <!-- 最近告警 -->
      <div class="detail-card glass-card alerts-card">
        <div class="card-title">相关告警</div>
        <div v-for="a in relatedAlerts" :key="a.id" class="alert-row">
          <span class="severity-tag" :class="a.severity">{{ a.severity }}</span>
          <span>{{ a.message }}</span>
          <span class="alert-time">{{ formatTime(a.created_at) }}</span>
        </div>
        <div v-if="relatedAlerts.length === 0" class="empty-tip">暂无相关告警</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 实例详情下钻页 — 按库类型展示指标、结构化建议、趋势与告警
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import * as echarts from 'echarts'
import api from '@/api'
import ThemeToggle from '@/components/ThemeToggle.vue'

interface AdviceItem {
  code: string
  severity: string
  title: string
  metric: string
  value: number
  threshold: number
  advice: string
}

const route = useRoute()
const snapshot = ref<any>(null)
const slowQueries = ref<any[]>([])
const relatedAlerts = ref<any[]>([])
const loading = ref(true)
const loadError = ref('')
const chartRefs: Record<string, HTMLElement> = {}
const charts: Record<string, echarts.ECharts> = {}
let pollTimer: ReturnType<typeof setInterval> | null = null
let chartsLoaded = false

const dbType = computed(() => snapshot.value?.instance?.db_type || snapshot.value?.params?.db_type || '')

const metricCards = computed(() => {
  const type = dbType.value
  if (type === 'redis') {
    return [
      { key: 'qps', label: 'OPS', suffix: '' },
      { key: 'hit_rate', label: '命中率', suffix: '%' },
      { key: 'memory_usage', label: '内存%', suffix: '%' },
      { key: 'connections', label: '客户端', suffix: '' },
    ]
  }
  if (type === 'postgresql') {
    return [
      { key: 'qps', label: 'QPS', suffix: '' },
      { key: 'connections', label: '连接数', suffix: '' },
      { key: 'cache_hit_rate', label: '缓存命中', suffix: '%' },
      { key: 'deadlocks', label: '死锁', suffix: '' },
    ]
  }
  if (type === 'mongodb') {
    return [
      { key: 'qps', label: 'OPS', suffix: '' },
      { key: 'connections', label: '连接数', suffix: '' },
      { key: 'queued_operations', label: '队列', suffix: '' },
      { key: 'page_faults', label: '缺页', suffix: '' },
    ]
  }
  return [
    { key: 'qps', label: 'QPS', suffix: '' },
    { key: 'connections', label: '连接数', suffix: '' },
    { key: 'innodb_buffer_hit_rate', label: 'Buffer 命中', suffix: '%' },
    { key: 'slow_queries', label: '慢查询/s', suffix: '' },
  ]
})

const chartMetrics = computed(() => {
  const type = dbType.value
  if (type === 'redis') {
    return [
      { name: 'qps', label: 'OPS 趋势' },
      { name: 'hit_rate', label: '命中率' },
      { name: 'memory_usage', label: '内存使用率' },
      { name: 'connections', label: '连接数' },
    ]
  }
  if (type === 'postgresql') {
    return [
      { name: 'qps', label: 'QPS 趋势' },
      { name: 'connections', label: '连接数趋势' },
      { name: 'cache_hit_rate', label: '缓存命中率' },
      { name: 'deadlocks', label: '死锁数' },
    ]
  }
  if (type === 'mongodb') {
    return [
      { name: 'qps', label: 'OPS 趋势' },
      { name: 'connections', label: '连接数趋势' },
      { name: 'queued_operations', label: '队列积压' },
      { name: 'page_faults', label: '缺页速率' },
    ]
  }
  return [
    { name: 'qps', label: 'QPS 趋势' },
    { name: 'connections', label: '连接数趋势' },
    { name: 'innodb_buffer_hit_rate', label: 'Buffer 命中率' },
    { name: 'slow_queries', label: '慢查询速率' },
  ]
})

const suggestions = computed<AdviceItem[]>(() => {
  const raw = snapshot.value?.suggestions
  if (!Array.isArray(raw)) return []
  return raw.map((s: any) =>
    typeof s === 'string'
      ? { code: s, severity: 'info', title: s, metric: '', value: 0, threshold: 0, advice: '' }
      : s
  )
})

function setChartRef(name: string, el: HTMLElement | null) {
  if (el) chartRefs[name] = el
}

function formatNum(v: number) {
  if (v === undefined || v === null || Number.isNaN(v)) return '-'
  return Number.isInteger(v) ? String(v) : v.toFixed(2)
}

function formatMetric(key: string, suffix = '') {
  const v = snapshot.value?.metrics?.[key]
  if (v === undefined || v === null) return '-'
  const text = Number.isInteger(v) ? String(v) : Number(v).toFixed(1)
  return suffix ? `${text}${suffix}` : text
}

function formatTime(t: string) {
  return dayjs(t).format('MM-DD HH:mm')
}

async function loadSnapshot() {
  const id = Number(route.params.id)
  try {
    const res = await api.get(`/instances/${id}/snapshot`)
    snapshot.value = res.data.data
    slowQueries.value = res.data.data.slow_queries || []
    loadError.value = ''
  } catch (e: any) {
    loadError.value = e?.response?.data?.detail || '加载实例快照失败'
  } finally {
    loading.value = false
  }
}

async function loadAlerts() {
  const id = Number(route.params.id)
  try {
    const alertRes = await api.get('/alerts', { params: { limit: 50 } })
    relatedAlerts.value = (alertRes.data.data || []).filter(
      (a: any) => a.instance_id === id
    )
  } catch {
    /* axios 已提示 */
  }
}

async function loadCharts() {
  const id = Number(route.params.id)
  for (const metric of chartMetrics.value) {
    try {
      const res = await api.get(`/dashboard/metrics/${id}`, {
        params: { metrics: metric.name, range: '-1h' },
      })
      const series = res.data.data?.[0]
      const el = chartRefs[metric.name]
      if (!series || !el) continue

      let chart = charts[metric.name]
      if (!chart) {
        chart = echarts.init(el, 'dark')
        charts[metric.name] = chart
      }
      chart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 40, right: 10, top: 10, bottom: 25 },
        xAxis: { type: 'time', axisLabel: { color: '#8e9aaf', fontSize: 10 } },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: 'rgba(0,255,255,0.08)' } },
          axisLabel: { color: '#8e9aaf', fontSize: 10 },
        },
        series: [{
          type: 'line',
          smooth: true,
          symbol: 'none',
          areaStyle: { color: 'rgba(0,212,255,0.15)' },
          lineStyle: { color: '#00d4ff' },
          data: (series.points || []).map((p: any) => [p.timestamp, p.value]),
        }],
      })
    } catch {
      /* ignore single metric */
    }
  }
  chartsLoaded = true
}

onMounted(async () => {
  await loadSnapshot()
  await loadAlerts()
  // 等待 DOM 挂载图表容器
  setTimeout(() => loadCharts(), 50)
  pollTimer = setInterval(async () => {
    await loadSnapshot()
    await loadAlerts()
  }, 15000)
})

watch(chartMetrics, () => {
  if (chartsLoaded) {
    Object.values(charts).forEach((c) => c.dispose())
    Object.keys(charts).forEach((k) => delete charts[k])
    setTimeout(() => loadCharts(), 50)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  Object.values(charts).forEach((c) => c.dispose())
})
</script>

<style scoped lang="scss">
.detail-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  h2 { font-size: 20px; color: var(--accent-cyan); }
}

.db-type-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--btn-bg-hover);
  color: var(--accent-cyan);
  text-transform: uppercase;
}

.state-tip {
  text-align: center;
  padding: 48px;
  color: var(--text-secondary);
  &.error { color: var(--accent-red); }
}

.metric-cards {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  text-align: center;
  padding: 16px;

  .metric-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
  .metric-value { font-size: 24px; font-weight: 700; color: var(--accent-cyan); }
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.detail-card { min-height: 200px; }
.slow-query-card, .suggestion-card, .params-card, .alerts-card { grid-column: span 1; }

.mini-chart { height: 160px; }

.param-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.param-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--btn-bg-hover);
  border-radius: 6px;
  font-size: 13px;

  .param-key { color: var(--text-secondary); }
  .param-val { color: var(--accent-cyan); font-weight: 500; }
}

.suggestion-list {
  list-style: none;
  padding: 0;
  margin: 0;

  li {
    padding: 10px 12px;
    margin-bottom: 8px;
    border-left: 3px solid var(--accent-cyan);
    background: var(--btn-bg-hover);
    border-radius: 0 6px 6px 0;
  }
}

.suggestion-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  strong { font-size: 13px; color: var(--text-primary, #e8eef7); }
}

.suggestion-advice {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.suggestion-meta {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.8;
}

.alert-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  color: var(--text-secondary);

  .alert-time { margin-left: auto; font-size: 11px; }
}

.severity-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: lowercase;
  &.critical { background: rgba(255,71,87,0.2); color: var(--accent-red); }
  &.warning { background: rgba(255,159,67,0.2); color: var(--accent-orange); }
  &.info { background: rgba(0,212,255,0.2); color: var(--accent-cyan); }
}

.empty-tip {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
  font-size: 13px;
}

@media (max-width: 900px) {
  .metric-cards { grid-template-columns: repeat(2, 1fr); }
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
