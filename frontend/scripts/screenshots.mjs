/**
 * 脚本功能：使用 Playwright 自动生成项目截图
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-23
 * 版本：V1.0
 *
 * 运行方式：node scripts/screenshots.mjs（需先 npm run preview 启动服务）
 */

import { chromium } from 'playwright'
import { mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const outputDir = join(__dirname, '..', '..', 'docs', 'screenshots')
mkdirSync(outputDir, { recursive: true })

const baseUrl = 'http://localhost:4173'

async function waitForService(page) {
  await page.waitForFunction(() => window.robotService !== undefined)
}

async function desktopPage(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await context.newPage()
  await page.goto(baseUrl)
  await waitForService(page)
  return { context, page }
}

async function mobilePage(browser) {
  const context = await browser.newContext({ viewport: { width: 375, height: 812 } })
  const page = await context.newPage()
  await page.goto(baseUrl)
  await waitForService(page)
  return { context, page }
}

async function captureDesktopOverview(browser) {
  const { page, context } = await desktopPage(browser)
  await page.screenshot({ path: join(outputDir, 'desktop-overview.png') })
  await context.close()
}

async function captureMobileOverview(browser) {
  const { page, context } = await mobilePage(browser)
  await page.getByText('打开面板').click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: join(outputDir, 'mobile-overview.png') })
  await context.close()
}

async function captureMapEditing(browser) {
  const { page, context } = await desktopPage(browser)
  await page.evaluate(() => window.robotService.reset())
  await page.getByText('障碍').first().click()
  const box = await page.locator('canvas').first().boundingBox()
  const startX = box.x + box.width / 2 - 40
  const startY = box.y + box.height / 2 - 40
  await page.mouse.move(startX, startY)
  await page.mouse.down()
  await page.mouse.move(startX + 120, startY, { steps: 10 })
  await page.mouse.move(startX + 120, startY + 80, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(300)
  await page.screenshot({ path: join(outputDir, 'map-editing.png') })
  await context.close()
}

async function capturePatrolRunning(browser) {
  const { page, context } = await desktopPage(browser)
  await page.evaluate(() => window.robotService.reset())
  await page.getByText('开始巡检').first().click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: join(outputDir, 'patrol-running.png') })
  await context.close()
}

async function captureAlertToast(browser) {
  const { page, context } = await desktopPage(browser)
  await page.evaluate(() => {
    window.robotService._addAnomaly('overheat', '机身温度过高：65.0℃', [5, 5])
  })
  await page.waitForTimeout(500)
  await page.screenshot({ path: join(outputDir, 'alert-toast.png') })
  await context.close()
}

async function capturePlayback(browser) {
  const { page, context } = await desktopPage(browser)
  await page.evaluate(() => window.robotService.reset())
  await page.evaluate(() => {
    window.robotService.startPatrol([[3, 3]])
  })
  await page.waitForTimeout(5000)
  await page.locator('.play-pause-button').first().click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: join(outputDir, 'playback.png') })
  await context.close()
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
  try {
    await captureDesktopOverview(browser)
    await captureMobileOverview(browser)
    await captureMapEditing(browser)
    await capturePatrolRunning(browser)
    await captureAlertToast(browser)
    await capturePlayback(browser)
    console.log('截图已保存到：', outputDir)
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error('截图失败：', error)
  process.exit(1)
})
