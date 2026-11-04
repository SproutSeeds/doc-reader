// Isolated UI simulation: permission/keyboard acceptance remains a device check.
import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.WORKSPACE_PREVIEW_URL || 'http://127.0.0.1:18766';
const output = process.env.WORKSPACE_QA_OUTPUT || 'reports/standalone-2026-11-04';
await mkdir(output, {recursive:true});
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH, args:['--mute-audio']});
const checks = [], faults = [];
try {
  for (const platform of ['macos','windows']) {
    const context = await browser.newContext({viewport:{width:1000,height:780}});
    await context.addInitScript(value => {window.readDocsDesktop = value;}, platform);
    const page = await context.newPage();
    page.on('pageerror', error => faults.push(error.message));
    assert.equal((await (await page.request.get(base + '/__workspace_preview__')).json()).isolated, true);
    await page.request.post(base + '/api/settings', {data:{setup_completed:false, setup_step:0, dictation_key:'f8', selection_shortcut:'<ctrl>+<alt>+r'}});
    let allowed = false;
    await page.route('**/api/state', async route => {
      const response = await route.fetch(); const data = await response.json();
      data.stt.hotkeys.platform = platform;
      data.tts.services.mac.bundled_models = true;
      Object.assign(data.stt.microphone, {native_helper_online:true, authorization:allowed?'authorized':'not determined', accessibility_trusted:allowed, input_monitoring_trusted:allowed});
      await route.fulfill({response, json:data});
    });
    await page.goto(base);
    await page.locator('#setupWizard[open]').waitFor();
    assert.match(await page.locator('#setupModelNote').innerText(), /Everything is included/);
    await page.screenshot({path:`${output}/setup-${platform}-speech.png`});
    await page.locator('#setupNext').click();
    await page.waitForFunction(()=>document.querySelector('#setupTitle').textContent === 'A little access.');
    assert.equal(await page.locator('#setupNext').isDisabled(), true);
    await page.screenshot({path:`${output}/setup-${platform}-access.png`});
    allowed = true;
    await page.waitForFunction(()=>!document.querySelector('#setupNext').disabled);
    await page.locator('#setupNext').click();
    await page.waitForFunction(()=>document.querySelector('#setupTitle').textContent === "Two keys. That's it.");
    assert.equal(await page.locator('#setupDictation').inputValue(), 'f8');
    await page.locator('#setupRecommended').click();
    assert.equal(await page.locator('#setupDictation').inputValue(), 'alt_l');
    assert.equal(await page.locator('#setupSelection').inputValue(), 'cmd_r');
    if (platform === 'windows') assert.match(await page.locator('#setupKeyboardNote').innerText(), /No right Windows key/);
    await page.screenshot({path:`${output}/setup-${platform}-shortcuts.png`});
    await page.locator('#setupNext').press('Tab');
    assert.equal(await page.locator('#setupLater').evaluate(el=>el===document.activeElement), true);
    await page.locator('#setupNext').click();
    await page.waitForFunction(()=>document.querySelector('#setupTitle').textContent === 'Make it yours.');
    assert.equal(await page.locator('#setupNext').isDisabled(), true);
    assert.equal(await page.locator('#setupHeard').isDisabled(), true);
    await page.locator('#setupListen').click();
    await page.waitForFunction(()=>!document.querySelector('#setupHeard').disabled);
    await page.locator('#setupHeard').check();
    await page.locator('#setupTrial').fill('A simulated dictation for interface verification.');
    await page.locator('#setupTried').check();
    await page.screenshot({path:`${output}/setup-${platform}-try.png`});
    await page.locator('#setupBack').click();
    await page.locator('#setupNext').press('Escape');
    await page.waitForFunction(()=>document.querySelector('#setupTitle').textContent === 'A little access.');
    await page.locator('#setupLater').click();
    await page.locator('#setupWizard').waitFor({state:'hidden'});
    await page.reload();
    await page.locator('#setupWizard[open]').waitFor();
    await page.waitForFunction(()=>document.querySelector('#setupTitle').textContent === 'A little access.');
    await page.waitForFunction(()=>!document.querySelector('#setupNext').disabled);
    await page.locator('#setupNext').click();
    for (const [width,height,theme] of [[520,620,'light'],[390,844,'light'],[1000,780,'dark']]) {
      await page.setViewportSize({width,height}); await page.emulateMedia({colorScheme:theme});
      assert.equal(await page.evaluate(()=>document.querySelector('#setupWizard').scrollWidth <= document.querySelector('#setupWizard').clientWidth + 1), true);
      await page.screenshot({path:`${output}/setup-${platform}-${width}-${theme}.png`});
      if (process.env.AXE_SCRIPT) {
        await page.addScriptTag({path:process.env.AXE_SCRIPT});
        const audit = await page.evaluate(async()=> (await axe.run(document.querySelector('#setupWizard'), {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})));
        assert.deepEqual(audit, []);
      }
    }
    await page.locator('#setupNext').click();
    await page.locator('#setupListen').click();
    await page.waitForFunction(()=>!document.querySelector('#setupHeard').disabled);
    await page.locator('#setupHeard').check(); await page.locator('#setupTried').check();
    await page.locator('#setupNext').click();
    await page.locator('#setupWizard').waitFor({state:'hidden'});
    await page.reload();
    await page.locator('#libraryToggle').waitFor();
    assert.equal(await page.locator('#setupWizard').isVisible(), false);
    const saved = await (await page.request.get(base + '/api/state')).json();
    assert.equal(saved.settings.setup_completed, true);
    assert.equal(saved.stt.hotkeys.dictation_key, 'alt_l');
    assert.equal(saved.stt.hotkeys.selection_shortcut, 'cmd_r');
    checks.push(`${platform}: first run, readiness and permission gates, preserved choices, recommended keys, try-it confirmation, Escape/Back/focus, resume, completion, 3 responsive views and accessibility`);
    await context.close();
  }
  assert.deepEqual(faults, []);
  await writeFile(`${output}/setup-browser.json`, JSON.stringify({checks, faults, permissions:'simulated', audio:'synthetic silent sample; no physical acceptance claimed'}, null, 2));
  console.log(checks.join('\n'));
} finally { await browser.close(); }
