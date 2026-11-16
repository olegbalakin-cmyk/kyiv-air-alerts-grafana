// Read-only browser proof for SEO draft preview. No third-party requests or website writes.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.SEO_PREVIEW_BASE || 'http://127.0.0.1:8765';
  const receipt = JSON.parse(fs.readFileSync('research/seo_pilot_2026_11_16/verified_snapshot.json', 'utf8'));
  const output = path.resolve('seo-preview-proof');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  const checks = [];
  try {
    for (const viewport of [
      {name: 'desktop', width: 1440, height: 900},
      {name: 'mobile', width: 390, height: 844}
    ]) {
      const context = await browser.newContext({
        viewport: {width: viewport.width, height: viewport.height},
        javaScriptEnabled: false,
        locale: 'uk-UA'
      });
      await context.route('**/*', route => {
        const host = new URL(route.request().url()).hostname;
        return host === '127.0.0.1' || host === 'localhost'
          ? route.continue() : route.abort();
      });
      const page = await context.newPage();
      for (const lang of ['uk', 'en']) {
        const dashboard = lang === 'uk' ? '/' : '/en/';
        const index = lang === 'uk' ? '/stats/' : '/en/stats/';
        const label = lang === 'uk' ? 'Статистика у таблицях' : 'Data tables';
        let response = await page.goto(base + dashboard, {waitUntil: 'domcontentloaded'});
        assert.equal(response.status(), 200, 'dashboard HTTP status');
        const link = page.locator('footer #staticStatsFooterLink');
        assert.equal(await link.count(), 1, 'one footer link');
        assert.equal((await link.textContent()).trim(), label, 'localized footer');
        assert.equal(await link.getAttribute('href'), index, 'localized URL');
        await page.locator('footer').scrollIntoViewIfNeeded();
        await page.locator('footer').screenshot({path: path.join(output, viewport.name + '-' + lang + '-footer.png')});
        checks.push({viewport: viewport.name, lang, kind: 'footer', href: index, pass: true});
        response = await page.goto(base + index, {waitUntil: 'domcontentloaded'});
        assert.equal(response.status(), 200, 'static index HTTP status');
        assert.equal(await page.locator('tbody tr').count(), 3, 'three index rows');
        const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        assert.ok(width <= 2, 'index horizontal overflow ' + width);
        await page.screenshot({path: path.join(output, viewport.name + '-' + lang + '-index.png')});
        checks.push({viewport: viewport.name, lang, kind: 'index', rows: 3, horizontalOverflowPx: width, pass: true});
        for (const item of receipt.cities) {
          const href = index + item.slug + '/2026-10/';
          response = await page.goto(base + href, {waitUntil: 'domcontentloaded'});
          assert.equal(response.status(), 200, 'city HTML HTTP status');
          assert.equal(await page.locator('tbody tr').count(), 31, 'daily rows for ' + item.slug);
          assert.equal(Number(await page.locator('[data-month-count]').getAttribute('data-month-count')), item.month_count, 'monthly count');
          const monthSeconds = Number(await page.locator('[data-month-seconds]').getAttribute('data-month-seconds'));
          assert.ok(Math.abs(monthSeconds - item.month_seconds) < 0.01, 'monthly seconds');
          assert.equal(await page.locator('script[type="application/ld+json"]').count(), 1, 'JSON-LD exists');
          if (item.slug === 'lviv') {
            assert.match(await page.locator('main').innerText(), lang === 'uk' ? /район/ : /Raion/);
          }
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
          assert.ok(overflow <= 2, 'city horizontal overflow ' + item.slug + ': ' + overflow);
          if (item.slug === 'kyiv' || item.slug === 'lviv')
            await page.screenshot({path: path.join(output, viewport.name + '-' + lang + '-' + item.slug + '.png')});
          checks.push({viewport: viewport.name, lang, kind: 'city', slug: item.slug, rows: 31, count: item.month_count, seconds: monthSeconds, horizontalOverflowPx: overflow, pass: true});
        }
      }
      await context.close();
      // Regression: the real dashboard runs a localization function which
      // rewrites footer <span> elements. Test with JS enabled as well.
      const interactive = await browser.newContext({
        viewport: {width: viewport.width, height: viewport.height},
        javaScriptEnabled: true,
        locale: 'uk-UA'
      });
      await interactive.route('**/*', route => {
        const host = new URL(route.request().url()).hostname;
        return host === '127.0.0.1' || host === 'localhost'
          ? route.continue() : route.abort();
      });
      const interactivePage = await interactive.newPage();
      for (const lang of ['uk', 'en']) {
        const dashboard = lang === 'uk' ? '/' : '/en/';
        const index = lang === 'uk' ? '/stats/' : '/en/stats/';
        const label = lang === 'uk' ? 'Статистика у таблицях' : 'Data tables';
        const response = await interactivePage.goto(base + dashboard, {waitUntil: 'domcontentloaded'});
        assert.equal(response.status(), 200, 'JS dashboard status');
        await interactivePage.waitForTimeout(1200);
        const link = interactivePage.locator('footer #staticStatsFooterLink');
        assert.equal(await link.count(), 1, 'footer link survives JS initialization');
        assert.equal((await link.textContent()).trim(), label, 'JS localized link');
        assert.equal(await link.getAttribute('href'), index, 'JS localized destination');
        assert.ok(await link.isVisible(), 'footer link is visible with JS on');
        assert.equal(await interactivePage.evaluate(() => {
          return document.querySelectorAll('footer > span').length;
        }), 2, 'existing JS-managed footer spans preserved');
        if (lang === 'en') {
          const first = await interactivePage.locator('footer > span').first().innerText();
          assert.match(first, /Data and code/, 'real English JS localization ran');
        }
        await link.scrollIntoViewIfNeeded();
        await link.screenshot({path: path.join(output, viewport.name + '-' + lang + '-js-enabled-link.png')});
        await link.click();
        await interactivePage.waitForURL('**' + index);
        assert.equal(await interactivePage.locator('tbody tr').count(), 3, 'JS enabled click opens stat index');
        checks.push({viewport: viewport.name, lang, kind: 'js-enabled-footer-navigation', href: index, pass: true});
      }
      await interactive.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(output, 'visual-matrix.json'), JSON.stringify({source: receipt.input_sha_git_blob, checks}, null, 2));
  assert.equal(checks.length, 24);
  process.stdout.write('SEO_PREVIEW_BROWSER_PASS: 24/24 no-JS and JS-enabled UA+EN desktop+mobile checks; screenshots recorded\n');
})().catch(err => {
  process.stderr.write('SEO_PREVIEW_BROWSER_FAIL: ' + (err.stack || err) + '\n');
  process.exitCode = 1;
});
