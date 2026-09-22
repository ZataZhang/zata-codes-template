/* 产品页面自身逻辑：视图切换交给共享侧栏的 [data-app-view] 按钮，初始视图由 hash / ?view= 决定。 */
(() => {
  const views = {
    users: { title: '成员列表', description: '按部门筛选成员，演示表格与抽屉。' },
    settings: { title: '产品设置', description: '演示表单与保存反馈。' },
  };
  const heading = document.querySelector('[data-view-heading]');
  const description = document.querySelector('[data-view-description]');

  function switchView(viewName) {
    const view = views[viewName] ? viewName : 'users';
    for (const section of document.querySelectorAll('[data-view-section]')) {
      section.hidden = section.dataset.viewSection !== view;
    }
    heading.textContent = views[view].title;
    description.textContent = views[view].description;
    window.setAppShellActiveView(view);
  }

  for (const button of document.querySelectorAll('[data-app-view]')) {
    button.addEventListener('click', () => switchView(button.dataset.appView));
  }
  document.addEventListener('prototype:reset', () => switchView('users'));
  switchView(window.resolveAppShellView(Object.keys(views), 'users'));
})();
