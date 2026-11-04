"""First-run sequence shared by the two native desktop windows."""

STYLE = r"""
    .shortcut-guide { display:flex; justify-content:center; gap:24px; padding:0 18px 14px; flex-wrap:wrap; }
    .shortcut-guide button { display:flex; align-items:center; gap:10px; font-size:12px; }
    .shortcut-guide kbd { font:inherit; color:var(--muted); }
    #setupWizard { width:min(760px, calc(100vw - 32px)); max-width:760px; max-height:calc(100dvh - 32px); padding:0; overflow:hidden; background:var(--solid); }
    #setupWizard::backdrop { backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); background:rgba(15,25,20,.18); }
    .setup-shell { padding:30px 44px 22px; height:min(740px, calc(100dvh - 34px)); display:flex; flex-direction:column; }
    .setup-top { display:flex; justify-content:space-between; align-items:center; gap:20px; flex-shrink:0; }
    .setup-progress { display:flex; gap:22px; list-style:none; padding:0; margin:0; font-size:12px; color:var(--muted); }
    .setup-progress [aria-current=step] { color:var(--ink); border-bottom:1px solid currentColor; padding-bottom:6px; }
    .setup-step { flex:1; min-height:0; overflow:auto; padding:32px 0 20px; }
    .setup-step[hidden] { display:none; }
    .setup-step h2 { font:400 clamp(34px,5vw,48px)/1.1 Georgia,serif; letter-spacing:-.04em; margin:0 0 14px; }
    .setup-step h2:focus { outline:none; }
    .setup-step p { margin:0 0 24px; color:var(--muted); font-size:14px; line-height:1.6; max-width:52ch; }
    .setup-rows { margin-top:30px; }
    .setup-row { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:15px 0; border-bottom:1px solid var(--line); font-size:14px; }
    .setup-row span:last-child { color:var(--muted); font-size:12px; }
    .setup-row .ready { color:var(--ink); }
    .setup-footer { display:flex; justify-content:space-between; align-items:center; gap:20px; padding-top:12px; flex-shrink:0; }
    .setup-footer #setupNext { font:italic 28px Georgia,serif; padding:12px 4px 12px 28px; margin-left:auto; }
    .setup-status { min-height:20px; font-size:13px; line-height:1.5; color:var(--muted); margin:4px 0; }
    .keyboard-map { display:grid; grid-template-columns:1fr 1.8fr 1fr; gap:10px; margin:28px 0 20px; }
    .keyboard-map kbd { display:flex; flex-direction:column; justify-content:space-between; min-height:86px; padding:14px; border-radius:14px; background:var(--glass); border:1px solid var(--line); font:14px system-ui; }
    .keyboard-map kbd span { color:var(--muted); font-size:11px; padding-top:16px; }
    .keyboard-map .space-key { justify-content:flex-end; text-align:center; color:var(--muted); font-size:12px; }
    .setup-choice { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin:20px 0 4px; }
    .setup-choice label { display:grid; gap:8px; font-size:12px; color:var(--muted); }
    .setup-choice select { appearance:none; cursor:pointer; border:0; border-bottom:1px solid var(--line); border-radius:0; background:transparent; color:var(--ink); padding:12px 0; font:14px system-ui; width:100%; }
    .keyboard-map.custom-keys { grid-template-columns:1fr 1fr; }
    .keyboard-map.custom-keys .space-key { display:none; }
    .setup-device { display:grid; gap:8px; margin-top:20px; font-size:12px; color:var(--muted); }
    .setup-device select { appearance:none; border:0; border-bottom:1px solid var(--line); background:transparent; color:var(--ink); font:14px system-ui; padding:12px 0; width:100%; cursor:pointer; }
    .setup-help { margin-top:8px; max-height:180px; overflow:auto; flex-shrink:0; font-size:13px; color:var(--muted); }
    .setup-help summary { list-style:none; cursor:pointer; display:inline-block; padding:10px 0; }
    .setup-help summary::-webkit-details-marker { display:none; }
    .setup-help > summary::after, .setup-help[open] > summary::after { content:none; }
    .setup-help[open] summary { color:var(--ink); }
    .setup-help p { line-height:1.6; max-width:60ch; margin:8px 0 14px; }
    #setupTrial { width:100%; min-height:100px; resize:vertical; margin:14px 0; padding:16px; border:1px solid var(--line); border-radius:12px; color:var(--ink); background:var(--glass); font:18px/1.5 Georgia,serif; }
    .setup-check { display:flex; align-items:center; gap:12px; font-size:13px; padding:10px 0; cursor:pointer; }
    .setup-check input { width:17px; height:17px; accent-color:var(--ink); }
    .setup-sample { display:flex; align-items:center; justify-content:space-between; gap:15px; }
    .setup-sample p { margin:0; color:var(--ink); }
    @media(max-width:600px) {
      .setup-shell { padding:22px; }
      .setup-progress { gap:12px; font-size:11px; }
      .setup-step { padding-top:32px; }
      .keyboard-map { gap:6px; grid-template-columns:1fr 1.3fr 1fr; }
      .keyboard-map kbd { padding:10px; font-size:12px; }
      .setup-choice { grid-template-columns:1fr; gap:10px; }
      .shortcut-guide { gap:4px 16px; padding-bottom:6px; }
    }
    @media(max-height:660px) { .setup-step { padding-top:22px; } .setup-help { max-height:130px; } }
"""

