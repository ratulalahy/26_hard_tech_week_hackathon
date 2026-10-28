import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.dirname(root);
const bundle = fs.readFileSync(path.join(root, 'data.js'), 'utf8');
const sandbox = { window: {} };
vm.runInNewContext(bundle, sandbox);
const D = JSON.parse(JSON.stringify(sandbox.window.PILOT_DATA));
const gitJSON = source => {
  const bytes = execFileSync('git', ['show', `${D.source_commit}:${source}`], {cwd: repo});
  assert.equal(createHash('sha256').update(bytes).digest('hex'), D.sources[source].sha256);
  return JSON.parse(bytes);
};
const m = gitJSON('results/test/metrics.json');
const e = gitJSON('results/test/extras.json');
const s = gitJSON('results/storage.json');
assert.deepEqual(D.routing.primary.contrast, m.contrasts.find(c => c.candidate === 'S' && c.reference === 'U').blocks['4']);
assert.deepEqual(D.routing.limited.contrast, e.extensions.mobility_le_8gpus.vs_U.S['4']);
assert.deepEqual(D.routing.timing.contrast, m.contrasts.find(c => c.candidate === 'W_time' && c.reference === 'U').blocks['4']);
assert.deepEqual(D.storage.assumptions, s.assumptions);
for (const aim of ['peak','carbon']) assert.deepEqual(D.storage.schedules[aim].metrics, e.storage.schedule_comparison.schedules[aim].cases.U['4']);
assert.equal(m.policies.S.metrics.completed_gpu_s.value, m.policies.U.metrics.completed_gpu_s.value);
assert.equal(m.policies.S.metrics.execution_kwh.value, m.policies.U.metrics.execution_kwh.value);
assert.equal(e.extensions.mobility_le_8gpus.policies.U.co2_kg.value, m.policies.U.metrics.co2_kg.value);
console.log('PASS: source hashes, both routing contrasts, waiting comparator, storage outcomes, assumptions and primary completed-work equality.');
const candidates = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', chromium.executablePath()];
const cache = path.join(os.homedir(), '.cache/ms-playwright');
if (fs.existsSync(cache)) for (const dir of fs.readdirSync(cache).filter(d => /^chromium-/.test(d)).sort().reverse()) {
  for (const arch of ['chrome-linux-arm64','chrome-linux64','chrome-linux']) candidates.push(path.join(cache,dir,arch,'chrome'));
}
const executablePath = candidates.find(p => p && fs.existsSync(p));
if (!executablePath) throw new Error('Chrome not found. Set CHROME_PATH to an installed Chrome binary.');
const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox']});
const errors = [], net = [], report = [];
const url = pathToFileURL(path.join(root, 'index.html')).href;
try {
  for (const viewport of [{width:1440,height:900},{width:1728,height:1117},{width:390,height:844}]) {
    const context = await browser.newContext({viewport, reducedMotion:'reduce', offline:true});
    await context.route('**/*', route => { if (route.request().url().startsWith('file:')) return route.continue(); net.push(route.request().url()); return route.abort(); });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => { if(m.type() === 'error') errors.push(m.text()); });
    await page.goto(url);
    await page.waitForSelector('html[data-ready="1"]');
    await page.evaluate(() => document.fonts.ready);
    for (const state of ['primary','limited','storage-peak','storage-carbon']) {
      const scene = state.startsWith('storage') ? 'storage' : state;
      await page.locator(`button[data-scene="${scene}"]`).click();
      if (scene === 'storage') await page.locator(`button[data-aim="${state.split('-')[1]}"]`).click();
      if (scene !== 'storage') {
        const expected = (D.routing[scene].contrast.saving.value * 100).toFixed(1) + '%';
        assert.equal(await page.locator('[data-metric="saving"]').innerText(), expected);
        const ci = D.routing[scene].contrast.saving_ci95.value.map(v => (v*100).toFixed(1)).join('–');
        assert.ok((await page.locator('.interval').innerText()).includes(ci));
      } else {
        const metrics = D.storage.schedules[state.split('-')[1]].metrics;
        assert.equal(await page.locator('[data-metric="rush"]').innerText(), metrics.rush_import_after_mw.value.toFixed(2) + ' MW');
        assert.ok((await page.locator('[data-metric="storage-carbon"]').innerText()).startsWith((metrics.cut_frac.value*100).toFixed(1)+'%'));
        assert.equal(await page.locator('.hour.charge').count(), D.storage.schedules[state.split('-')[1]].charge_hours.value.length);
      }
      const overflow = await page.evaluate(() => [...document.querySelectorAll('main *')].filter(el => {
        if (!el.getClientRects().length || el.classList.contains('sr-only')) return false;
        const r=el.getBoundingClientRect();return r.right>innerWidth+1 || r.left < -1;
      }).map(el => el.tagName+'.'+el.className));
      assert.deepEqual(overflow, [], `Horizontal overflow in ${state} at ${viewport.width}`);
      await page.addScriptTag({path:path.join(root,'node_modules/axe-core/axe.min.js')});
      const violations = await page.evaluate(async () => (await axe.run(document,{preload:false,runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})));
      assert.deepEqual(violations, [], `Accessibility ${state} ${viewport.width}`);
      await page.screenshot({path:path.join(root,`qa/${state}-${viewport.width}.png`),fullPage:true});
      report.push({state,width:viewport.width,axeViolations:violations.length});
    }
    await page.locator('#evidence-open').click();
    assert.ok((await page.locator('#evidence-body').innerText()).includes(D.source_commit));
    assert.ok((await page.locator('#evidence-body').innerText()).includes('schedules.carbon.cases.U.4'));
    const dialogAxe=await page.evaluate(async ()=>(await axe.run(document,{preload:false,runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>v.id));
    assert.deepEqual(dialogAxe,[]);
    await page.screenshot({path:path.join(root,`qa/evidence-${viewport.width}.png`),fullPage:true});
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#evidence').evaluate(el=>el.open),false);
    await page.locator('#restart').click();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('html').getAttribute('data-scene'),'limited');
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('html').getAttribute('data-scene'),'storage');
    await page.keyboard.press('ArrowLeft');
    assert.equal(await page.locator('html').getAttribute('data-scene'),'limited');
    await page.locator('#restart').click();
    await page.locator('[data-next="limited"]').click();
    await page.locator('[data-next="storage"]').click();
    await page.locator('#inspect-storage').click();
    assert.equal(await page.locator('#evidence').evaluate(el=>el.open),true);
    await context.close();
    console.log(`PASS: four states at ${viewport.width}×${viewport.height}, offline file://, exact metrics, no overflow, axe 0, evidence, keyboard and guided flow.`);
  }
  for (const broken of ['window.PILOT_DATA = undefined;', bundle.replace('"saving": {','"missingSaving": {')]) {
    const context = await browser.newContext();
    await context.route('**/data.js', route => route.fulfill({contentType:'application/javascript',body:broken}));
    const page = await context.newPage();
    await page.goto(url);
    await page.waitForSelector('html[data-ready="error"]');
    assert.equal(await page.locator('#error').isVisible(),true);
    assert.equal(await page.locator('#content').isVisible(),false);
    await context.close();
  }
  console.log('PASS: absent and malformed evidence fail visibly, without invented zero values.');
  assert.deepEqual(errors,[],'Browser errors');assert.deepEqual(net,[],'Network attempts');
  fs.writeFileSync(path.join(root,'qa/test-report.json'),JSON.stringify({sourceCommit:D.source_commit,browserVersion:browser.version(),platform:process.platform,checks:report,browserErrors:errors,networkAttempts:net},null,2)+'\n');
  console.log('PASS: zero browser errors and zero external network requests.');
} finally { await browser.close(); }
