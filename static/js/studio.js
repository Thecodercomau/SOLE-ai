(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const generateBtn = $('generateBtn'), regenBtn = $('regenBtn'), regenImgBtn = $('regenImgBtn');
  const formError = $('formError'), emptyState = $('emptyState'), loadingState = $('loadingState');
  const loaderText = $('loaderText'), stageGroq = $('stageGroq'), stageHF = $('stageHF'), result = $('result');
  const resultName = $('resultName'), resultTagline = $('resultTagline'), resultTags = $('resultTags');
  const resultPrice = $('resultPrice'), resultAudience = $('resultAudience'), resultDesc = $('resultDesc');
  const materialsList = $('materialsList'), featuresList = $('featuresList'), soleText = $('soleText');
  const colorwayTabs = $('colorwayTabs'), colorwayInfo = $('colorwayInfo'), sneakerStage = $('sneakerStage');
  const imgLoading = $('imgLoading'), imgFrame = $('imgFrame'), aiImage = $('aiImage');
  const imgError = $('imgError'), imgErrorText = $('imgErrorText');
  const captchaModal = $('captchaModal'), captchaCancel = $('captchaCancel');

  const LOADER_MSGS = ['Querying AI…','Designing silhouette…','Choosing materials…','Mixing colorways…','Finalizing specs…'];
  let loaderInterval = null, currentColorways = [], currentConcept = null, captchaWidgetId = null;

  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

  // ── hCaptcha ──────────────────────────────────────────────────────
  window.hcaptchaReady = () => {
    captchaWidgetId = hcaptcha.render('hcaptchaWidget', {
      sitekey: window.HCAPTCHA_SITE_KEY, theme: 'dark', size: 'compact',
      callback: token => { captchaModal.classList.add('hidden'); runGeneration(token); },
      'expired-callback': () => { captchaModal.classList.add('hidden'); generateBtn.disabled = false; formError.textContent = 'CAPTCHA expired.'; },
    });
  };

  generateBtn?.addEventListener('click', () => {
    formError.textContent = '';
    if (typeof hcaptcha === 'undefined' || captchaWidgetId === null) { formError.textContent = 'CAPTCHA not loaded. Refresh.'; return; }
    hcaptcha.reset(captchaWidgetId);
    captchaModal.classList.remove('hidden');
  });
  captchaCancel?.addEventListener('click', () => { captchaModal.classList.add('hidden'); hcaptcha?.reset(captchaWidgetId); });

  // ── Chips & colors ────────────────────────────────────────────────
  document.querySelectorAll('.chip-group').forEach(g => {
    const inp = $(g.dataset.field);
    g.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
      g.querySelectorAll('.chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      if (inp) inp.value = c.dataset.value;
    }));
  });

  const syncColor = (pid, tid) => {
    const p = $(pid), t = $(tid);
    if (!p || !t) return;
    p.addEventListener('input', () => t.value = p.value);
    t.addEventListener('input', () => { if (/^#[0-9A-Fa-f]{6}$/.test(t.value)) p.value = t.value; });
  };
  syncColor('primary_color','primary_color_text');
  syncColor('accent_color','accent_color_text');

  const collectPrefs = () => ({
    style: $('style').value, material: $('material').value, occasion: $('occasion').value,
    primary_color: $('primary_color').value, accent_color: $('accent_color').value,
    inspiration: $('inspiration').value.trim(),
  });

  // ── Loader ────────────────────────────────────────────────────────
  const startLoader = () => { let i=0; loaderText.textContent=LOADER_MSGS[0]; loaderInterval=setInterval(()=>{ i=(i+1)%LOADER_MSGS.length; loaderText.textContent=LOADER_MSGS[i]; },1400); };
  const stopLoader  = () => { clearInterval(loaderInterval); loaderInterval=null; };

  const setUI = s => {
    [emptyState,loadingState,result].forEach(el=>el.classList.add('hidden'));
    ({empty:emptyState,loading:loadingState,result}[s])?.classList.remove('hidden');
  };
  const setStage = a => {
    stageGroq?.classList.toggle('stage-pill--active', a==='groq');
    stageHF?.classList.toggle('stage-pill--active', a==='hf');
    stageGroq?.classList.toggle('stage-pill--done', a==='hf');
  };

  // ── Image helpers ─────────────────────────────────────────────────
  const showImgLoading = () => { imgLoading?.classList.remove('hidden'); imgFrame?.classList.add('hidden'); imgError?.classList.add('hidden'); regenImgBtn?.classList.add('hidden'); };
  const showImgResult  = url => { imgLoading?.classList.add('hidden'); imgError?.classList.add('hidden'); if(aiImage) aiImage.src=url; imgFrame?.classList.remove('hidden'); regenImgBtn?.classList.remove('hidden'); };
  const showImgError   = msg => { imgLoading?.classList.add('hidden'); imgFrame?.classList.add('hidden'); if(imgErrorText) imgErrorText.textContent=msg||'Image generation failed.'; imgError?.classList.remove('hidden'); regenImgBtn?.classList.remove('hidden'); };

  // ── Colorway SVG ──────────────────────────────────────────────────
  const applyColorway = (cw, el) => {
    const svg = el.querySelector('.sneaker-svg') || el;
    [['--upper-color',cw.upper],['--panel-color',cw.sole],['--toe-color',cw.upper],
     ['--accent-color',cw.accent],['--lace-color',cw.lace],['--midsole-color',cw.tongue]
    ].forEach(([p,v]) => svg.style.setProperty(p, v||''));
  };

  const selectColorway = idx => {
    colorwayTabs.querySelectorAll('.cw-tab').forEach((t,i) => t.classList.toggle('active',i===idx));
    applyColorway(currentColorways[idx], sneakerStage);
    colorwayInfo.innerHTML = [['Upper',currentColorways[idx].upper],['Sole',currentColorways[idx].sole],
      ['Accent',currentColorways[idx].accent],['Lace',currentColorways[idx].lace],['Tongue',currentColorways[idx].tongue]]
      .map(([l,c])=>`<div class="cw-color-item"><div class="cw-dot" style="background:${c}"></div>${l}: <strong style="color:var(--text)">${c}</strong></div>`).join('');
  };

  const buildColorwayTabs = cws => {
    colorwayTabs.innerHTML = '';
    cws.forEach((cw,i) => {
      const btn = document.createElement('button');
      btn.className = 'cw-tab' + (i===0?' active':'');
      btn.innerHTML = `<span class="cw-swatch" style="background:${cw.upper}"></span><span class="cw-swatch" style="background:${cw.accent}"></span>${esc(cw.name)}`;
      btn.addEventListener('click', () => selectColorway(i));
      colorwayTabs.appendChild(btn);
    });
  };

  // ── Render concept ────────────────────────────────────────────────
  const renderConcept = c => {
    currentConcept = c;
    resultName.textContent = c.name||''; resultTagline.textContent = c.tagline||'';
    resultPrice.textContent = c.retail_price||''; resultAudience.textContent = c.target_audience||'';
    resultDesc.textContent = c.description||''; resultTags.textContent = (c.style_tags||[]).join(' · ');
    materialsList.innerHTML = (c.materials||[]).map(m=>`<li>${esc(m)}</li>`).join('');
    featuresList.innerHTML  = (c.features||[]).map(f=>`<li>${esc(f)}</li>`).join('');
    soleText.textContent = c.sole_type||'—';
    currentColorways = c.colorways||[];
    if (currentColorways.length) { buildColorwayTabs(currentColorways); selectColorway(0); }
  };

  // ── Image fetch ───────────────────────────────────────────────────
  const fetchImage = async prompt => {
    setStage('hf'); showImgLoading();
    try {
      const r = await fetch('/generate-image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image_prompt:prompt})});
      const d = await r.json();
      if (!r.ok||d.error) throw new Error(d.error||'Image generation failed');
      showImgResult(d.image_url);
    } catch(e) { showImgError(e.message); }
  };

  // ── Main flow ─────────────────────────────────────────────────────
  const runGeneration = async token => {
    const prefs = collectPrefs();
    generateBtn.disabled = true;
    setUI('loading'); setStage('groq'); startLoader();
    try {
      const r = await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...prefs,'h-captcha-response':token})});
      const d = await r.json();
      if (!r.ok||d.error) throw new Error(d.error||'Server error');
      stopLoader(); renderConcept(d.concept); setUI('result');
      fetchImage(d.concept.image_prompt || `Premium ${prefs.style} sneaker, ${prefs.material}, studio photography, 8k`);
    } catch(e) {
      stopLoader(); setUI('empty'); formError.textContent = e.message||'Something went wrong.';
    } finally {
      generateBtn.disabled = false;
      if (typeof hcaptcha!=='undefined' && captchaWidgetId!==null) hcaptcha.reset(captchaWidgetId);
    }
  };

  regenImgBtn?.addEventListener('click', () => currentConcept && fetchImage(currentConcept.image_prompt||`Premium sneaker, ${currentConcept.name||'sneaker'}, studio, 8k`));
  regenBtn?.addEventListener('click', () => { formError.textContent=''; setUI('empty'); currentConcept=null; document.querySelector('.form-panel')?.scrollIntoView({behavior:'smooth'}); });

})();
