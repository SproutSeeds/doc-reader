"""First-run sequence shared by the two native desktop windows."""

STYLE = r"""
    .shortcut-guide { display:flex; justify-content:center; gap:24px; padding:0 18px 14px; flex-wrap:wrap; }
    .shortcut-guide button { display:flex; align-items:center; gap:10px; font-size:12px; }
    .shortcut-guide kbd { font:inherit; color:var(--muted); }
    #setupWizard { width:min(760px, calc(100vw - 32px)); max-width:760px; max-height:calc(100dvh - 32px); padding:0; overflow:auto; background:var(--solid); }
    #setupWizard::backdrop { backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); background:rgba(15,25,20,.18); }
    .setup-shell { padding:30px 44px 22px; min-height:550px; display:flex; flex-direction:column; }
    .setup-top { display:flex; justify-content:space-between; align-items:center; gap:20px; }
    .setup-progress { display:flex; gap:22px; list-style:none; padding:0; margin:0; font-size:12px; color:var(--muted); }
    .setup-progress [aria-current=step] { color:var(--ink); border-bottom:1px solid currentColor; padding-bottom:6px; }
    .setup-step { flex:1; padding:42px 0 26px; }
    .setup-step[hidden] { display:none; }
    .setup-step h2 { font:400 clamp(34px,5vw,48px)/1.1 Georgia,serif; letter-spacing:-.04em; margin:0 0 14px; }
    .setup-step h2:focus { outline:none; }
    .setup-step p { margin:0 0 24px; color:var(--muted); font-size:14px; line-height:1.6; max-width:52ch; }
    .setup-rows { margin-top:30px; }
    .setup-row { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:15px 0; border-bottom:1px solid var(--line); font-size:14px; }
    .setup-row span:last-child { color:var(--muted); font-size:12px; }
    .setup-row .ready { color:var(--ink); }
    .setup-footer { display:flex; justify-content:space-between; align-items:center; gap:20px; padding-top:12px; }
    .setup-footer #setupNext { font:italic 28px Georgia,serif; padding:12px 4px 12px 28px; margin-left:auto; }
    .setup-status { min-height:20px; font-size:13px; line-height:1.5; color:var(--muted); margin:4px 0; }
    .keyboard-map { display:grid; grid-template-columns:1fr 1.8fr 1fr; gap:10px; margin:28px 0 20px; }
    .keyboard-map kbd { display:flex; flex-direction:column; justify-content:space-between; min-height:86px; padding:14px; border-radius:14px; background:var(--glass); border:1px solid var(--line); font:14px system-ui; }
    .keyboard-map kbd span { color:var(--muted); font-size:11px; padding-top:16px; }
    .keyboard-map .space-key { justify-content:flex-end; text-align:center; color:var(--muted); font-size:12px; }
    .setup-choice { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin:20px 0 4px; }
    .setup-choice label { display:grid; gap:8px; font-size:12px; color:var(--muted); }
    .setup-choice select { appearance:none; cursor:pointer; border:0; border-bottom:1px solid var(--line); border-radius:0; background:transparent; color:var(--ink); padding:12px 0; font:14px system-ui; width:100%; }
    #setupTrial { width:100%; min-height:100px; resize:vertical; margin:14px 0; padding:16px; border:1px solid var(--line); border-radius:12px; color:var(--ink); background:var(--glass); font:18px/1.5 Georgia,serif; }
    .setup-check { display:flex; align-items:center; gap:12px; font-size:13px; padding:10px 0; cursor:pointer; }
    .setup-check input { width:17px; height:17px; accent-color:var(--ink); }
    .setup-sample { display:flex; align-items:center; justify-content:space-between; gap:15px; }
    .setup-sample p { margin:0; color:var(--ink); }
    @media(max-width:600px) {
      .setup-shell { padding:22px; min-height:480px; }
      .setup-progress { gap:12px; font-size:11px; }
      .setup-step { padding-top:32px; }
      .keyboard-map { gap:6px; grid-template-columns:1fr 1.3fr 1fr; }
      .keyboard-map kbd { padding:10px; font-size:12px; }
      .setup-choice { grid-template-columns:1fr; gap:10px; }
      .shortcut-guide { gap:4px 16px; padding-bottom:6px; }
    }
    @media(max-height:660px) { .setup-shell { min-height:0; } .setup-step { padding-top:22px; } }
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
        <p>Choose Allow, then enable Read Docs in your system settings.</p>
        <div class="setup-row"><span>Microphone</span><button id="setupMicrophone" type="button">Allow</button></div>
        <div class="setup-row" id="setupAccessibilityRow"><span>Read and paste in other apps</span><a id="setupAccessibility" href="read-docs://permission/accessibility">Allow</a></div>
        <div class="setup-row" id="setupInputRow"><span>Global shortcuts</span><a id="setupInput" href="read-docs://permission/input">Allow</a></div>
        <p id="setupAccessNote" class="setup-status"></p>
      </section>
      <section class="setup-step" data-step="2" hidden>
        <h2 tabindex="-1">Two keys. That's it.</h2>
        <p>Hold the left key to dictate. Tap the right key to read highlighted text.</p>
        <div class="keyboard-map" aria-label="Recommended key positions around the spacebar, keyboard layouts vary">
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
      <p id="setupStatus" class="setup-status" role="status" aria-live="polite"></p>
      <div class="setup-footer"><button id="setupBack" type="button">Back</button><button id="setupNext" type="button">Continue</button></div>
    </div>
  </dialog>
"""

