/* Run against the real LOCAL Django demo, after installing Playwright separately.
   npm install --no-save playwright
   npx playwright install chromium
   node scripts/capture_screenshots.cjs
   Requires seed_demo's fictional accounts. Does not contact external services. */
const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}, deviceScaleFactor: 1});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const output = path.join(__dirname, '..', 'docs', 'screenshots');
  fs.mkdirSync(output, {recursive: true});
  try {
    await page.goto('http://127.0.0.1:8000/accounts/login/');
    await page.getByLabel('Username:').fill('demo_coordinator');
    await page.getByLabel('Password:').fill('Demo-Only-2026!');
    await Promise.all([
      page.waitForURL('http://127.0.0.1:8000/'),
      page.getByRole('button', {name: 'Sign in →'}).click(),
    ]);
    await page.screenshot({path: path.join(output, 'dashboard.png'), fullPage: true});
    await page.getByRole('link', {name: /Launch press kit/}).click();
    await page.screenshot({path: path.join(output, 'report.png'), fullPage: true});
    await page.getByRole('link', {name: 'Partners & requirements'}).click();
    await page.screenshot({path: path.join(output, 'requirements.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.goto('http://127.0.0.1:8000/');
    await page.screenshot({path: path.join(output, 'mobile-dashboard.png'), fullPage: true});
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('Saved screenshots from the running fictional demo in docs/screenshots/.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