HTML = r"""
  <div class="shortcut-guide" aria-label="Your shortcuts">
    <button id="dictationGuide" type="button"><span>Dictate</span><kbd id="dictationGuideKey">Left Option / Alt</kbd></button>
    <button id="readingGuide" type="button"><span>Read selection</span><kbd id="readingGuideKey">Right Command / Windows</kbd></button>
  </div>
  <dialog id="setupWizard" aria-labelledby="setupTitle">
    <div class="setup-shell">
      <div class="setup-top">
        <ol class="setup-progress" aria-label="Setup progress">
          <li>Speech</li><li>Access</li><li>Shortcuts</li><li>Try it</li>
        </ol>
        <button id="setupLater" type="button">Set up later</button>
      </div>
      <section class="setup-step" data-step="0">
        <h2 id="setupTitle" tabindex="-1">A voice of your own.</h2>
        <p id="setupModelNote">Preparing speech on this device.</p>
        <div class="setup-rows">
          <div class="setup-row"><span>Reading · Kokoro</span><span id="setupTTS">Preparing…</span></div>
          <div class="setup-row"><span>Dictation · Whisper</span><span id="setupSTT">Preparing…</span></div>
        </div>
        <button id="setupRetry" type="button" hidden>Try again</button>
      </section>
      <section class="setup-step" data-step="1" hidden>
        <h2 tabindex="-1">A little access.</h2>
        <p id="setupAccessIntro">Choose Allow, then enable Read Docs in your system settings.</p>
        <div class="setup-row"><span>Microphone</span><button id="setupMicrophone" type="button">Allow</button></div>
        <div class="setup-row" id="setupAccessibilityRow"><span>Read and paste in other apps</span><a id="setupAccessibility" href="read-docs://permission/accessibility">Allow</a></div>
        <div class="setup-row" id="setupInputRow"><span>Global shortcuts</span><a id="setupInput" href="read-docs://permission/input">Allow</a></div>
        <p id="setupAccessNote" class="setup-status"></p>
        <label class="setup-device">Microphone<select id="setupMicrophoneDevice" aria-label="Choose microphone"></select></label>
      </section>
      <section class="setup-step" data-step="2" hidden>
        <h2 tabindex="-1">Your shortcuts.</h2>
        <p id="setupShortcutNote">Choose a key for each action.</p>
        <div class="keyboard-map" id="setupKeyboardMap" aria-label="Recommended key positions around the spacebar, keyboard layouts vary">
          <kbd id="setupLeftKey">Left Option<span>Dictate</span></kbd>
          <kbd class="space-key">Space</kbd>
          <kbd id="setupRightKey">Right Command<span>Read selection</span></kbd>
        </div>
        <div class="setup-choice">
          <label>Dictation<select id="setupDictation" aria-label="Dictation shortcut"></select></label>
          <label>Read selection<select id="setupSelection" aria-label="Read selection shortcut"></select></label>
        </div>
        <button id="setupRecommended" type="button">Use recommended keys</button>
        <p id="setupKeyboardNote" class="setup-status"></p>
      </section>
      <section class="setup-step" data-step="3" hidden>
        <h2 tabindex="-1">Make it yours.</h2>
        <div class="setup-sample"><p id="setupReadSample">A quiet place for your words.</p><button id="setupListen" type="button">Listen</button></div>
        <label class="setup-check"><input id="setupHeard" type="checkbox">I can hear the voice</label>
        <label class="visually-hidden" for="setupTrial">Try dictation here</label>
        <textarea id="setupTrial" placeholder="Click here, then hold your dictation key and speak." spellcheck="false"></textarea>
        <p id="setupTryNote">Release to insert your words. Then highlight them and tap your reading key.</p>
        <label class="setup-check"><input id="setupTried" type="checkbox">Dictation and reading my selection work</label>
      </section>
      <details id="setupHelp" class="setup-help"><summary>Need help?</summary><p id="setupHelpText"></p></details>
      <p id="setupStatus" class="setup-status" role="status" aria-live="polite"></p>
      <div class="setup-footer"><button id="setupBack" type="button">Back</button><button id="setupNext" type="button">Continue</button></div>
    </div>
  </dialog>
"""

