import { chromium } from 'playwright'
import fs from 'fs'

const BASE = process.argv[2] || 'http://localhost:3000'
const shotDir = '/workspace/docs/screenshots'
fs.mkdirSync(shotDir, { recursive: true })
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
const errors = []
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()) })

await page.goto(BASE, { waitUntil: 'load' })
await page.waitForTimeout(3000)

const result = {}

// 先复位后端状态，避免历史巡检/低电量污染本用例
await page.evaluate(() => window.robotService.reset())
await page.waitForTimeout(800)

// 1. 撞墙三连：卡住提示 + 地图抖动（在 360ms 抖动窗口内检测）
await page.evaluate(() => window.robotService.move(0, -1)) // 起点贴地图上边界
await page.waitForTimeout(150)
result.blockedMode = await page.evaluate(() => window.robotService._state.mode)
result.shakeClass = await page.locator('.canvas-shake').count()
result.stuckToast = await page.locator('text=机器人被障碍物卡住').count()
await page.screenshot({ path: shotDir + '/feature-blocked-shake.png' })
await page.waitForTimeout(500)
result.shakeAutoReset = await page.locator('.canvas-shake').count()

// 2. 一键排障（正前方为边界墙：恢复 manual 即可）
result.resolveBtn = await page.locator('button:has-text("一键排障")').count()
await page.locator('button:has-text("一键排障")').first().click()
await page.waitForTimeout(600)
result.afterResolve = await page.evaluate(() => window.robotService._state.mode)
await page.screenshot({ path: shotDir + '/feature-after-resolve.png' })

// 3. 内置地图切换：仓储走廊（24 宽）
await page.locator('button:has-text("仓储走廊")').click()
await page.waitForTimeout(900)
result.warehouseWidth = await page.evaluate(() => window.robotService.getMap().width)
result.robotAtNewStart = await page.evaluate(() => {
  const m = window.robotService.getMap()
  const s = window.robotService._state
  return s.x === m.start[0] && s.y === m.start[1]
})
await page.screenshot({ path: shotDir + '/feature-preset-warehouse.png' })

// 4. 切回默认厂房 + 悬停详情徽标
await page.locator('button:has-text("默认厂房")').click()
await page.waitForTimeout(900)
const box = await page.locator('canvas').first().boundingBox()
await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3)
await page.waitForTimeout(400)
result.hoverBadge = await page.locator('text=/\\[\\d+, \\d+\\] ·/').count()
await page.screenshot({ path: shotDir + '/feature-hover-badge.png' })

// 5. 地图导入导出 / 形象上传入口
result.exportBtn = await page.locator('button:has-text("导出地图")').count()
result.importBtn = await page.locator('button:has-text("导入地图")').count()
result.avatarBtn = await page.locator('button:has-text("上传形象")').count()

// 6. 移动端入口
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })
await mobile.goto(BASE, { waitUntil: 'load' })
await mobile.waitForTimeout(2500)
result.mobileResolveBtn = await mobile.locator('button:has-text("一键排障")').count()
await mobile.screenshot({ path: shotDir + '/feature-mobile.png' })

await browser.close()
result.errors = errors
console.log(JSON.stringify(result, null, 2))
