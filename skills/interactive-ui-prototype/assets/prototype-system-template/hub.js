(() => {
  // 清单只维护 registry.js；这里不再手写条目，也不在侧栏脚本里重复一份。
  const prototypes = Array.isArray(window.PROTOTYPE_REGISTRY) ? window.PROTOTYPE_REGISTRY : [];
  const labels = { 'image-state': '图片原型', 'code-native': '交互原型', available: '可用', archived: '已归档' };
  const state = { query: '', project: 'all', module: 'all', form: 'all', availability: 'all', group: 'none', selectedId: prototypes[0]?.id ?? '' };
  const elements = { catalog: document.querySelector('#catalog'), detail: document.querySelector('#detail'), empty: document.querySelector('#empty'), search: document.querySelector('#search'), project: document.querySelector('#project'), module: document.querySelector('#module'), form: document.querySelector('#form'), total: document.querySelector('[data-total]'), filters: [...document.querySelectorAll('[data-filter]')], groups: [...document.querySelectorAll('[data-group]')] };
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
  const addOptions = (select, values) => [...new Set(values)].sort().forEach((value) => select.add(new Option(value, value)));
  const matches = (prototype) => {
    const text = `${prototype.title} ${prototype.description} ${prototype.project} ${prototype.module} ${prototype.system ?? ''}`.toLowerCase();
    return (!state.query || text.includes(state.query)) && (state.project === 'all' || prototype.project === state.project) && (state.module === 'all' || prototype.module === state.module) && (state.form === 'all' || prototype.form === state.form) && (state.availability === 'all' || prototype.availability === state.availability);
  };
  const renderDetail = () => {
    const prototype = prototypes.find((candidate) => candidate.id === state.selectedId);
    if (!prototype) { elements.detail.innerHTML = '<p>请选择一个原型。</p>'; return; }
    const preview = prototype.preview ? `<img src="${escapeHtml(prototype.preview)}" alt="${escapeHtml(prototype.title)}预览">` : '<div class="thumb placeholder">HTML</div>';
    const systemRow = `<div><dt>原型系统</dt><dd>${escapeHtml(prototype.system || '独立原型')}</dd></div>`;
    elements.detail.innerHTML = `${preview}<h2>${escapeHtml(prototype.title)}</h2><p>${escapeHtml(prototype.description)}</p><dl><div><dt>项目</dt><dd>${escapeHtml(prototype.project)}</dd></div><div><dt>模块</dt><dd>${escapeHtml(prototype.module)}</dd></div>${systemRow}<div><dt>形式</dt><dd>${labels[prototype.form]}</dd></div><div><dt>验证层级</dt><dd>${escapeHtml(prototype.validationLevel)}</dd></div><div><dt>版本</dt><dd>${escapeHtml(prototype.version)}</dd></div></dl><div class="detail-actions"><a class="secondary" href="${escapeHtml(prototype.source)}">查看说明</a><a class="primary" href="${escapeHtml(prototype.entry)}">打开原型</a></div>`;
  };
  const rowMarkup = (prototype) => `<tr data-id="${escapeHtml(prototype.id)}" class="${prototype.id === state.selectedId ? 'selected' : ''}"><td><a href="${escapeHtml(prototype.entry)}" aria-label="打开${escapeHtml(prototype.title)}">${prototype.preview ? `<img class="thumb" src="${escapeHtml(prototype.preview)}" alt="">` : '<span class="thumb placeholder">HTML</span>'}</a></td><td><a class="title-link" href="${escapeHtml(prototype.entry)}">${escapeHtml(prototype.title)}</a></td><td>${escapeHtml(prototype.project)}</td><td>${escapeHtml(prototype.module)}</td><td><span class="pill">${labels[prototype.form] ?? escapeHtml(prototype.form)}</span></td><td><span class="pill success">${labels[prototype.availability] ?? escapeHtml(prototype.availability)}</span></td></tr>`;
  /** 同名原型属于同一台产品：分组行说明它们共享外壳，评审者不必回目录逐个打开。 */
  const groupMarkup = (systemName, groupEntries) => `<tr class="group-row"><td colspan="6"><strong>${escapeHtml(systemName)}（${groupEntries.length}）</strong><span>共享同一个产品外壳，打开任意一个都能用左侧侧栏点到其余模块。</span></td></tr>`;
  const render = () => {
    const visible = prototypes.filter(matches);
    if (!visible.some((prototype) => prototype.id === state.selectedId)) state.selectedId = visible[0]?.id ?? '';
    elements.empty.hidden = visible.length > 0;
    if (state.group === 'none') {
      elements.catalog.innerHTML = visible.map(rowMarkup).join('');
    } else {
      const groups = new Map();
      for (const prototype of visible) {
        const systemName = prototype.system || '独立原型';
        if (!groups.has(systemName)) groups.set(systemName, []);
        groups.get(systemName).push(prototype);
      }
      elements.catalog.innerHTML = [...groups].map(([systemName, groupEntries]) => groupMarkup(systemName, groupEntries) + groupEntries.map(rowMarkup).join('')).join('');
    }
    renderDetail();
  };
  addOptions(elements.project, prototypes.map((prototype) => prototype.project)); addOptions(elements.module, prototypes.map((prototype) => prototype.module)); elements.total.textContent = String(prototypes.length);
  elements.search.addEventListener('input', (event) => { state.query = event.target.value.trim().toLowerCase(); render(); });
  [['project', elements.project], ['module', elements.module], ['form', elements.form]].forEach(([key, select]) => select.addEventListener('change', (event) => { state[key] = event.target.value; render(); }));
  elements.catalog.addEventListener('click', (event) => { if (event.target.closest('a,button')) return; const row = event.target.closest('[data-id]'); if (row) { state.selectedId = row.dataset.id; render(); } });
  elements.filters.forEach((button) => button.addEventListener('click', () => { const filter = button.dataset.filter; state.form = ['image-state', 'code-native'].includes(filter) ? filter : 'all'; state.availability = filter === 'available' ? 'available' : 'all'; elements.form.value = state.form; state.group = filter === 'all' ? 'none' : state.group; elements.filters.forEach((candidate) => candidate.classList.toggle('active', candidate === button)); render(); }));
  elements.groups.forEach((button) => button.addEventListener('click', () => { state.group = button.dataset.group; elements.groups.forEach((candidate) => candidate.classList.toggle('active', candidate === button)); render(); }));
  render();
})();
