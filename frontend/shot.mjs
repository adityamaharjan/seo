import { chromium } from 'playwright'
const out = process.argv[2]
const browser = await chromium.launch()
for (const scheme of ['light', 'dark']) {
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 1200 },
    colorScheme: scheme,
    deviceScaleFactor: 2,
  })
  const page = await ctx.newPage()
  const errors = []
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto('http://127.0.0.1:5199/preview.html', { waitUntil: 'networkidle' })
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${out}/preview-${scheme}.png`, fullPage: true })
  console.log(scheme, 'errors:', errors.length ? errors.join(' | ') : 'none')
  await ctx.close()
}
await browser.close()
