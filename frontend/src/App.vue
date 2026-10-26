<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const API = '/api'
const active = ref('overview')
const loading = ref(true)
const live = ref(false)
const encoding = ref(false)
const encodedCount = ref(0)
const selectedCell = ref(null)
const privacyStep = ref(0)
const overview = ref({ metrics: {}, regions: [], devices: [], updated_at: '--' })
const trend = ref([])
const chartEl = ref(null)
const computeChartEl = ref(null)
const uploadChartEl = ref(null)
const aggregateChartEl = ref(null)
const perfScenario = ref('length')
const anomalyRatio = ref(0.25)
const simulating = ref(false)
const privacyData = ref(null)
let chart
let perfCharts = []
let liveTimer
let encodingTimer

const nav = [
  ['overview', '系统总览', 'Overview'],
  ['devices', '设备监测', 'IoT Monitoring'],
  ['encoding', '空间编码', 'Hilbert Encoding'],
  ['privacy', '隐私计算', 'DPF Privacy'],
  ['results', '分析结果', 'Analytics'],
  ['security', '安全模型', 'Security Model'],
  ['performance', '性能评估', 'Evaluation'],
]

const performanceData = {
  length: {
    x: ['4', '8', '16', '24', '32'], xName: '编码长度',
    compute: { PSDA: [3.2, 5.1, 8.8, 12.7, 16.4], EPSG: [8.5, 15.2, 29.8, 44.5, 58.7], FEISG: [6.8, 12.4, 23.1, 34.2, 45.6], Panther: [11.2, 20.5, 39.4, 58.8, 77.1] },
    upload: { PSDA: [12, 20, 36, 52, 68], EPSG: [29, 53, 101, 149, 197], FEISG: [23, 41, 77, 113, 149], Panther: [36, 68, 132, 196, 260] },
    aggregate: { PSDA: [1.8, 2.7, 4.3, 5.9, 7.4], EPSG: [4.6, 8.1, 15.3, 22.4, 29.5], FEISG: [3.9, 6.8, 12.7, 18.6, 24.4], Panther: [7.1, 13.2, 25.1, 37.4, 49.6] },
  },
  devices: {
    x: ['100', '200', '300', '400', '500'], xName: 'IoT设备数量',
    compute: { PSDA: [4.1, 7.5, 10.8, 14.3, 17.7], EPSG: [12.5, 23.8, 35.2, 46.4, 58.1], FEISG: [9.8, 18.6, 27.5, 36.4, 45.2], Panther: [15.9, 31.2, 46.5, 61.7, 77.4] },
    upload: { PSDA: [15, 28, 41, 54, 67], EPSG: [40, 79, 118, 157, 196], FEISG: [30, 60, 89, 119, 148], Panther: [52, 104, 156, 208, 260] },
    aggregate: { PSDA: [2.1, 3.5, 4.9, 6.2, 7.6], EPSG: [6.1, 11.9, 17.8, 23.6, 29.4], FEISG: [5.0, 9.8, 14.7, 19.5, 24.3], Panther: [10.2, 20.1, 30.0, 39.8, 49.7] },
  },
}

const processSteps = [
  { page: 'devices', short: '采集', title: 'IoT 数据采集' },
  { page: 'encoding', short: '编码', title: 'Hilbert 空间编码' },
  { page: 'privacy', short: '拆分', title: 'DPF 密钥生成' },
  { page: 'privacy', short: '计算', title: '双服务器协同计算' },
  { page: 'results', short: '聚合', title: '区域结果聚合' },
  { page: 'results', short: '分析', title: '管理部门分析' },
]