SCRIPT = r"""
    const setup = { step:0, initialized:false, busy:false, audio:null, audioURL:'', heard:false, origin:null, choiceSignature:'' };
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
    }
    async function leaveSetup() {
      if (setup.busy) return;
      try { await setupSave({setup_step:setup.step}); }
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
      const controls = Array.from(setupDialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select, textarea, a[href]')).filter(el => el.getClientRects().length);
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
      $('setupAccessNote').textContent = !window.readDocsDesktop ? 'Open the installed Read Docs app to grant access.' :
        !mic.native_helper_online ? 'Waiting for the desktop helper…' : mic.authorization === 'denied' ? 'Enable microphone access in system settings, then return here.' :
        windows ? 'Windows must allow desktop apps to use your microphone.' : 'If macOS asks you to quit and reopen, open Read Docs again to resume setup.';
      $('setupLeftKey').firstChild.textContent = windows ? 'Left Alt' : 'Left Option';
      $('setupRightKey').firstChild.textContent = windows ? 'Right Windows' : 'Right Command';
      $('setupKeyboardNote').textContent = windows ? 'No right Windows key? Choose Ctrl + Alt + R. Key positions vary by keyboard.' : 'Recommended keys sit on either side of the spacebar. Your saved choices are kept.';
      const signature = JSON.stringify([hotkeys.dictation_options, hotkeys.selection_options, hotkeys.dictation_key, hotkeys.selection_shortcut]);
      if (setup.choiceSignature !== signature && !setup.busy) {
        setup.choiceSignature = signature;
        for (const [id, options, value] of [['setupDictation',hotkeys.dictation_options,hotkeys.dictation_key], ['setupSelection',hotkeys.selection_options,hotkeys.selection_shortcut]]) {
          const select = $(id); select.replaceChildren();
          for (const item of options || []) select.add(new Option(item.label, item.value));
          if (value && !Array.from(select.options).some(option => option.value === value)) select.add(new Option(value, value));
          select.value = value || '';
        }
      }
      $('setupNext').disabled = setup.busy || (setup.step === 0 && !ready) ||
        (setup.step === 1 && !setupPermissions(data)) ||
        (setup.step === 3 && (!setup.heard || !$('setupHeard').checked || !$('setupTried').checked));
      $('setupHeard').disabled = !setup.heard;
      if (setup.step === 0 && (kokoro.error || whisper.error)) $('setupStatus').textContent = kokoro.error || whisper.error;
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
    });
    $('setupNext').addEventListener('click', async () => {
      if ($('setupNext').disabled) return;
      setup.busy = true; $('setupNext').disabled = true; $('setupStatus').textContent = '';
      try {
        const values = {setup_step:Math.min(setup.step + 1, 3)};
        if (setup.step === 2) Object.assign(values, {dictation_key:$('setupDictation').value, selection_shortcut:$('setupSelection').value, stt_enabled:true});
        if (setup.step === 3) values.setup_completed = true;
        const data = await setupSave(values);
        if (setup.step === 3) { stopSetupAudio(); setupDialog.close(); setup.origin?.focus(); }
        else showSetup(setup.step + 1);
        render(data);
      } catch(error) { $('setupStatus').textContent = error.message; }
      finally { setup.busy = false; renderSetup(state.data || {}); }
    });
    $('setupRetry').addEventListener('click', async () => {
      $('setupRetry').disabled = true; $('setupStatus').textContent = 'Preparing speech…';
      try { await api('/api/setup/prepare', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}); await refresh(); }
      catch(error) { $('setupStatus').textContent = error.message; }
      finally { $('setupRetry').disabled = false; }
    });
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
