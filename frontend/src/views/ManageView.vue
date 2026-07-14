<template>
  <div class="manage-page">
    <header class="manage-header">
      <div class="header-actions">
        <el-button @click="$router.push('/')" icon="ArrowLeft">返回大屏</el-button>
        <ThemeToggle />
      </div>
      <h2>系统管理</h2>
      <div class="system-status" v-if="sysStatus">
        采集成功率 {{ sysStatus.recent_success_rate }}% · 监控 {{ sysStatus.monitored_instances }} 个实例
      </div>
    </header>

    <el-tabs v-model="activeTab" class="manage-tabs">
      <!-- 数据库实例 -->
      <el-tab-pane label="数据库实例" name="instances">
        <div class="tab-toolbar">
          <el-button type="primary" @click="showInstanceDialog()">添加实例</el-button>
          <el-button @click="loadInstances">刷新</el-button>
        </div>
        <el-table :data="instances" style="width: 100%">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="db_type" label="类型" width="100" />
          <el-table-column label="地址" width="220">
            <template #default="{ row }">{{ row.host }}:{{ row.port }}</template>
          </el-table-column>
          <el-table-column label="分组" width="100">
            <template #default="{ row }">{{ groupName(row.group_id) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <span class="status-dot" :class="row.status"></span> {{ row.status }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260">
            <template #default="{ row }">
              <el-button size="small" @click="testConn(row)">测试</el-button>
              <el-button size="small" @click="$router.push(`/instance/${row.id}`)">详情</el-button>
              <el-button size="small" @click="showInstanceDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteInstance(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 分组管理 -->
      <el-tab-pane label="分组管理" name="groups">
        <div class="tab-toolbar">
          <el-button type="primary" @click="showGroupDialog()">添加分组</el-button>
        </div>
        <el-table :data="groups" style="width: 100%">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="group_type" label="类型" width="120" />
          <el-table-column prop="description" label="描述" />
        </el-table>
      </el-tab-pane>

      <!-- 告警规则 -->
      <el-tab-pane label="告警规则" name="rules">
        <div class="tab-toolbar">
          <el-button type="primary" @click="showRuleDialog()">添加规则</el-button>
        </div>
        <el-table :data="rules" style="width: 100%">
          <el-table-column prop="name" label="规则名称" />
          <el-table-column prop="metric_name" label="指标" width="120" />
          <el-table-column label="条件" width="140">
            <template #default="{ row }">{{ row.operator }} {{ row.threshold }}</template>
          </el-table-column>
          <el-table-column prop="severity" label="级别" width="80" />
          <el-table-column prop="duration_seconds" label="持续(s)" width="80" />
          <el-table-column label="内置" width="60">
            <template #default="{ row }">{{ row.is_builtin ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.is_enabled" @change="toggleRule(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button v-if="!row.is_builtin" size="small" @click="showRuleDialog(row)">编辑</el-button>
              <el-button v-if="!row.is_builtin" size="small" type="danger" @click="deleteRule(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 通知渠道 -->
      <el-tab-pane label="通知渠道" name="channels">
        <div class="tab-toolbar">
          <el-button type="primary" @click="showChannelDialog()">添加渠道</el-button>
        </div>
        <el-table :data="channels" style="width: 100%">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="channel_type" label="类型" width="100" />
          <el-table-column prop="webhook_url" label="Webhook" show-overflow-tooltip />
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.is_enabled" @change="toggleChannel(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="deleteChannel(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 采集日志 -->
      <el-tab-pane label="采集日志" name="logs">
        <div class="tab-toolbar">
          <el-button @click="loadCollectionLogs">刷新</el-button>
        </div>
        <el-table :data="collectionLogs" style="width: 100%" max-height="500">
          <el-table-column prop="timestamp" label="时间" width="180" />
          <el-table-column prop="instance_name" label="实例" width="150" />
          <el-table-column label="结果" width="80">
            <template #default="{ row }">
              <el-tag :type="row.success ? 'success' : 'danger'" size="small">
                {{ row.success ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="attempt" label="重试" width="60" />
          <el-table-column prop="error" label="错误信息" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>

      <!-- 数据导出 -->
      <el-tab-pane label="数据导出" name="export">
        <div class="export-form glass-card">
          <h3>导出监控数据</h3>
          <el-form label-width="100px" style="max-width: 500px">
            <el-form-item label="实例">
              <el-select v-model="exportForm.instance_id" placeholder="全部实例" clearable style="width: 100%">
                <el-option v-for="i in instances" :key="i.id" :value="i.id" :label="i.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="指标">
              <el-select v-model="exportForm.metrics" multiple style="width: 100%">
                <el-option value="qps" label="QPS" />
                <el-option value="connections" label="连接数" />
                <el-option value="cpu_usage" label="CPU" />
                <el-option value="slow_queries" label="慢查询" />
              </el-select>
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="exportForm.timeRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="格式">
              <el-radio-group v-model="exportForm.format">
                <el-radio value="csv">CSV</el-radio>
                <el-radio value="json">JSON</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="exportData">导出数据</el-button>
              <el-button @click="exportPDF">导出 PDF 报告</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 实例对话框 -->
    <el-dialog v-model="instanceDialogVisible" :title="editingInstance ? '编辑实例' : '添加实例'" width="520px">
      <el-form ref="formRef" :model="instanceForm" :rules="formRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="instanceForm.name" />
        </el-form-item>
        <el-form-item label="类型" prop="db_type">
          <el-select v-model="instanceForm.db_type" style="width: 100%">
            <el-option value="mysql" label="MySQL" />
            <el-option value="postgresql" label="PostgreSQL" />
            <el-option value="redis" label="Redis" />
            <el-option value="mongodb" label="MongoDB" />
          </el-select>
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="instanceForm.group_id" clearable placeholder="无分组" style="width: 100%">
            <el-option v-for="g in groups" :key="g.id" :value="g.id" :label="g.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机" prop="host">
          <el-input v-model="instanceForm.host" placeholder="Docker 填 host.docker.internal" />
          <div class="host-hint">Docker 环境请填 <code>host.docker.internal</code></div>
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="instanceForm.port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户名"><el-input v-model="instanceForm.username" /></el-form-item>
        <el-form-item label="密码">
          <el-input v-model="instanceForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="数据库"><el-input v-model="instanceForm.database_name" /></el-form-item>
        <el-form-item label="最大连接" prop="max_connections">
          <el-input-number v-model="instanceForm.max_connections" :min="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="instanceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveInstance">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分组对话框 -->
    <el-dialog v-model="groupDialogVisible" title="添加分组" width="400px">
      <el-form :model="groupForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="groupForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="groupForm.group_type" style="width: 100%">
            <el-option value="environment" label="环境" />
            <el-option value="business" label="业务线" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="groupForm.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGroup">保存</el-button>
      </template>
    </el-dialog>

    <!-- 告警规则对话框 -->
    <el-dialog v-model="ruleDialogVisible" :title="editingRule ? '编辑规则' : '添加规则'" width="500px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="名称"><el-input v-model="ruleForm.name" /></el-form-item>
        <el-form-item label="指标">
          <el-select v-model="ruleForm.metric_name" style="width: 100%">
            <el-option value="cpu_usage" label="CPU 使用率" />
            <el-option value="connections" label="连接数" />
            <el-option value="connection_ratio" label="连接数比率" />
            <el-option value="slow_queries" label="慢查询数" />
            <el-option value="replication_lag" label="主从延迟" />
            <el-option value="qps" label="QPS" />
          </el-select>
        </el-form-item>
        <el-form-item label="运算符">
          <el-select v-model="ruleForm.operator" style="width: 120px">
            <el-option value=">" label=">" />
            <el-option value="<" label="<" />
            <el-option value=">=" label=">=" />
            <el-option value="<=" label="<=" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值"><el-input-number v-model="ruleForm.threshold" /></el-form-item>
        <el-form-item label="持续(秒)"><el-input-number v-model="ruleForm.duration_seconds" :min="0" /></el-form-item>
        <el-form-item label="级别">
          <el-select v-model="ruleForm.severity" style="width: 120px">
            <el-option value="info" label="提示" />
            <el-option value="warning" label="警告" />
            <el-option value="critical" label="紧急" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>

    <!-- 通知渠道对话框 -->
    <el-dialog v-model="channelDialogVisible" title="添加通知渠道" width="500px">
      <el-form :model="channelForm" label-width="100px">
        <el-form-item label="名称"><el-input v-model="channelForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="channelForm.channel_type" style="width: 100%">
            <el-option value="wechat" label="企业微信" />
            <el-option value="dingtalk" label="钉钉" />
            <el-option value="feishu" label="飞书" />
            <el-option value="email" label="邮件" />
          </el-select>
        </el-form-item>
        <el-form-item label="Webhook">
          <el-input v-model="channelForm.webhook_url" placeholder="机器人 Webhook 地址" />
        </el-form-item>
        <el-form-item v-if="channelForm.channel_type === 'email'" label="收件人">
          <el-input v-model="channelForm.email_recipients" placeholder="多个邮箱用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="channelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveChannel">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { downloadWithAuth, postDownloadWithAuth } from '@/utils/download'

const formRef = ref<FormInstance>()
const activeTab = ref('instances')
const instances = ref<any[]>([])
const groups = ref<any[]>([])
const rules = ref<any[]>([])
const channels = ref<any[]>([])
const collectionLogs = ref<any[]>([])
const sysStatus = ref<any>(null)

const instanceDialogVisible = ref(false)
const groupDialogVisible = ref(false)
const ruleDialogVisible = ref(false)
const channelDialogVisible = ref(false)
const editingInstance = ref<any>(null)
const editingRule = ref<any>(null)

const instanceForm = reactive({
  name: '', db_type: 'mysql', host: '', port: 3306,
  username: '', password: '', database_name: '', max_connections: 100, group_id: null as number | null,
})
const groupForm = reactive({ name: '', group_type: 'environment', description: '' })
const ruleForm = reactive({
  name: '', metric_name: 'cpu_usage', operator: '>', threshold: 80,
  duration_seconds: 300, severity: 'warning', is_enabled: true,
})
const channelForm = reactive({
  name: '', channel_type: 'wechat', webhook_url: '', email_recipients: '', is_enabled: true,
})
const exportForm = reactive({
  instance_id: null as number | null,
  metrics: ['qps', 'connections'],
  timeRange: null as [Date, Date] | null,
  format: 'csv',
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入主机', trigger: 'blur' }],
  port: [{ required: true, type: 'number', message: '请输入端口', trigger: 'blur' }],
}

function groupName(id: number | null) {
  if (!id) return '-'
  return groups.value.find(g => g.id === id)?.name || '-'
}

onMounted(() => {
  loadAll()
})

async function loadAll() {
  await Promise.all([
    loadInstances(), loadGroups(), loadRules(), loadChannels(), loadSysStatus(),
  ])
}

async function loadInstances() {
  const res = await api.get('/instances')
  instances.value = res.data.data
}
async function loadGroups() {
  const res = await api.get('/instances/groups')
  groups.value = res.data.data
}
async function loadRules() {
  const res = await api.get('/alerts/rules')
  rules.value = res.data.data
}
async function loadChannels() {
  const res = await api.get('/alerts/channels')
  channels.value = res.data.data
}
async function loadCollectionLogs() {
  const res = await api.get('/system/collection-logs', { params: { limit: 100 } })
  collectionLogs.value = res.data.data
}
async function loadSysStatus() {
  const res = await api.get('/system/status')
  sysStatus.value = res.data.data
}

function buildPayload() {
  return {
    name: instanceForm.name.trim(),
    db_type: instanceForm.db_type,
    host: instanceForm.host.trim(),
    port: instanceForm.port ?? 3306,
    username: instanceForm.username?.trim() || '',
    password: instanceForm.password || '',
    database_name: instanceForm.database_name?.trim() || '',
    max_connections: instanceForm.max_connections ?? 100,
    group_id: instanceForm.group_id,
  }
}

function showInstanceDialog(row?: any) {
  editingInstance.value = row || null
  if (row) {
    Object.assign(instanceForm, {
      name: row.name, db_type: row.db_type, host: row.host, port: row.port,
      username: row.username || '', password: '', database_name: row.database_name || '',
      max_connections: row.max_connections || 100, group_id: row.group_id,
    })
  } else {
    Object.assign(instanceForm, {
      name: '', db_type: 'mysql', host: '', port: 3306,
      username: '', password: '', database_name: '', max_connections: 100, group_id: null,
    })
  }
  instanceDialogVisible.value = true
}

async function saveInstance() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload = buildPayload()
  try {
    if (editingInstance.value) {
      const d = { ...payload }
      if (!d.password) delete (d as any).password
      await api.put(`/instances/${editingInstance.value.id}`, d)
    } else {
      await api.post('/instances', payload)
    }
    ElMessage.success('保存成功')
    instanceDialogVisible.value = false
    loadInstances()
  } catch (e) { /* */ }
}

async function deleteInstance(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该实例？相关告警记录将一并清除。', '确认')
    await api.delete(`/instances/${id}`)
    ElMessage.success('已删除')
    loadInstances()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      /* 错误由 axios 拦截器提示 */
    }
  }
}

async function testConn(row: any) {
  if (!instanceForm.password && editingInstance.value?.id !== row.id) {
    showInstanceDialog(row)
    ElMessage.warning('请在编辑弹窗中填入密码后测试')
    return
  }
  const res = await api.post('/instances/test-connection', {
    db_type: row.db_type, host: row.host, port: row.port,
    username: row.username, password: instanceForm.password,
    database_name: row.database_name,
  })
  const d = res.data.data
  ElMessage[d.success ? 'success' : 'error'](d.success ? `连接成功 ${d.latency_ms?.toFixed(1)}ms` : d.message)
}

function showGroupDialog() { groupDialogVisible.value = true }
async function saveGroup() {
  await api.post('/instances/groups', groupForm)
  ElMessage.success('分组已创建')
  groupDialogVisible.value = false
  loadGroups()
}

function showRuleDialog(row?: any) {
  editingRule.value = row || null
  if (row) Object.assign(ruleForm, row)
  else Object.assign(ruleForm, {
    name: '', metric_name: 'cpu_usage', operator: '>', threshold: 80,
    duration_seconds: 300, severity: 'warning',
  })
  ruleDialogVisible.value = true
}

async function saveRule() {
  if (editingRule.value) {
    await api.put(`/alerts/rules/${editingRule.value.id}`, ruleForm)
  } else {
    await api.post('/alerts/rules', ruleForm)
  }
  ElMessage.success('规则已保存')
  ruleDialogVisible.value = false
  loadRules()
}

async function deleteRule(id: number) {
  await ElMessageBox.confirm('确定删除该规则？', '确认')
  await api.delete(`/alerts/rules/${id}`)
  ElMessage.success('已删除')
  loadRules()
}

async function toggleRule(row: any) {
  await api.patch(`/alerts/rules/${row.id}/toggle`)
  loadRules()
}

function showChannelDialog() { channelDialogVisible.value = true }
async function saveChannel() {
  await api.post('/alerts/channels', channelForm)
  ElMessage.success('渠道已添加')
  channelDialogVisible.value = false
  loadChannels()
}

async function deleteChannel(id: number) {
  await ElMessageBox.confirm('确定删除？', '确认')
  await api.delete(`/alerts/channels/${id}`)
  loadChannels()
}

async function toggleChannel(row: any) {
  await api.patch(`/alerts/channels/${row.id}/toggle`)
  loadChannels()
}

async function exportData() {
  if (!exportForm.timeRange) {
    ElMessage.warning('请选择时间范围')
    return
  }
  const ext = exportForm.format
  await postDownloadWithAuth('/export/data', {
    instance_id: exportForm.instance_id,
    metric_names: exportForm.metrics,
    start_time: exportForm.timeRange[0].toISOString(),
    end_time: exportForm.timeRange[1].toISOString(),
    format: exportForm.format,
  }, `metrics.${ext}`)
}

async function exportPDF() {
  await downloadWithAuth('/export/report/pdf', 'monitor_report.pdf')
}
</script>

<style scoped lang="scss">
.manage-page {
  height: 100%;
  padding: 16px 24px;
  overflow-y: auto;
}

.manage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  h2 { color: var(--accent-cyan); }
}

.header-actions { display: flex; align-items: center; gap: 10px; }

.system-status {
  font-size: 12px;
  color: var(--text-secondary);
}

.tab-toolbar { margin-bottom: 16px; display: flex; gap: 8px; }

.export-form {
  max-width: 600px;
  padding: 24px;
  h3 { color: var(--accent-cyan); margin-bottom: 16px; }
}

.host-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  code { color: var(--accent-cyan); background: var(--btn-bg-hover); padding: 1px 6px; border-radius: 4px; }
}
</style>
