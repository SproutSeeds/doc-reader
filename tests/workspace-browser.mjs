// Run against tests/serve_workspace_preview.py, never a personal library.
// PLAYWRIGHT_MODULE may point to an existing Playwright install. No runtime dependency.
import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.WORKSPACE_PREVIEW_URL || 'http://127.0.0.1:18766';
const output = resolve(process.env.WORKSPACE_QA_OUTPUT || 'reports/app-design-2026-11-03');
await mkdir(output, {recursive:true});
const browser = await chromium.launch({headless:true,
  ...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {}),
  args:['--disable-gpu', '--mute-audio']});
const checks = [];
const faults = [];
const record = name => {checks.push(name); console.log('PASS', name);};
const state = async page => (await page.request.get(`${base}/api/state`)).json();
const visible = async (page, selector) => page.locator(selector).waitFor({state:'visible',timeout:8000});
const hidden = async (page, selector) => page.locator(selector).waitFor({state:'hidden',timeout:8000});
const panelOpen = async (page, id) => assert.equal(await page.locator(id).evaluate(el=>el.open), true);
const focusIs = async (page, id) => page.waitForFunction(id=>document.activeElement.id===id,id,{timeout:8000});
const waitText = (page, selector, text) => page.waitForFunction(({selector,text})=>document.querySelector(selector).textContent.includes(text), {selector,text});
const pages = [];
const accessibility = [];

async function newPage(viewport, colorScheme='light') {
  const context = await browser.newContext({viewport, colorScheme, permissions:['clipboard-read','clipboard-write']});
  const page = await context.newPage();
  pages.push(page);
  page.on('pageerror', e=>faults.push(e.message));
  await page.goto(base);
  await page.waitForFunction(()=>document.querySelectorAll('.row-item').length >= 2);
  if (process.env.AXE_SCRIPT) await page.addScriptTag({path:process.env.AXE_SCRIPT});
  return page;
}

async function audit(page,name) {
  if (!process.env.AXE_SCRIPT) return;
  if (!await page.evaluate(()=>typeof window.axe==='object')) await page.addScriptTag({path:process.env.AXE_SCRIPT});
  const result=await page.evaluate(()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
  const violations=result.violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)}));
  accessibility.push({name,violations});
  assert.deepEqual(violations,[],`Accessibility: ${name}`);
}

async function geometry(page) {
  const result = await page.evaluate(()=>{
    const controls = document.querySelector('.control-bar').getBoundingClientRect();
    const open = document.querySelector('dialog[open]');
    const dialog = open?.getBoundingClientRect();
    return {
      overflow:document.documentElement.scrollWidth > innerWidth,
      centered:Math.abs((controls.left+controls.right)/2 - innerWidth/2) < 1,
      dockVisible:controls.bottom <= innerHeight && controls.left >= 0 && controls.right <= innerWidth,
      panelVisible:!dialog || (dialog.left >= 0 && dialog.right <= innerWidth && dialog.top >= 0 && dialog.bottom <= innerHeight),
    };
  });
  assert.deepEqual(result, {overflow:false,centered:true,dockVisible:true,panelVisible:true});
}

