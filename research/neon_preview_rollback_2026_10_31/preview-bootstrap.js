/* Preview-only routing and labels. The production frontend is untouched. */
(() => {
  const requested = new URL(location.href).searchParams.get('preview_source');
  const source = requested || window.PREVIEW_DEFAULT_SOURCE;
  if (!['legacy', 'neon'].includes(source)) throw new Error('Invalid preview source');
  window.PREVIEW_CONFIG = Object.freeze({source, dataBase: `./data/${source}/`});
  const notice = document.getElementById('researchNotice');
  notice.style.cssText = 'padding:16px 24px;border:2px solid #e5ad39;background:#31250f;color:#fff;font:15px/1.6 system-ui;position:relative;z-index:40';
  notice.innerHTML = `<strong>${source === 'neon' ? 'RESEARCH / NEON CANDIDATE' : 'RESEARCH / LEGACY ROLLBACK'}</strong> · <b>${source === 'neon' ? 'DST SIMULATION' : 'DST SIMULATION OFF (legacy)'}</b><br>Frozen input cutoff: <time>2026-10-30T15:27:55.138400Z</time>. Frozen snapshot; no continuous Neon freshness proof.<br><label>Preview source <select id="previewSource"><option value="neon">neon</option><option value="legacy">legacy</option></select></label> · Alert-cause and casualty auxiliary data retain pinned Git provenance.<span id="previewLoadStatus" role="status"></span>`;
  const select = document.getElementById('previewSource');
  select.value = source;
  select.addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('preview_source', select.value);
    location.href = url.href;
  });
  const original = window.fetch.bind(window);
  window.fetch = async (input, options) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.origin !== location.origin) throw new Error('Preview blocks cross-origin data request');
    try {
      const response = await original(input, options);
      if (!response.ok) document.getElementById('previewLoadStatus').textContent = ` · Preview data load error: ${url.pathname} (${response.status}); no remote fallback.`;
      return response;
    } catch (error) {
      document.getElementById('previewLoadStatus').textContent = ` · Preview data load error: ${url.pathname}; no remote fallback.`;
      throw error;
    }
  };
})();
