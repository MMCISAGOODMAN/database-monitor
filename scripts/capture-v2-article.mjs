/**
 * v2.0 公众号文章实拍截图
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const BASE = process.env.BASE_URL || 'http://localhost:8088'
const OUT = path.resolve(ROOT, 'docs/wechat-article-v2/images')

async function waitForSite(page, retries = 60) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 5000 })
      if (res && res.ok()) return
      if (res && [200, 301, 302, 304].includes(res.status())) return
    } catch {
      /* retry */
    }
    await page.waitForTimeout(2000)
  }
  throw new Error(`站点不可用: ${BASE}`)
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await page.screenshot({ path: path.join(OUT, '01-login.png'), fullPage: false })

  const user = page.locator('input').first()
  const pass = page.locator('input[type="password"]').first()
  await user.fill('admin')
  await pass.fill('admin123')
  await page.locator('button').filter({ hasText: /登/ }).first().click()
  await page.waitForTimeout(3500)
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const browser = await chromium.launch()
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  })
  const page = await ctx.newPage()

  await waitForSite(page)
  await login(page)

  // 大屏
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(4000)
  await page.screenshot({ path: path.join(OUT, '02-dashboard.png'), fullPage: false })

  // 全屏
  const fsBtn = page.locator('button[title="全屏"]')
  if (await fsBtn.count()) {
    await fsBtn.click()
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT, '03-dashboard-fullscreen.png'), fullPage: false })
    const exitBtn = page.locator('button[title="退出全屏"]')
    if (await exitBtn.count()) await exitBtn.click()
    await page.waitForTimeout(500)
  } else {
    await page.screenshot({ path: path.join(OUT, '03-dashboard-fullscreen.png'), fullPage: false })
  }

  // 管理页实例
  await page.goto(`${BASE}/manage`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)
  await page.screenshot({ path: path.join(OUT, '06-manage-instances.png'), fullPage: true })

  // 告警规则
  const rulesTab = page.locator('.el-tabs__item').filter({ hasText: '告警规则' })
  if (await rulesTab.count()) {
    await rulesTab.click()
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT, '07-manage-rules.png'), fullPage: true })
  }

  // 从 API 拿一个可用实例 id
  const token = await page.evaluate(() => localStorage.getItem('token'))
  let instanceId = null
  let redisId = null
  if (token) {
    const res = await page.request.get(`${BASE}/api/instances`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok()) {
      const body = await res.json()
      const list = body.data || []
      const redis = list.find((i) => i.db_type === 'redis')
      const mysql = list.find((i) => i.db_type === 'mysql')
      const any = list[0]
      redisId = redis?.id
      instanceId = mysql?.id || redis?.id || any?.id
    }
  }

  if (!instanceId) {
    // 大屏点进详情兜底
    await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(2000)
    const row = page.locator('.instance-row, .el-table__row, [class*="instance"]').first()
    if (await row.count()) {
      await row.dblclick().catch(() => row.click())
      await page.waitForTimeout(2500)
    }
  } else {
    await page.goto(`${BASE}/instance/${instanceId}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(3000)
  }

  await page.screenshot({ path: path.join(OUT, '04-instance-detail.png'), fullPage: true })

  // 建议区域特写
  const suggestion = page.locator('.suggestion-card').first()
  if (await suggestion.count()) {
    await suggestion.screenshot({ path: path.join(OUT, '05-suggestions.png') })
  } else {
    await page.screenshot({ path: path.join(OUT, '05-suggestions.png'), fullPage: false })
  }

  // Redis 详情（若有）
  if (redisId && redisId !== instanceId) {
    await page.goto(`${BASE}/instance/${redisId}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(3000)
    await page.screenshot({ path: path.join(OUT, '08-redis-detail.png'), fullPage: true })
  } else if (redisId) {
    // 已在 redis 详情
    await page.screenshot({ path: path.join(OUT, '08-redis-detail.png'), fullPage: true })
  } else {
    // 复用详情图
    await page.screenshot({ path: path.join(OUT, '08-redis-detail.png'), fullPage: true })
  }

  // 封面 HTML -> PNG
  const coverPath = path.resolve(ROOT, 'docs/wechat-article-v2/cover.html')
  await page.setViewportSize({ width: 900, height: 383 })
  await page.goto('file://' + coverPath, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  const coverEl = page.locator('#cover')
  if (await coverEl.count()) {
    await coverEl.screenshot({ path: path.join(OUT, 'cover.png') })
  } else {
    await page.screenshot({ path: path.join(OUT, 'cover.png'), fullPage: false })
  }

  await browser.close()
  await writeFile(
    path.join(OUT, '.captured'),
    `captured_at=${new Date().toISOString()}\nbase=${BASE}\ninstance=${instanceId}\n`,
  )
  console.log('Screenshots saved to', OUT)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
