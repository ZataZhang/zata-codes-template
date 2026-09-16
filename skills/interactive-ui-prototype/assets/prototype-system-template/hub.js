(() => {
  // 复制模板后只维护此 registry；不要在 HTML 中重复手写原型条目。
  const prototypes = [
    { id: 'example-image', title: '示例图片原型', project: '示例项目', module: '核心流程', form: 'image-state', version: 'v1.0', updatedAt: 'YYYY-MM-DD', availability: 'available', validationLevel: 'component preview', description: '替换为原型用途和主要流程。', preview: './assets/example.png', entry: './image-state.html', source: './prototype-notes.html' },
    { id: 'example-interactive', title: '示例交互原型', project: '示例项目', module: '设置', form: 'code-native', version: 'v1.0', updatedAt: 'YYYY-MM-DD', availability: 'available', validationLevel: 'component preview', description: '替换为交互原型说明。', preview: '', entry: './example.html', source: './prototype-notes.html' },
  ];
  const labels = { 'image-state': '图片原型', 'code-native': '交互原型', available: '可用', archived: '已归档' };
  const state = { query: '', project: 'all', module: 'all', form: 'all', availability: 'all', selectedId: prototypes[0]?.id ?? '' };
  const elements = { catalog: document.querySelector('#catalog'), detail: document.querySelector('#detail'), empty: document.querySelector('#empty'), search: document.querySelector('#search'), project: document.querySelector('#project'), module: document.querySelector('#module'), form: document.querySelector('#form'), total: document.querySelector('[data-total]'), filters: [...document.querySelectorAll('[data-filter]')] };
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
  const addOptions = (select, values) => [...new Set(values)].sort().forEach((value) => select.add(new Option(value, value)));
  const matches = (prototype) => {
    const text = `${prototype.title} ${prototype.description} ${prototype.project} ${prototype.module}`.toLowerCase();
    return (!state.query || text.includes(state.query)) && (state.project === 'all' || prototype.project === state.project) && (state.module === 'all' || prototype.module === state.module) && (state.form === 'all' || prototype.form === state.form) && (state.availability === 'all' || prototype.availability === state.availability);
  };
  const renderDetail = () => {
    const prototype = prototypes.find((candidate) => candidate.id === state.selectedId);
    if (!prototype) { elements.detail.innerHTML = '<p>请选择一个原型。</p>'; return; }
    const preview = prototype.preview ? `<img src="${escapeHtml(prototype.preview)}" alt="${escapeHtml(prototype.title)}预览">` : '<div class="thumb placeholder">HTML</div>';
    elements.detail.innerHTML = `${preview}<h2>${escapeHtml(prototype.title)}</h2><p>${escapeHtml(prototype.description)}</p><dl><div><dt>项目</dt><dd>${escapeHtml(prototype.project)}</dd></div><div><dt>模块</dt><dd>${escapeHtml(prototype.module)}</dd></div><div><dt>形式</dt><dd>${labels[prototype.form]}</dd></div><div><dt>验证层级</dt><dd>${escapeHtml(prototype.validationLevel)}</dd></div><div><dt>版本</dt><dd>${escapeHtml(prototype.version)}</dd></div></dl><div class="detail-actions"><a class="secondary" href="${escapeHtml(prototype.source)}">查看说明</a><a class="primary" href="${escapeHtml(prototype.entry)}">打开原型</a></div>`;
  };
  const render = () => {
    const visible = prototypes.filter(matches);
    if (!visible.some((prototype) => prototype.id === state.selectedId)) state.selectedId = visible[0]?.id ?? '';
    elements.empty.hidden = visible.length > 0;
    elements.catalog.innerHTML = visible.map((prototype) => `<tr data-id="${prototype.id}" class="${prototype.id === state.selectedId ? 'selected' : ''}"><td><a href="${escapeHtml(prototype.entry)}" aria-label="打开${escapeHtml(prototype.title)}">${prototype.preview ? `<img class="thumb" src="${escapeHtml(prototype.preview)}" alt="">` : '<span class="thumb placeholder">HTML</span>'}</a></td><td><a class="title-link" href="${escapeHtml(prototype.entry)}">${escapeHtml(prototype.title)}</a></td><td>${escapeHtml(prototype.project)}</td><td>${escapeHtml(prototype.module)}</td><td><span class="pill">${labels[prototype.form]}</span></td><td><span class="pill success">${labels[prototype.availability]}</span></td></tr>`).join('');
    renderDetail();
  };
  addOptions(elements.project, prototypes.map((prototype) => prototype.project)); addOptions(elements.module, prototypes.map((prototype) => prototype.module)); elements.total.textContent = String(prototypes.length);
  elements.search.addEventListener('input', (event) => { state.query = event.target.value.trim().toLowerCase(); render(); });
  [['project', elements.project], ['module', elements.module], ['form', elements.form]].forEach(([key, select]) => select.addEventListener('change', (event) => { state[key] = event.target.value; render(); }));
  elements.catalog.addEventListener('click', (event) => { if (event.target.closest('a,button')) return; const row = event.target.closest('[data-id]'); if (row) { state.selectedId = row.dataset.id; render(); } });
  elements.filters.forEach((button) => button.addEventListener('click', () => { const filter = button.dataset.filter; state.form = ['image-state', 'code-native'].includes(filter) ? filter : 'all'; state.availability = filter === 'available' ? 'available' : 'all'; elements.form.value = state.form; elements.filters.forEach((candidate) => candidate.classList.toggle('active', candidate === button)); render(); }));
  render();
})();