try {
  const isolated = await (await fetch(`${base}/__workspace_preview__`)).json();
  assert.deepEqual(isolated,{isolated:true,playback:'simulated'},'Refuse to modify a personal library');
  await fetch(`${base}/api/stop`,{method:'POST'});
  await fetch(`${base}/api/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speech_backend:'local-kokoro',kokoro_voice:'af_heart',read_rate:180,stt_enabled:true})});
  const page = await newPage({width:1440,height:960});
  assert.equal(await page.title(), 'Read Docs');
  await hidden(page,'#pause'); await hidden(page,'#stop');
  await hidden(page,'#newText');
  assert.equal(await page.locator('button svg').count(),0);
  await page.screenshot({path:`${output}/draft-desktop.png`});
  await audit(page,'canvas');
  record('Quiet initial workspace and text-only controls');

  const draft = 'A draft that survives library navigation.\n\nA second paragraph stays intact.';
  await page.locator('#text').fill(draft);
  await page.waitForFunction(value=>localStorage.getItem('docReader.draft')===value,draft);
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#text').value.length>0);
  assert.equal(await page.locator('#text').inputValue(),draft);
  record('Draft survives reload without changing storage keys');

  await page.locator('#libraryToggle').click();
  await panelOpen(page,'#librarySidebar'); await focusIs(page,'librarySearch');
  await page.screenshot({path:`${output}/library-desktop.png`});
  await page.locator('#showAll').focus();
  await page.locator('#showAll').press('ArrowRight');
  assert.equal(await page.locator('#showReadings').getAttribute('aria-selected'),'true');
  await page.locator('#librarySearch').fill('little room');
  assert.equal(await page.locator('.row-item').count(),1);
  await page.locator('.row-item').click();
  await waitText(page,'#itemViewText','The first light');
  await focusIs(page,'workspaceSurface');
  await page.screenshot({path:`${output}/reading-desktop.png`});
  record('Library search, keyboard filters, selection and workspace focus');

  await page.locator('#copyItem').click();
  assert.ok((await page.evaluate(()=>navigator.clipboard.readText())).startsWith('The first light'));
  await page.locator('#editItem').click();
  const savedText = await page.locator('#itemEditor').inputValue();
  const editMarker = `Edited during isolated QA at ${Date.now()}.`;
  await page.locator('#itemEditor').fill(savedText+'\n\n'+editMarker);
  await page.locator('#inspectorToggle').click();
  await page.locator('#inspectorClose').press('Escape');
  await visible(page,'#itemEditor');
  assert.ok((await page.locator('#itemEditor').inputValue()).endsWith(editMarker));
  await page.locator('#saveItem').click();
  await waitText(page,'#itemViewText',editMarker);
  await focusIs(page,'editItem');
  await page.locator('#newText').click();
  assert.equal(await page.locator('#text').inputValue(),draft);
  record('Copy, edit, panel Escape, save, focus restoration and draft preservation');

  await page.locator('#readText').click();
  await visible(page,'#pause'); await visible(page,'#stop'); await hidden(page,'#readText');
  await page.locator('#pause').click();
  await waitText(page,'#pause','Resume');
  await page.locator('#pause').click();
  await waitText(page,'#pause','Pause');
  await page.locator('#stop').click();
  await hidden(page,'#pause'); await hidden(page,'#stop'); await visible(page,'#readText');
  record('Read, pause, resume and stop use existing API routes (simulated audio)');

  for (const [trigger, panel, close] of [
    ['libraryToggle','librarySidebar','libraryClose'], ['importToggle','importMenu','importClose'],
    ['inspectorToggle','inspector','inspectorClose'], ['voiceButton','voiceMenu','voiceClose'],
    ['rateButton','rateMenu','rateClose'], ['dictationChip','inspector','inspectorClose'],
  ]) {
    await page.locator(`#${trigger}`).click();
    await panelOpen(page,`#${panel}`);
    await audit(page,panel);
    // Native modal dialogs keep keyboard focus out of the background canvas.
    for(let index=0; index<12; index++) {
      await page.locator(':focus').press('Tab');
      assert.ok(await page.evaluate(id=>document.getElementById(id).contains(document.activeElement),panel),`${panel} focus stays contained after Tab ${index}`);
    }
    await page.locator(`#${close}`).focus();
    await page.locator(`#${close}`).press('Escape');
    await hidden(page,`#${panel}`); await focusIs(page,trigger);
    await page.locator(`#${trigger}`).click();
    await page.locator(`#${close}`).click();
    await focusIs(page,trigger);
  }
  record('Every panel has Close, Escape, contained focus and correct return focus');

  await page.locator('#voiceButton').click();
  await page.screenshot({path:`${output}/voices-desktop.png`});
  await page.getByRole('button',{name:'Play a sample of Bella',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.voice-preview.playing'));
  await page.locator('#voiceClose').click();
  await page.locator('#voiceButton').click();
  assert.equal(await page.locator('.voice-preview.playing').count(),0);
  await page.locator('.voice-option[data-voice="af_bella"]').click();
  await hidden(page,'#voiceMenu'); await focusIs(page,'voiceButton');
  assert.equal((await state(page)).tts.kokoro_voice,'af_bella');
  await page.locator('#rateButton').click();
  await page.locator('#readRate').fill('225');
  await waitText(page,'#readRateValue','225');
  await page.waitForFunction(()=>document.querySelector('#rateButton').textContent==='1.25×');
  await page.locator('#rateClose').click();
  await page.waitForFunction(async()=> (await (await fetch('/api/state')).json()).settings.read_rate===225);
  record('Voice sample cleanup, voice selection and speed persistence');

  // Fail a settings request while the modal is open; the error must be readable there.
  await page.route('**/api/settings', route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'QA speech service unavailable.'})}));
  await page.locator('#voiceButton').click();
  await page.locator('.voice-option[data-voice="af_heart"]').click();
  await waitText(page,'#voiceMenu .panel-error','QA speech service unavailable');
  await page.locator('#voiceClose').click();
  await page.unroute('**/api/settings');
  await page.locator('#voiceButton').click();
  await page.locator('.voice-option[data-voice="af_heart"]').click();
  record('Action errors stay visible in the active modal and recover');

  await page.locator('#importToggle').click();
  await page.locator('#file').setInputFiles({name:'Reading sample.txt',mimeType:'text/plain',buffer:Buffer.from('An imported text document with a complete sentence.')});
  await hidden(page,'#importMenu');
  await waitText(page,'#itemViewText','An imported text document');
  await page.locator('#stop').click();
  await page.locator('#importToggle').click();
  await page.locator('#audioTimestamps').check();
  const wav=Buffer.alloc(44+32000);
  wav.write('RIFF',0); wav.writeUInt32LE(wav.length-8,4); wav.write('WAVEfmt ',8);
  wav.writeUInt32LE(16,16); wav.writeUInt16LE(1,20); wav.writeUInt16LE(1,22);
  wav.writeUInt32LE(16000,24); wav.writeUInt32LE(32000,28); wav.writeUInt16LE(2,32); wav.writeUInt16LE(16,34);
  wav.write('data',36); wav.writeUInt32LE(32000,40);
  await page.locator('#audioFile').setInputFiles({name:'Sample.wav',mimeType:'audio/wav',buffer:wav});
  await hidden(page,'#importMenu');
  await waitText(page,'#itemViewText','hello');
  record('Document and audio imports, timestamp preference and selected result');

  await page.locator('#inspectorToggle').click();
  await page.screenshot({path:`${output}/settings-desktop.png`});
  await page.locator('#shortcutSettings > summary').click();
  await page.locator('#dictationKeyField').click();
  await page.locator('#dictationKeyField').press('Escape');
  await panelOpen(page,'#inspector');
  assert.equal(await page.locator('#dictationKeyField').getAttribute('aria-pressed'),'false');
  await page.locator('#dictationEnabled').uncheck();
  await waitText(page,'#dictationStatus','Dictation off');
  await page.locator('#inspectorClose').click();
  await page.locator('#importToggle').click();
  assert.equal(await page.locator('#audioFile').isDisabled(),true);
  await waitText(page,'#audioAvailability','Enable dictation');
  await page.locator('#importClose').click();
  await page.locator('#inspectorToggle').click();
  await page.locator('#dictationEnabled').check();
  await page.locator('#inspectorClose').click();
  record('Shortcut capture cancellation and clear disabled-audio condition');

  for(const [name,width,height,scheme] of [
    ['small',320,568,'light'],['mobile',390,844,'light'],['tablet',768,1024,'light'],
    ['laptop',1024,768,'light'],['wide',1920,1080,'light'],['dark',1440,960,'dark'],['short',844,390,'light'],
  ]) {
    const p=await newPage({width,height},scheme);
    await geometry(p);
    await p.screenshot({path:`${output}/draft-${name}.png`});
    if(name==='dark') await audit(p,'dark canvas');
    for(const [trigger,panel,close] of [
      ['libraryToggle','librarySidebar','libraryClose'],['importToggle','importMenu','importClose'],
      ['voiceButton','voiceMenu','voiceClose'],['rateButton','rateMenu','rateClose'],['inspectorToggle','inspector','inspectorClose'],
    ]) {
      await p.locator(`#${trigger}`).click();
      await geometry(p);
      if(['mobile','dark','short'].includes(name)) await p.screenshot({path:`${output}/${panel}-${name}.png`});
      await p.locator(`#${close}`).click();
    }
    await p.locator('#libraryToggle').click();
    await p.locator('.row-item').filter({hasText:'A little room'}).click();
    await waitText(p,'#itemViewText','The first light');
    await geometry(p);
    if(['mobile','dark','short'].includes(name)) await p.screenshot({path:`${output}/reading-${name}.png`});
    await p.context().close();
  }
  assert.deepEqual(faults,[]);
  record('Seven window sizes/themes: centered controls, contained panels, no horizontal overflow or browser errors');
  await writeFile(`${output}/browser-checks.json`,JSON.stringify({passed:true,checks,errors:faults,scope:'Isolated library; simulated playback and transcription. Native microphone/hotkeys and audio quality are outside this browser test.'},null,2)+'\n');
  if(process.env.AXE_SCRIPT) await writeFile(`${output}/accessibility.json`,JSON.stringify(accessibility,null,2)+'\n');
} finally {
  await browser.close();
}
