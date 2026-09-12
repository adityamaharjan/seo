import { chromium } from 'playwright'
const out = process.argv[2]
const browser = await chromium.launch()
const ctx = await browser.newContext({
  viewport: { width: 1180, height: 900 },
  deviceScaleFactor: 3,
})
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5199/preview.html', { waitUntil: 'networkidle' })
await page.waitForTimeout(500)

// The report masthead: score dial, title, counts.
const masthead = page.locator('[role="img"]').first().locator('xpath=..')
await masthead.screenshot({ path: `${out}/crop-masthead.png` })

// The keyword targeting card, legend included.
await page.locator('section[aria-labelledby="keywords"]').screenshot({ path: `${out}/crop-keywords.png` })

// The first group of checks.
await page.locator('section[aria-labelledby="checks"]').screenshot({ path: `${out}/crop-checks.png` })
console.log('ok')
await browser.close()