SCRIPT = r"""
    const setup = { step:0, initialized:false, busy:false, audio:null, audioURL:'', heard:false, origin:null, choiceSignature:'', deviceSignature:'', prepareAttempted:false, preparing:false };
    const setupDialog = $('setupWizard');
    function setupSave(values) {
      return api('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(values)});
    }
    function stopSetupAudio() {
      if (setup.audio) setup.audio.pause();
      if (setup.audioURL) URL.revokeObjectURL(setup.audioURL);
      setup.audio = null; setup.audioURL = ''; $('setupListen').textContent = 'Listen';
    }
    function showSetup(step=0) {
      if (!setupDialog.open) {
        setup.origin = document.activeElement;
        setupDialog.showModal();
      }
      setup.step = Math.max(0, Math.min(3, step));
      $('setupStatus').textContent = '';
      $('setupHelp').open = false;
      document.querySelectorAll('.setup-step').forEach((el, i) => {
        el.hidden = i !== setup.step;
        const heading = el.querySelector('h2');
        heading.removeAttribute('id');
        if (!el.hidden) { heading.id = 'setupTitle'; heading.focus(); }
      });
      document.querySelectorAll('.setup-progress li').forEach((el, i) => {
        if (i === setup.step) el.setAttribute('aria-current', 'step');
        else el.removeAttribute('aria-current');
      });
      $('setupBack').hidden = setup.step === 0;
      $('setupNext').textContent = setup.step === 3 ? 'Start reading' : 'Continue';
      renderSetup(state.data || {});
      if (setup.step === 0 && !setup.prepareAttempted && !$('setupRetry').hidden) prepareSetupSpeech();
    }
    async function leaveSetup() {
      if (setup.busy) return;
      try { await setupSave({setup_step:setup.step, ...(setup.step === 2 ? setupChoices() : {})}); }
      catch(error) { $('setupStatus').textContent = error.message; return; }
      stopSetupAudio(); setupDialog.close(); setup.origin?.focus();
    }
    function setupBack() { if (!setup.busy) setup.step > 0 ? showSetup(setup.step - 1) : leaveSetup(); }
    $('setupBack').addEventListener('click', setupBack);
    $('setupLater').addEventListener('click', leaveSetup);
    setupDialog.addEventListener('cancel', (event) => { event.preventDefault(); setupBack(); });
    setupDialog.addEventListener('keydown', event => {
      const {key:pressed} = event;
      if (pressed !== 'Tab') return;
      const controls = Array.from(setupDialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea, a[href], summary')).filter(el => el.getClientRects().length);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement.id === 'setupTitle')) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    $('dictationGuide').addEventListener('click', () => showSetup(2));
    $('readingGuide').addEventListener('click', () => showSetup(2));
    $('setupReopen').addEventListener('click', () => { setInspectorOpen(false); showSetup(0); });

    function setupPermissions(data) {
      const mic = data.stt?.microphone || {};
      const windows = (window.readDocsDesktop || data.stt?.hotkeys?.platform) === 'windows';
      return mic.native_helper_online && mic.authorization === 'authorized' &&
        (windows || (mic.accessibility_trusted && mic.input_monitoring_trusted));
    }
    function setupChoices() {
      return {dictation_key:$('setupDictation').value, selection_shortcut:$('setupSelection').value};
    }
    function renderSetupKeys() {
      const dictation = $('setupDictation'), reading = $('setupSelection');
      const dictateLabel = dictation.selectedOptions[0]?.textContent || 'your dictation key';
      const readLabel = reading.selectedOptions[0]?.textContent || 'your reading shortcut';
      const recommended = dictation.value === 'alt_l' && reading.value === 'cmd_r';
      const readAction = reading.value === 'cmd_r' ? 'Tap' : 'Press';
      $('setupLeftKey').firstChild.textContent = dictateLabel;
      $('setupRightKey').firstChild.textContent = readLabel;
      $('setupKeyboardMap').classList.toggle('custom-keys', !recommended);
      $('setupRecommended').hidden = recommended;
      $('setupKeyboardMap').setAttribute('aria-label', recommended ? 'Recommended keys around the spacebar; keyboard layouts vary' : 'Your chosen shortcuts');
      $('setupShortcutNote').textContent = `Hold ${dictateLabel} to dictate. ${readAction} ${readLabel} to read highlighted text.`;
      $('setupTrial').placeholder = `Click here, then hold ${dictateLabel} and speak.`;
      $('setupTryNote').textContent = `Release to insert your words. Highlight them, then ${readAction.toLowerCase()} ${readLabel}.`;
    }
    function renderSetup(data) {
      const hotkeys = data.stt?.hotkeys || {};
      const mic = data.stt?.microphone || {};
      const windows = (window.readDocsDesktop || hotkeys.platform) === 'windows';
      $('dictationGuideKey').textContent = hotkeys.dictation_label || 'Left Option / Alt';
      $('readingGuideKey').textContent = hotkeys.selection_label || 'Right Command / Windows';
      const engine = data.tts?.services?.mac || {};
      const kokoro = engine.engines?.kokoro || {};
      const whisper = engine.engines?.whisper || {};
      const ready = kokoro.loaded && whisper.loaded;
      $('setupModelNote').textContent = engine.bundled_models ? 'Everything is included. Your words stay on this device.' : 'Preparing local speech. Source installs download models on first use.';
      $('setupTTS').textContent = kokoro.loaded ? 'Ready' : kokoro.error ? 'Needs attention' : 'Preparing…';
      $('setupSTT').textContent = whisper.loaded ? 'Ready' : whisper.error ? 'Needs attention' : 'Preparing…';
      $('setupRetry').hidden = ready;
      $('setupAccessibilityRow').hidden = windows;
      $('setupInputRow').hidden = windows;
      $('setupMicrophone').textContent = mic.authorization === 'authorized' ? 'Allowed' : 'Allow';
      $('setupAccessibility').textContent = mic.accessibility_trusted ? 'Allowed' : 'Allow';
      $('setupInput').textContent = mic.input_monitoring_trusted ? 'Allowed' : 'Allow';
      $('setupAccessIntro').textContent = windows ? 'Choose Allow to enable dictation and check Windows microphone access.' : 'Choose Allow, then enable Read Docs in your system settings.';
      $('setupAccessNote').textContent = !window.readDocsDesktop ? 'Open the installed Read Docs app to grant access.' :
        !mic.native_helper_online ? 'Waiting for the desktop helper…' : mic.authorization === 'denied' ? 'Enable microphone access in system settings, then return here.' :
        windows ? 'Windows must allow desktop apps to use your microphone.' : 'If macOS asks you to quit and reopen, open Read Docs again to resume setup.';
      $('setupKeyboardNote').textContent = windows ? 'No right Windows key? Choose Ctrl + Alt + R. Key positions vary by keyboard.' : 'Recommended keys sit on either side of the spacebar. Your saved choices are kept.';
      $('setupKeyboardNote').hidden = !windows;
      $('setupHelpText').textContent = [
        'First launch can take a minute. If speech stays on Preparing or shows Needs attention, choose Try again. If it still cannot start, quit and reopen Read Docs. The desktop download already includes the speech models.',
        windows ? 'In Windows Settings, turn on Microphone access and Let desktop apps access your microphone. Return here and choose the microphone you want to use. If no input is available, connect a microphone and try again.' : 'In System Settings, open Privacy & Security. Enable Read Docs under Microphone, Accessibility and Input Monitoring. If it is missing from Accessibility, use the add control and choose the installed app from Applications. If macOS asks you to quit, reopen Read Docs to resume here.',
        'Choose a preset from each list. Use recommended keys restores the defaults. You can change these later in Settings, including supported custom keys and combinations. If a shortcut is already used by another app, choose a different one.',
        `Listen first and check your output volume. Click the text area before dictating. If it stays empty, use Back to check your microphone and permissions. If reading does not start, wait for dictation to finish and select the text again.${windows ? '' : ' On Mac, a quick tap can also start dictation; tap the same key again to stop.'}`
      ][setup.step];
      const deviceSignature = JSON.stringify([mic.devices, mic.selected_id]);
      if (setup.deviceSignature !== deviceSignature && !$('setupMicrophoneDevice').disabled) {
        setup.deviceSignature = deviceSignature;
        const select = $('setupMicrophoneDevice'); select.replaceChildren();
        for (const device of mic.devices || [{id:'', name:'System Default'}]) select.add(new Option(device.name, device.id));
        select.value = mic.selected_id || '';
      }
      const signature = JSON.stringify([hotkeys.dictation_options, hotkeys.selection_options, hotkeys.dictation_key, hotkeys.selection_shortcut]);
      if (setup.choiceSignature !== signature && !setup.busy) {
        setup.choiceSignature = signature;
        for (const [id, options, value] of [['setupDictation',hotkeys.dictation_options,hotkeys.dictation_key], ['setupSelection',hotkeys.selection_options,hotkeys.selection_shortcut]]) {
          const select = $(id); select.replaceChildren();
          for (const item of options || []) select.add(new Option(item.label, item.value));
          if (value && !Array.from(select.options).some(option => option.value === value)) select.add(new Option(id === 'setupDictation' ? hotkeys.dictation_label || value : hotkeys.selection_label || value, value));
          select.value = value || '';
        }
      }
      renderSetupKeys();
      $('setupNext').disabled = setup.busy || (setup.step === 0 && !ready) ||
        (setup.step === 1 && !setupPermissions(data)) ||
        (setup.step === 3 && (!setup.heard || !$('setupHeard').checked || !$('setupTried').checked));
      $('setupHeard').disabled = !setup.heard;
      if (setup.step === 0 && (kokoro.error || whisper.error)) $('setupStatus').textContent = 'Speech needs attention. Choose Try again, or open Need help.';
      else if (setup.step === 0 && ready && $('setupStatus').textContent === 'Preparing speech…') $('setupStatus').textContent = '';
      if (!setup.initialized && data.settings) {
        setup.initialized = true;
        if (window.readDocsDesktop && !data.settings.setup_completed) showSetup(data.settings.setup_step || 0);
      }
    }
    $('setupMicrophone').addEventListener('click', async () => {
      if (!window.readDocsDesktop) { $('setupStatus').textContent = 'Open the installed Read Docs app to grant access.'; return; }
      try {
        render(await setupSave({stt_enabled:true}));
        location.href = 'read-docs://permission/microphone';
      } catch(error) { $('setupStatus').textContent = error.message; }
    });
    for (const id of ['setupAccessibility','setupInput']) $(id).addEventListener('click', event => {
      if (!window.readDocsDesktop) { event.preventDefault(); $('setupStatus').textContent = 'Open the installed Read Docs app to grant access.'; }
    });
    $('setupRecommended').addEventListener('click', () => {
      $('setupDictation').value = 'alt_l'; $('setupSelection').value = 'cmd_r';
      renderSetupKeys();
    });
    for (const id of ['setupDictation','setupSelection']) $(id).addEventListener('change', renderSetupKeys);
    $('setupMicrophoneDevice').addEventListener('change', async () => {
      const select = $('setupMicrophoneDevice'); select.disabled = true;
      try { const data = await setupSave({microphone_id:select.value}); select.disabled = false; render(data); }
      catch(error) { $('setupStatus').textContent = error.message; }
      finally { select.disabled = false; }
    });
    $('setupNext').addEventListener('click', async () => {
      if ($('setupNext').disabled) return;
      setup.busy = true; $('setupNext').disabled = true; $('setupStatus').textContent = '';
      try {
        const values = {setup_step:Math.min(setup.step + 1, 3)};
        if (setup.step === 2) Object.assign(values, setupChoices(), {stt_enabled:true});
        if (setup.step === 3) values.setup_completed = true;
        const data = await setupSave(values);
        if (setup.step === 3) { stopSetupAudio(); setupDialog.close(); setup.origin?.focus(); }
        else showSetup(setup.step + 1);
        render(data);
      } catch(error) { $('setupStatus').textContent = error.message; }
      finally { setup.busy = false; renderSetup(state.data || {}); }
    });
    async function prepareSetupSpeech() {
      if (setup.preparing) return;
      setup.prepareAttempted = true; setup.preparing = true;
      $('setupRetry').disabled = true; $('setupStatus').textContent = 'Preparing speech…';
      try { await api('/api/setup/prepare', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}); await refresh(); }
      catch(error) { $('setupStatus').textContent = 'Speech could not start. Choose Try again, or quit and reopen Read Docs.'; }
      finally { setup.preparing = false; $('setupRetry').disabled = false; }
    }
    $('setupRetry').addEventListener('click', prepareSetupSpeech);
    $('setupListen').addEventListener('click', async () => {
      if (setup.audio) { stopSetupAudio(); return; }
      $('setupListen').disabled = true;
      try {
        const response = await fetch(`/api/voices/preview?voice=${encodeURIComponent(state.data?.tts?.kokoro_voice || 'af_heart')}`);
        if (!response.ok) throw new Error('The voice sample could not load. Return to Speech and try again.');
        setup.audioURL = URL.createObjectURL(await response.blob());
        setup.audio = new Audio(setup.audioURL);
        setup.audio.addEventListener('ended', stopSetupAudio);
        await setup.audio.play();
        setup.heard = true; $('setupListen').textContent = 'Stop'; renderSetup(state.data || {});
      } catch(error) { stopSetupAudio(); $('setupStatus').textContent = error.message; }
      finally { $('setupListen').disabled = false; }
    });
    for (const id of ['setupHeard','setupTried']) $(id).addEventListener('change', () => renderSetup(state.data || {}));
"""