const statusText = { normal: '运行平稳', warning: '负荷偏高', critical: '潜在异常', offline: '设备离线' }
const statusClass = (status) => `state-${status}`
const currentRegion = computed(() => selectedCell.value || overview.value.regions[0] || {})
const criticalRegions = computed(() => overview.value.regions.filter(r => r.status !== 'normal'))
const regionIndex = (region) => parseInt(region.code || '0', 2)
const spatialRegions = computed(() => [...overview.value.regions].sort((a, b) => a.y - b.y || a.x - b.x))
const curvePath = (list) => list.map(r => `${50 + r.x * 100},${50 + r.y * 100}`).join(' ')
const hilbertPath = computed(() => curvePath(overview.value.regions))
const rowScanPath = computed(() => curvePath(spatialRegions.value))
const currentStep = computed(() => {
  if (active.value === 'devices') return 0
  if (active.value === 'encoding') return 1
  if (active.value === 'privacy') return privacyStep.value >= 2 ? 3 : 2
  if (active.value === 'results') return 5
  return -1
})

async function fetchData() {
  try {
    const [a, b] = await Promise.all([
      fetch(`${API}/overview`).then(r => r.json()),
      fetch(`${API}/trend`).then(r => r.json()),
    ])
    overview.value = a
    trend.value = b.points
    loading.value = false
    await nextTick()
    renderChart()
  } catch (e) {
    loading.value = false
  }
}

function renderChart() {
  if (!chartEl.value || !chartEl.value.clientWidth) return
  chart ||= echarts.init(chartEl.value)
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 38, right: 18, top: 28, bottom: 30 },
    tooltip: { trigger: 'axis', backgroundColor: '#101d2e', borderColor: '#2d4967', textStyle: { color: '#fff' } },
    xAxis: { type: 'category', data: trend.value.map(x => x.time), axisLine: { lineStyle: { color: '#37516c' } }, axisLabel: { color: '#7890a8' } },
    yAxis: { type: 'value', min: 40, axisLine: { show: false }, splitLine: { lineStyle: { color: '#182b40' } }, axisLabel: { color: '#7890a8' } },
    series: [{
      data: trend.value.map(x => x.load), type: 'line', smooth: true, symbol: 'circle', symbolSize: 7,
      lineStyle: { color: '#32d8d0', width: 3 }, itemStyle: { color: '#9ef6ed' },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(50,216,208,.28)' }, { offset: 1, color: 'rgba(50,216,208,0)' }]) }
    }]
  })
}

function performanceOption(metric, unit) {
  const data = performanceData[perfScenario.value]
  const colors = { PSDA: '#32d8d0', EPSG: '#ffb74a', FEISG: '#56a4ff', Panther: '#ff636e' }
  return {
    animationDuration: 700,
    color: Object.values(colors),
    tooltip: { trigger: 'axis', backgroundColor: '#101d2e', borderColor: '#2d4967', textStyle: { color: '#fff' } },
    legend: { top: 0, right: 0, itemWidth: 12, itemHeight: 3, textStyle: { color: '#718aa0', fontSize: 9 } },
    grid: { left: 42, right: 16, top: 42, bottom: 34 },
    xAxis: { type: 'category', name: data.xName, nameTextStyle: { color: '#58738a', fontSize: 9 }, data: data.x, axisLine: { lineStyle: { color: '#29445a' } }, axisLabel: { color: '#70889c', fontSize: 9 } },
    yAxis: { type: 'value', name: unit, nameTextStyle: { color: '#58738a', fontSize: 9 }, splitLine: { lineStyle: { color: '#172b3e' } }, axisLabel: { color: '#70889c', fontSize: 9 } },
    series: Object.entries(data[metric]).map(([name, values]) => ({ name, data: values, type: 'line', smooth: true, symbolSize: name === 'PSDA' ? 7 : 5, lineStyle: { width: name === 'PSDA' ? 3 : 1.5, color: colors[name] }, itemStyle: { color: colors[name] } })),
  }
}

function renderPerformanceCharts() {
  if (!computeChartEl.value) return
  if (!perfCharts.length) perfCharts = [echarts.init(computeChartEl.value), echarts.init(uploadChartEl.value), echarts.init(aggregateChartEl.value)]
  perfCharts[0].setOption(performanceOption('compute', 'ms'), true)
  perfCharts[1].setOption(performanceOption('upload', 'KB'), true)
  perfCharts[2].setOption(performanceOption('aggregate', 'ms'), true)
}

