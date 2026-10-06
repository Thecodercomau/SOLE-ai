(function () {
  'use strict';

  const generateBtn = document.getElementById('generateBtn');
  const formError   = document.getElementById('formError');
  const emptyState  = document.getElementById('emptyState');
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

  // ── Generate button — UI only, no AI yet ────────────────────────
  generateBtn && generateBtn.addEventListener('click', () => {
    const style    = document.getElementById('style').value;
    const material = document.getElementById('material').value;
    const primary  = document.getElementById('primary_color').value;
    const accent   = document.getElementById('accent_color').value;

    // Show a mock result to confirm the UI is working
    emptyState && emptyState.classList.add('hidden');
    if (result) {
      result.classList.remove('hidden');
      document.getElementById('resultName').textContent    = 'UI Interface Ready';
      document.getElementById('resultTagline').textContent = `${style} · ${material} · ${primary} / ${accent}`;
      document.getElementById('resultDesc').textContent    = 'Lesson 1 complete. The interface is structured and all inputs are wired up. Proceed to Lesson 2 to connect the AI.';
      document.getElementById('resultPrice').textContent   = 'Lesson 1';
      document.getElementById('resultAudience').textContent = 'Interface only';
    }
    formError.textContent = '';
  });

})();