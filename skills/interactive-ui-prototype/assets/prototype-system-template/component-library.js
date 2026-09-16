(() => {
  // 组件目录与原型 registry 分离；这里只登记组件资产。
  const components = [
    { id: 'buttons', title: '按钮', icon: 'B', category: 'actions', categoryLabel: '操作', contents: '主要、次要、危险、禁用', status: '可用', preview: '<button class="primary">主要操作</button> <button class="secondary">次要操作</button>' },
    { id: 'table', title: '表格', icon: '▤', category: 'display', categoryLabel: '数据展示', contents: '表头、行选择、状态列', status: '可用', preview: '<div class="mini-table"><b>名称</b><b>状态</b><span>示例条目</span><span class="pill success">可用</span></div>' },
    { id: 'forms', title: '表单与选择', icon: '⌨', category: 'inputs', categoryLabel: '输入', contents: '输入框、选择器、开关、校验', status: '可用', preview: '<label class="field">名称<input value="示例原型"></label>' },
    { id: 'feedback', title: '反馈与浮层', icon: '!', category: 'feedback', categoryLabel: '反馈', contents: 'Dialog、Toast、Loading', status: '可用', preview: '<button class="primary">打开 Dialog</button>' },
  ];
  const categoryLabels = { all: '全部组件', actions: '操作', display: '数据展示', inputs: '输入', feedback: '反馈' };
  let selectedCategory = 'all'; const search = document.querySelector('#component-search'); const list = document.querySelector('#component-list'); const nav = document.querySelector('#category-nav'); const empty = document.querySelector('#component-empty');
  const renderNav = () => { nav.innerHTML = Object.entries(categoryLabels).map(([id,label]) => `<button class="${id === selectedCategory ? 'active' : ''}" data-category="${id}">${label}<strong>${id === 'all' ? components.length : ''}</strong></button>`).join(''); };
  const render = () => { const query = search.value.trim().toLowerCase(); const visible = components.filter((component) => (selectedCategory === 'all' || component.category === selectedCategory) && (!query || `${component.title} ${component.contents}`.toLowerCase().includes(query))); empty.hidden = visible.length > 0; list.innerHTML = visible.map((component) => `<details class="component-entry"><summary><span class="component-icon">${component.icon}</span><strong>${component.title}</strong><span>${component.categoryLabel}</span><span>${component.contents}</span><span class="pill success">${component.status}</span><i>⌄</i></summary><div class="component-preview">${component.preview}<a class="detail-link" href="./component-detail.html?component=${component.id}">查看完整组件 →</a></div></details>`).join(''); renderNav(); };
  nav.addEventListener('click', (event) => { const button = event.target.closest('[data-category]'); if (button) { selectedCategory = button.dataset.category; render(); } }); search.addEventListener('input', render); render();
})();
