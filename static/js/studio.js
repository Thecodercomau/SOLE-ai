/* Generate sneaker concepts after hCaptcha verification. */

(function () {
  'use strict';

  const generateBtn = document.getElementById('generateBtn');
  const formError   = document.getElementById('formError');
  const emptyState  = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const result      = document.getElementById('result');

  // ── Chip selection ──────────────────────────────────────────────
  document.querySelectorAll('.chip-group').forEach(group => {
    const hiddenInput = document.getElementById(group.dataset.field);
    group.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        if (hiddenInput) hiddenInput.value = chip.dataset.value;
      });
    });
  });

  // ── Color pickers ───────────────────────────────────────────────
  function syncColorPair(pickerId, textId) {
    const picker = document.getElementById(pickerId);
    const text   = document.getElementById(textId);
    if (!picker || !text) return;
    picker.addEventListener('input', () => { text.value = picker.value; });
    text.addEventListener('input', () => {
      if (/^#[0-9A-Fa-f]{6}$/.test(text.value)) picker.value = text.value;
    });
  }
  syncColorPair('primary_color', 'primary_color_text');
  syncColorPair('accent_color',  'accent_color_text');

  function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  const captchaModal = document.getElementById('captchaModal');
  const captchaCancel = document.getElementById('captchaCancel');
  let captchaWidgetId = null;
  let captchaApiReady = false;

  function collectPrefs() {
    return {
      style:         document.getElementById('style').value,
      material:      document.getElementById('material').value,
      occasion:      document.getElementById('occasion').value,
      primary_color: document.getElementById('primary_color').value,
      accent_color:  document.getElementById('accent_color').value,
      inspiration:   document.getElementById('inspiration').value.trim(),
    };
  }

  async function runGeneration(token) {
    const prefs = collectPrefs();
    generateBtn.disabled = true;
    emptyState  && emptyState.classList.add('hidden');
    result      && result.classList.add('hidden');
    loadingState && loadingState.classList.remove('hidden');

    try {
      const resp = await fetch('/generate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ...prefs, 'h-captcha-response': token }),
      });
      const data = await resp.json();

      loadingState && loadingState.classList.add('hidden');

      if (!resp.ok || data.error) {
        emptyState && emptyState.classList.remove('hidden');
        formError.textContent = data.error || 'Concept generation failed.';
      } else {
        const c = data.concept;
        result && result.classList.remove('hidden');
        document.getElementById('resultName').textContent     = c.name || '';
        document.getElementById('resultTagline').textContent  = c.tagline || '';
        document.getElementById('resultDesc').textContent     = c.description || '';
        document.getElementById('resultPrice').textContent    = c.retail_price || '';
        document.getElementById('resultAudience').textContent = c.target_audience || '';
        document.getElementById('resultTags').textContent     = (c.style_tags || []).join(' · ');
        document.getElementById('materialsList').innerHTML    = (c.materials || []).map(m => `<li>${escHtml(m)}</li>`).join('');
        document.getElementById('featuresList').innerHTML     = (c.features  || []).map(f => `<li>${escHtml(f)}</li>`).join('');
        document.getElementById('soleText').textContent       = c.sole_type || '—';
      }
    } catch (err) {
      loadingState && loadingState.classList.add('hidden');
      emptyState   && emptyState.classList.remove('hidden');
      formError.textContent = 'Network error: ' + err.message;
    } finally {
      generateBtn.disabled = false;
      if (typeof hcaptcha !== 'undefined' && captchaWidgetId !== null) {
        hcaptcha.reset(captchaWidgetId);
      }
    }
  }

  document.getElementById('regenBtn') && document.getElementById('regenBtn').addEventListener('click', () => {
    result     && result.classList.add('hidden');
    emptyState && emptyState.classList.remove('hidden');
    formError.textContent = '';
  });

  function renderCaptcha() {
    captchaWidgetId = hcaptcha.render('hcaptchaWidget', {
      sitekey: window.HCAPTCHA_SITE_KEY,
      theme: 'dark',
      size: 'compact',
      callback: token => {
        captchaModal.classList.add('hidden');
        runGeneration(token);
      },
      'expired-callback': () => {
        captchaModal.classList.add('hidden');
        generateBtn.disabled = false;
        formError.textContent = 'CAPTCHA expired. Please try again.';
      },
      'error-callback': () => {
        captchaModal.classList.add('hidden');
        generateBtn.disabled = false;
        formError.textContent = 'CAPTCHA could not be verified. Please try again.';
      },
    });
  }

  window.hcaptchaReady = () => {
    captchaApiReady = true;
    if (!window.HCAPTCHA_SITE_KEY) {
      formError.textContent = 'CAPTCHA is not configured. Please contact the site owner.';
    }
  };

  generateBtn && generateBtn.addEventListener('click', () => {
    formError.textContent = '';
    if (!window.HCAPTCHA_SITE_KEY) {
      formError.textContent = 'CAPTCHA is not configured. Please contact the site owner.';
      return;
    }
    if (!captchaApiReady || typeof hcaptcha === 'undefined') {
      formError.textContent = 'CAPTCHA is still loading. Please try again in a moment.';
      return;
    }
    generateBtn.disabled = true;
    captchaModal.classList.remove('hidden');
    if (captchaWidgetId === null) {
      window.requestAnimationFrame(() => {
        if (!captchaModal.classList.contains('hidden')) renderCaptcha();
      });
    } else {
      hcaptcha.reset(captchaWidgetId);
    }
  });

  captchaCancel && captchaCancel.addEventListener('click', () => {
    captchaModal.classList.add('hidden');
    generateBtn.disabled = false;
    if (typeof hcaptcha !== 'undefined' && captchaWidgetId !== null) {
      hcaptcha.reset(captchaWidgetId);
    }
  });

  document.getElementById('hcaptchaApi')?.addEventListener('error', () => {
    formError.textContent = 'CAPTCHA failed to load. Check your connection and try again.';
  });

})();