async function setPerfScenario(value) {
  perfScenario.value = value
  await nextTick()
  renderPerformanceCharts()
}

function toggleLive() {
  live.value = !live.value
  if (live.value) liveTimer = setInterval(fetchData, 3500)
  else clearInterval(liveTimer)
}

function startEncoding() {
  clearInterval(encodingTimer)
  encoding.value = true
  encodedCount.value = 0
  encodingTimer = setInterval(() => {
    encodedCount.value += 1
    if (encodedCount.value >= overview.value.regions.length) {
      clearInterval(encodingTimer)
      encoding.value = false
    }
  }, 160)
}

async function fetchPrivacy() {
  const code = currentRegion.value.code
  const res = await fetch(`${API}/privacy-demo${code ? `?region=${code}` : ''}`)
  privacyData.value = await res.json()
}

async function runPrivacy() {
  await fetchPrivacy()
  privacyStep.value = 0
  const timer = setInterval(() => {
    privacyStep.value += 1
    if (privacyStep.value >= 3) clearInterval(timer)
  }, 850)
}

async function simulateLoads() {
  simulating.value = true
  try {
    const res = await fetch(`${API}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anomaly_ratio: anomalyRatio.value }),
    })
    overview.value = await res.json()
    selectedCell.value = null
    await fetchPrivacy()
  } finally {
    simulating.value = false
  }
}

function chooseRegion(region) { selectedCell.value = region }
function go(page) { active.value = page }
function goStep(index) {
  active.value = processSteps[index].page
  if (processSteps[index].page === 'privacy') privacyStep.value = index === 3 ? 2 : 0
}

watch(active, async (page) => {
  if (page === 'results') { await nextTick(); renderChart(); chart?.resize() }
  if (page === 'performance') { await nextTick(); renderPerformanceCharts(); perfCharts.forEach(c => c.resize()) }
  if (page === 'privacy') { await fetchPrivacy() }
})

onMounted(() => {
  fetchData().then(fetchPrivacy)
  window.addEventListener('resize', () => { chart?.resize(); perfCharts.forEach(c => c.resize()) })
})
onBeforeUnmount(() => { clearInterval(liveTimer); clearInterval(encodingTimer); chart?.dispose(); perfCharts.forEach(c => c.dispose()) })
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><span></span><span></span><span></span></div>
        <div><strong>PSDA</strong><small>POWER ANALYTICS</small></div>
      </div>
      <nav>
        <button v-for="item in nav" :key="item[0]" :class="{ active: active === item[0] }" :aria-label="item[1]" :title="item[1]" @click="go(item[0])">
          <span class="nav-dot"></span><span><b>{{ item[1] }}</b><small>{{ item[2] }}</small></span>
        </button>
      </nav>
      <div class="system-state"><i></i><div><b>系统运行正常</b><small>双服务器安全连接</small></div></div>
    </aside>

    <main>
      <header>
        <div><p>SMART GRID · PRIVACY PRESERVING</p><h1>隐私保护型电力分布分析平台</h1></div>
        <div class="header-actions"><span class="last-update">数据更新 {{ overview.updated_at }}</span><button class="outline" @click="toggleLive">{{ live ? '暂停实时刷新' : '启动实时监测' }}</button></div>
      </header>

      <div class="process-bar">
        <div class="process-caption"><span>PSDA PROCESS</span><b>{{ currentStep < 0 ? '系统待命' : processSteps[currentStep].title }}</b></div>
        <div class="process-line">
          <div class="process-fill" :style="{ width: currentStep < 0 ? '0%' : `${currentStep / (processSteps.length - 1) * 100}%` }"></div>
          <button v-for="(step, index) in processSteps" :key="step.title" :class="{ passed: currentStep >= index, current: currentStep === index }" @click="goStep(index)" :title="step.title">
            <i>{{ index + 1 }}</i><span>{{ step.short }}</span>
          </button>
        </div>
        <span class="process-value">{{ currentStep < 0 ? 0 : Math.round((currentStep + 1) / processSteps.length * 100) }}%</span>
      </div>

      <section v-if="loading" class="loading"><div></div><p>正在连接电力感知网络…</p></section>

      <template v-else>
        <section v-show="active === 'overview'" class="page">
          <div class="section-title"><div><span>01 / OVERVIEW</span><h2>系统总览</h2></div><p>从分布式物联网节点感知区域用电状态，以隐私保护方式完成汇聚分析。</p></div>
          <div class="metrics">
            <article><span>接入 IoT 设备</span><strong>{{ overview.metrics.devices }}</strong><small>DEVICES ONLINE</small></article>
            <article><span>监测区域</span><strong>{{ overview.metrics.regions }}</strong><small>HILBERT CELLS</small></article>
            <article><span>潜在异常区域</span><strong class="amber">{{ overview.metrics.alerts }}</strong><small>NEEDS ATTENTION</small></article>
            <article><span>平均分析耗时</span><strong>{{ overview.metrics.latency }}<em>ms</em></strong><small>AGGREGATION TIME</small></article>
          </div>
          <div class="overview-grid">
            <article class="panel map-panel">
              <div class="panel-head"><div><small>REGIONAL POWER GRID</small><h3>区域电力分布</h3></div><div class="grid-actions"><div class="legend"><i class="normal"></i>正常<i class="warning"></i>偏高<i class="critical"></i>异常</div><label class="ratio-picker">关注比例<select v-model.number="anomalyRatio"><option :value="0.1">10%</option><option :value="0.25">25%</option><option :value="0.4">40%</option></select></label><button class="outline compact" :disabled="simulating" @click="simulateLoads">{{ simulating ? '生成中…' : '随机生成负荷' }}</button></div></div>
              <div class="power-grid">
                <button v-for="region in spatialRegions" :key="region.code" :class="[statusClass(region.status), { selected: currentRegion.code === region.code }]" @click="chooseRegion(region)">
                  <small>{{ region.code }}</small><strong>{{ region.load }}%</strong><span>{{ region.name }}</span>
                </button>
                <svg class="hilbert-overlay" viewBox="0 0 400 400" preserveAspectRatio="none"><polyline :points="hilbertPath" /></svg>
              </div>
            </article>
            <article class="panel detail-panel">
              <div class="panel-head"><div><small>REGION DETAIL</small><h3>{{ currentRegion.name }} · {{ currentRegion.code }}</h3></div><span :class="['status-pill', statusClass(currentRegion.status)]">{{ statusText[currentRegion.status] }}</span></div>
              <div class="load-ring" :style="{ '--load': `${currentRegion.load * 3.6}deg` }"><div><strong>{{ currentRegion.load }}</strong><span>% 区域负荷</span></div></div>
              <dl><div><dt>接入设备</dt><dd>{{ currentRegion.devices }} 台</dd></div><div><dt>电压均值</dt><dd>{{ currentRegion.voltage }} V</dd></div><div><dt>聚合指数</dt><dd>{{ currentRegion.aggregate }}</dd></div><div><dt>空间坐标</dt><dd>({{ currentRegion.x }}, {{ currentRegion.y }})</dd></div></dl>
              <p class="metric-note">聚合指数 = 该区域 {{ currentRegion.devices }} 台设备的负荷经 DPF 聚合后的总量，即论文中管理部门对各区域求和得到的结果；接入设备数与电压均值不随模拟刷新变化。</p>
              <button class="primary" @click="go('results')">查看分析结果 <span>→</span></button>
            </article>
          </div>
        </section>

        <section v-show="active === 'encoding'" class="page">
          <div class="section-title"><div><span>03 / HILBERT ENCODING</span><h2>希尔伯特空间编码</h2></div><p>将二维电网区域映射为具有空间局部性的一维序列，降低区域数据处理开销。</p></div>
          <div class="feature-layout">
            <article class="panel encoding-card">
              <div class="panel-head"><div><small>2ND ORDER CURVE · DEMO</small><h3>二维位置到一维编码</h3></div><button class="primary compact" @click="startEncoding">{{ encoding ? '编码中…' : '开始编码' }}</button></div>
              <div class="encode-grid">
                <button v-for="region in spatialRegions" :key="region.code" :class="[{ passed: regionIndex(region) < encodedCount, current: regionIndex(region) === encodedCount - 1 }, statusClass(region.status)]" @click="chooseRegion(region)"><span>{{ regionIndex(region) }}</span><b>{{ region.code }}</b><small>({{ region.x }},{{ region.y }})</small></button>
                <svg viewBox="0 0 400 400" preserveAspectRatio="none"><polyline :points="hilbertPath" /></svg>
              </div>
            </article>
            <article class="panel formula-card">
              <small>ENCODING INSPECTOR</small><h3>编码检查器</h3>
              <div class="mapping"><span>物理位置</span><strong>({{ currentRegion.x }}, {{ currentRegion.y }})</strong><i>↓</i><span>Hilbert 序号</span><strong>{{ parseInt(currentRegion.code || '0', 2) }}</strong><i>↓</i><span>二进制区域编码</span><strong class="cyan">{{ currentRegion.code }}</strong></div>
              <p>相邻区域在编码序列中尽可能保持接近，适合快速聚合大规模电网中的空间数据。</p>
            </article>
          </div>
          <article class="panel encoding-compare">
            <div class="compare-copy"><small>WHY HILBERT CURVE</small><h3>为什么使用空间填充曲线</h3><p>逐行编码在换行位置会让连续编号跨越较大的物理距离；Hilbert曲线通过递归旋转和连接，使序列中相邻编码尽可能对应现实中的相邻区域。</p><div class="locality-metric"><span>空间局部性</span><b>Hilbert 更优</b></div></div>
            <div class="scan-demo"><div class="compare-title"><span>普通逐行扫描</span><b>跨行跳跃</b></div><div class="mini-grid row-scan"><i v-for="region in spatialRegions" :key="region.code">{{ region.y * 4 + region.x }}</i><svg viewBox="0 0 400 400" preserveAspectRatio="none"><polyline :points="rowScanPath" /></svg></div></div>
            <div class="scan-demo"><div class="compare-title"><span>Hilbert曲线扫描</span><b class="good">保持邻近</b></div><div class="mini-grid hilbert-scan"><i v-for="region in spatialRegions" :key="region.code">{{ regionIndex(region) }}</i><svg viewBox="0 0 400 400" preserveAspectRatio="none"><polyline :points="hilbertPath" /></svg></div></div>
          </article>
        </section>

        <section v-show="active === 'devices'" class="page">
          <div class="section-title"><div><span>02 / IOT MONITORING</span><h2>物联网设备监测</h2></div><p>16 个区域感知节点分别汇集辖区内智能电表、充电站和变压器监测器的数据。</p></div>
          <article class="panel table-panel">
            <div class="panel-head"><div><small>LIVE SENSOR NODES</small><h3>分布式感知节点</h3></div><span class="live-badge"><i></i>LIVE</span></div>
            <div class="device-table">
              <div class="tr th"><span>感知节点</span><span>区域编码</span><span>下辖设备</span><span>电压均值</span><span>区域负荷</span><span>状态</span></div>
              <div class="tr" v-for="device in overview.devices" :key="device.id"><span><b>{{ device.name }}</b><small>{{ device.id }}</small></span><span class="mono">{{ device.region }}</span><span>{{ device.managed_devices }} 台</span><span>{{ device.voltage }} V</span><span><i class="bar"><i :style="{ width: device.load + '%' }"></i></i>{{ device.load }}%</span><span :class="['device-state', statusClass(device.status)]">{{ statusText[device.status] }}</span></div>
            </div>
          </article>
        </section>

        <section v-show="active === 'privacy'" class="page">
          <div class="section-title"><div><span>04 / DPF PRIVACY</span><h2>双服务器隐私计算</h2></div><p>DPF 将区域编码和测量值拆分为两个密钥份额，单台服务器无法推断原始信息。</p></div>
          <article class="panel privacy-panel">
            <div class="privacy-flow">
              <div :class="['flow-node device-node', { active: privacyStep >= 0 }]"><span>IoT</span><b>感知节点</b><small v-if="privacyData">区域 {{ privacyData.target.code }} · 负荷 {{ privacyData.target.load }}</small><small v-else>•••</small></div>
              <div class="split-lines"><i></i><i></i></div>
              <div class="server-stack">
                <div :class="['flow-node server-node', { active: privacyStep >= 1 }]"><span>S₀</span><b>协作服务器 A</b><small>{{ privacyStep >= 1 && privacyData ? '持有 k₀ · ' + privacyData.keys.server_a.replace('k0: ', '') : '•••' }}</small></div>
                <div :class="['flow-node server-node', { active: privacyStep >= 1 }]"><span>S₁</span><b>协作服务器 B</b><small>{{ privacyStep >= 1 && privacyData ? '持有 k₁ · ' + privacyData.keys.server_b.replace('k1: ', '') : '•••' }}</small></div>
              </div>
              <div class="merge-lines"><i></i><i></i></div>
              <div :class="['flow-node result-node', { active: privacyStep >= 2 }]"><span>Σ</span><b>安全聚合结果</b><small>{{ privacyStep >= 2 && privacyData ? `仅 ${privacyData.target.code} 处恢复为 ${privacyData.target.load}` : '只恢复区域统计值' }}</small></div>
            </div>
            <div class="privacy-copy"><small>NON-COLLUDING ARCHITECTURE</small><h3>单点不可见，联合可计算</h3><p>两个服务器遵循协议但可能尝试推断额外信息，因此系统假设二者不合谋。任一服务器单独持有的份额都不会暴露目标区域和原始负荷。</p><button class="primary" @click="runPrivacy">运行一次隐私计算 <span>→</span></button><div class="share-equation" v-if="privacyData"><div><span>服务器A 在 α 处</span><b>{{ privacyStep >= 1 ? privacyData.evaluation.server_a[regionIndex(privacyData.target)] : '?' }}</b></div><i>+</i><div><span>服务器B 在 α 处</span><b>{{ privacyStep >= 1 ? privacyData.evaluation.server_b[regionIndex(privacyData.target)] : '?' }}</b></div><i>=</i><div class="sum"><span>聚合负荷 β</span><b>{{ privacyStep >= 2 ? privacyData.target.load : '?' }}</b></div></div><div class="step-status"><i :class="{ done: privacyStep >= 1 }"></i>① 按 Hilbert 编码 α 生成密钥份额 k₀ / k₁<i :class="{ done: privacyStep >= 2 }"></i>② 两台服务器分别求值 Eval(i, kᵢ, x)<i :class="{ done: privacyStep >= 3 }"></i>③ 部门求和，仅在 α 处得到 β</div></div>
          </article>
          <article class="panel dpf-detail" v-if="privacyData">
            <div class="panel-head"><div><small>DPF EVALUATION · ALL {{ privacyData.evaluation.codes.length }} CODES</small><h3>两个密钥在全部区域编码上的求值</h3></div><span class="status-pill state-normal">α = {{ privacyData.target.code }} · β = {{ privacyData.target.load }}</span></div>
            <div class="dpf-table">
              <div class="dpf-row dpf-head"><span class="dpf-label">区域编码 x</span><b v-for="c in privacyData.evaluation.codes" :key="c" :class="{ target: c === privacyData.target.code }">{{ c }}</b></div>
              <div class="dpf-row"><span class="dpf-label">Eval(0, k₀, x)</span><b v-for="(v, i) in privacyData.evaluation.server_a" :key="i" :class="{ target: privacyData.evaluation.codes[i] === privacyData.target.code }">{{ v }}</b></div>
              <div class="dpf-row"><span class="dpf-label">Eval(1, k₁, x)</span><b v-for="(v, i) in privacyData.evaluation.server_b" :key="i" :class="{ target: privacyData.evaluation.codes[i] === privacyData.target.code }">{{ v }}</b></div>
              <div class="dpf-row dpf-sum"><span class="dpf-label">相加 mod {{ privacyData.field }}</span><b v-for="(v, i) in privacyData.evaluation.sum" :key="i" :class="{ target: privacyData.evaluation.codes[i] === privacyData.target.code }">{{ v }}</b></div>
            </div>
            <div class="dpf-notes">
              <p><b>① 密钥生成 Gen(λ, α, β) → (k₀, k₁)：</b>IoT 设备把区域位置编码为 α = {{ privacyData.target.code }}、负荷记为 β = {{ privacyData.target.load }}，生成一对密钥：{{ privacyData.keys.server_a }} 交给服务器 A，{{ privacyData.keys.server_b }} 交给服务器 B；任一密钥单独看都不包含 α 与 β 的信息。</p>
              <p><b>② 双服务器求值 Eval(i, kᵢ, x)：</b>两台服务器各自在全部 16 个区域编码上求值，得到两组份额，单组份额与随机数不可区分。</p>
              <p><b>③ 部门求和：</b>两组份额相加后，只有 α = {{ privacyData.target.code }} 位置得到 β = {{ privacyData.target.load }}，其余位置为 0，因此管理部门只恢复出目标区域的统计值。</p>
              <p class="demo-note">演示份额用有限域 ℤ{{ privacyData.field }} 上的加法表示组合关系；论文中的真实份额由伪随机生成器递归展开，单个数值不能解释为用户负荷。</p>
            </div>
          </article>
        </section>

        <section v-show="active === 'results'" class="page">
          <div class="section-title"><div><span>05 / ANALYTICS</span><h2>电力分布分析结果</h2></div><p>呈现区域分布模式并识别可能存在不均衡的范围，为管理部门进一步处置提供依据。</p></div>
          <div class="results-grid">
            <article class="panel chart-panel"><div class="panel-head"><div><small>LOAD TREND</small><h3>全网聚合负荷趋势</h3></div><span class="delta">↑ 3.8% 较上一时段</span></div><div ref="chartEl" class="chart"></div></article>
            <article class="panel alert-panel"><small>REGIONAL INSIGHTS</small><h3>重点关注区域</h3><div class="alert-item" v-for="r in criticalRegions" :key="r.code"><span :class="statusClass(r.status)">{{ r.code }}</span><div><b>{{ r.name }}</b><p>聚合负荷 {{ r.load }}%，高于邻近区域</p></div><strong>{{ r.status === 'critical' ? '高' : '中' }}</strong></div></article>
          </div>
          <article class="panel conclusion"><div><span>ANALYSIS SUMMARY</span><h3>分析结论</h3></div><p>系统发现 <b>{{ criticalRegions.map(r => r.name).join('、') }}</b> 的聚合负荷存在偏高趋势，可能出现电力分布不均衡。建议电力管理部门优先检查相关区域，并结合实时运行数据进一步确认。</p><button class="outline" @click="go('overview')">返回区域地图</button></article>
        </section>

        <section v-show="active === 'performance'" class="page performance-page">
          <div class="section-title"><div><span>08 / PERFORMANCE EVALUATION</span><h2>方案性能评估</h2></div><p>从设备端计算、数据上传和管理端聚合三个方面，对比PSDA与代表性隐私计算方案。</p></div>
          <div class="performance-toolbar">
            <div><small>EXPERIMENT VARIABLE</small><b>实验维度</b></div>
            <button :class="{ active: perfScenario === 'length' }" @click="setPerfScenario('length')">编码长度</button>
            <button :class="{ active: perfScenario === 'devices' }" @click="setPerfScenario('devices')">IoT设备数量</button>
            <span>趋势复现数据 · 用于课程交互演示</span>
          </div>
          <div class="performance-summary">
            <article><span>DEVICE SIDE</span><strong>轻量计算</strong><p>DPF密钥生成避免逐区域执行高开销加密。</p></article>
            <article><span>COMMUNICATION</span><strong>低上传开销</strong><p>紧凑的密钥份额降低大规模设备通信负担。</p></article>
            <article><span>DEPARTMENT SIDE</span><strong>快速聚合</strong><p>管理端主要执行服务器结果相加，无需逐条解密。</p></article>
          </div>
          <div class="performance-grid">
            <article class="panel performance-card"><div><small>COMPUTATION TIME</small><h3>设备端计算时间</h3></div><div ref="computeChartEl" class="performance-chart"></div></article>
            <article class="panel performance-card"><div><small>UPLOAD COST</small><h3>上传通信开销</h3></div><div ref="uploadChartEl" class="performance-chart"></div></article>
            <article class="panel performance-card wide"><div><small>AGGREGATION TIME</small><h3>管理端聚合时间</h3></div><div ref="aggregateChartEl" class="performance-chart"></div><p class="performance-conclusion"><b>论文结论：</b>随着编码长度和IoT设备数量增加，各方案开销总体呈线性增长；PSDA在三项指标中保持较低开销，体现出面向大规模智能电网的扩展能力。</p></article>
          </div>
        </section>

        <section v-show="active === 'security'" class="page security-page">
          <div class="section-title"><div><span>07 / SECURITY MODEL</span><h2>安全假设与系统边界</h2></div><p>明确各参与实体的可信程度、可见信息与论文方案能够提供的安全保证。</p></div>
          <div class="security-entities">
            <article><span>EDGE</span><i>IoT</i><h3>物联网设备</h3><b class="trust medium">半诚实</b><p>按协议采集、编码和上传数据；当前方案不防御完全被攻陷后主动伪造数据的设备。</p></article>
            <article><span>SERVER 0</span><i>S₀</i><h3>协作服务器 A</h3><b class="trust medium">半诚实 · 不合谋</b><p>遵循计算协议，但可能尝试从自己持有的DPF份额中推断额外信息。</p></article>
            <article><span>SERVER 1</span><i>S₁</i><h3>协作服务器 B</h3><b class="trust medium">半诚实 · 不合谋</b><p>与服务器A独立运行；安全保证依赖两台服务器不会共享各自的秘密份额。</p></article>
            <article><span>AUTHORITY</span><i>DEP</i><h3>电力管理部门</h3><b class="trust high">完全可信</b><p>接收区域聚合结果，用于监测电网运行状态和优化资源配置。</p></article>
          </div>
          <div class="security-layout">
            <article class="panel visibility-matrix">
              <div class="panel-head"><div><small>DATA VISIBILITY MATRIX</small><h3>实体信息可见范围</h3></div><span>✓ 可见　— 不可见</span></div>
              <div class="security-table">
                <div class="security-row head"><span>参与实体</span><span>原始测量值</span><span>精确区域</span><span>单个DPF份额</span><span>区域聚合结果</span></div>
                <div class="security-row"><b>IoT设备</b><span class="yes">✓</span><span class="yes">✓</span><span>自身份额</span><span>—</span></div>
                <div class="security-row"><b>服务器A</b><span>—</span><span>—</span><span class="yes">k₀</span><span>局部结果</span></div>
                <div class="security-row"><b>服务器B</b><span>—</span><span>—</span><span class="yes">k₁</span><span>局部结果</span></div>
                <div class="security-row"><b>管理部门</b><span>—</span><span>区域级</span><span>—</span><span class="yes">✓</span></div>
              </div>
            </article>
            <article class="panel boundaries">
              <small>SCHEME BOUNDARIES</small><h3>方案能力边界</h3>
              <ul><li><i>✓</i><div><b>可以实现</b><p>保护上传过程中的目标区域与用电数据，输出区域级电力分布模式。</p></div></li><li><i>!</i><div><b>依赖条件</b><p>两台协作服务器必须互不合谋，并按照既定协议正确执行计算。</p></div></li><li><i>×</i><div><b>暂不支持</b><p>无法防御恶意IoT设备，也不负责精确定位短路或具体电气故障。</p></div></li></ul>
            </article>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>
