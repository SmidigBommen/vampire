// Production check: node --input-type=module - URL SCREENSHOT < browser_check.mjs
// Run from a directory whose node_modules has playwright-core. Needs a Chromium in ~/.cache/ms-playwright.
// Loads the page, presses Enter twice, waits, and exits 1 on a page error, console error,
// failed request or a missing canvas. Does not write anything to the site.
import { chromium } from 'playwright-core';
import { readdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const [url, shot] = process.argv.slice(2);
if (!url) {
  console.log('usage: node --input-type=module - URL [SCREENSHOT] < browser_check.mjs');
  process.exit(2);
}
const cache = join(homedir(), '.cache', 'ms-playwright');
const dir = readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().pop();
const sub = readdirSync(join(cache, dir)).find((d) => d.startsWith('chrome'));
const browser = await chromium.launch({ executablePath: join(cache, dir, sub, 'chrome'), args: ['--autoplay-policy=no-user-gesture-required', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 852, height: 480 } });
const errors = [];
page.on('pageerror', (e) => errors.push(`page error: ${e}`));
page.on('console', (m) => m.type() === 'error' && errors.push(`console: ${m.text()}`));
page.on('response', (r) => r.status() >= 400 && errors.push(`${r.status()} ${r.url()}`));
page.on('requestfailed', (r) => errors.push(`request failed: ${r.url()}`));
try {
  await page.goto(`${url}?t=${Date.now()}`, { waitUntil: 'load', timeout: 30000 });
  await page.waitForSelector('canvas', { timeout: 15000 });
  for (let i = 0; i < 2; i++) {
    await page.waitForTimeout(2000);
    await page.keyboard.press('Enter', { delay: 40 });
  }
  await page.waitForTimeout(4000);
  if (shot) await page.screenshot({ path: shot });
} catch (e) {
  errors.push(String(e));
}
await browser.close();
if (errors.length) {
  console.log(errors.join('\n'));
  process.exit(1);
}
console.log('ok');
