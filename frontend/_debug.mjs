import { chromium } from 'playwright'

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
page.on('pageerror', (e) => console.log('PAGEERROR:', e.message))
page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE:', m.text()) })

await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)

// 先复位后端状态，等回到 manual 且电量满格
await page.evaluate(() => window.robotService.reset())
await page.waitForTimeout(800)
console.log('复位后:', await page.evaluate(() => ({
  mode: window.robotService._state.mode,
  battery: window.robotService._state.battery,
  x: window.robotService._state.x,
  y: window.robotService._state.y,
})))

// 触发撞墙：起点 (0,0) 向上是界外
await page.evaluate(() => window.robotService.move(0, -1))
await page.waitForTimeout(150)
console.log('撞墙后 150ms mode:', await page.evaluate(() => window.robotService._state.mode))
console.log('撞墙后 150ms shake class:', await page.locator('.canvas-shake').count())
console.log('撞墙后 150ms toast 数:', await page.locator('.fixed.top-14 > div').count())

// 等抖动结束（360ms）确认自动复位
await page.waitForTimeout(500)
console.log('700ms 后 shake class:', await page.locator('.canvas-shake').count())

// toast 文本确认
const texts = await page.locator('.fixed.top-14 > div').allTextContents()
console.log('当前 toast 文本:', JSON.stringify(texts))

// 一键排障：正前方是边界墙，应恢复 manual
await page.locator('button:has-text("一键排障")').first().click()
await page.waitForTimeout(500)
console.log('排障后 mode:', await page.evaluate(() => window.robotService._state.mode))

await browser.close()
