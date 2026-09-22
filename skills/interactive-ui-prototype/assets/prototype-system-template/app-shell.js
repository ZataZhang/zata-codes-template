/*
 * 产品外壳 app shell：同一产品的多个原型页面共享的侧栏。它属于被评审的产品 UI，
 * 不是 prototype chrome（评审 Dock 见 prototype-chrome.js）。
 *
 * 为什么需要它：多个原型画的是同一台产品时，各自复制一份侧栏必然互相漂移，
 * 跨模块入口也只能画成点不动的文字，评审者看到的是几座孤岛而不是一个产品。
 *
 * 这里只声明「哪个模块对应 registry 里的哪个原型、进入哪个视图」；
 * 文件名、标题、能否打开一律查 registry.js，不在侧栏里重复维护第二份清单。
 * 查不到、或 availability 不是 available 的模块降级为静态文本并说明原因，
 * 不留下点了会失败的假按钮。
 *
 * 加载顺序：registry.js → app-shell.js → 页面自身脚本（页面脚本要给 [data-app-view] 绑事件）。
 */
(() => {
  const navGroups = [
    {
      label: '工作台',
      items: [
        { prototypeId: 'example-interactive', label: '成员列表', icon: '▦', view: 'users' },
        { prototypeId: 'example-interactive', label: '产品设置', icon: '⚙', view: 'settings' },
        { prototypeId: 'example-image', label: '图片状态原型', icon: '✦', view: 'overview' },
        { prototypeId: 'example-archived', label: '归档模块', icon: '◈' },
        { label: '账单', icon: '▤' },
      ],
    },
  ];

  const registry = Array.isArray(window.PROTOTYPE_REGISTRY) ? window.PROTOTYPE_REGISTRY : [];
  const entriesById = new Map(registry.map((entry) => [entry.id, entry]));
  const currentPage = document.body.dataset.appShellPage || window.location.pathname.split('/').pop() || '';
  const bareFileName = (path) => String(path || '').replace(/^\.\//, '');

  /** 一个导航项能落到哪种形态：跨页链接 / 本页视图按钮 / 静态文本，全由 registry 决定。 */
  function resolveNavItem(navItem) {
    const entry = navItem.prototypeId ? entriesById.get(navItem.prototypeId) : null;
    // 侧栏写产品里的模块名，不写原型文档标题：同一个原型的两个子视图要能各自命名。
    const label = navItem.label || (entry ? entry.title : navItem.prototypeId) || '未命名条目';
    const icon = navItem.icon || '·';
    if (!entry) return { label, icon, pendingReason: `${label}：本次没有原型，不可点击` };
    if (entry.availability !== 'available') return { label, icon, pendingReason: `${label}：原型当前为 ${entry.availability}，不可打开` };
    const fileName = bareFileName(entry.entry);
    if (!fileName) return { label, icon, pendingReason: `${label}：registry 未登记入口` };
    if (fileName === currentPage) return { label, icon, samePage: true, view: navItem.view };
    return { label, icon, href: `./${fileName}${navItem.view ? `#${navItem.view}` : ''}` };
  }

  function buildNavItem(navItem) {
    const target = resolveNavItem(navItem);
    let node;
    if (target.href) {
      node = document.createElement('a');
      node.className = 'app-nav-item app-nav-link';
      node.href = target.href;
      node.title = `${target.label}：跳到另一个原型页面`;
    } else if (target.samePage && target.view) {
      node = document.createElement('button');
      node.type = 'button';
      node.className = 'app-nav-item';
      node.dataset.appView = target.view;
      node.title = target.label;
    } else {
      node = document.createElement('span');
      node.className = target.samePage ? 'app-nav-item is-current' : 'app-nav-item is-pending';
      if (target.samePage) node.setAttribute('aria-current', 'page');
      else node.title = target.pendingReason;
    }
    const iconNode = document.createElement('span');
    iconNode.className = 'app-nav-icon';
    iconNode.setAttribute('aria-hidden', 'true');
    iconNode.textContent = target.icon;
    const labelNode = document.createElement('span');
    labelNode.className = 'app-nav-text';
    labelNode.textContent = target.label;
    node.append(iconNode, labelNode);
    if (target.href) {
      const markNode = document.createElement('span');
      markNode.className = 'app-nav-cross';
      markNode.setAttribute('aria-hidden', 'true');
      markNode.textContent = '↗';
      node.append(markNode);
    }
    return node;
  }

  for (const slot of document.querySelectorAll('[data-app-sidebar]')) {
    const navNode = document.createElement('nav');
    navNode.className = 'app-nav';
    navNode.setAttribute('aria-label', '产品主导航');
    for (const navGroup of navGroups) {
      const groupNode = document.createElement('div');
      groupNode.className = 'app-nav-group';
      const groupLabel = document.createElement('div');
      groupLabel.className = 'app-nav-group-label';
      groupLabel.textContent = navGroup.label;
      groupNode.append(groupLabel, ...navGroup.items.map(buildNavItem));
      navNode.append(groupNode);
    }
    slot.append(navNode);
  }

  /** 跨原型跳转只传递目标视图：hash 优先，其次 ?view=，都没有时回到页面默认视图。 */
  window.resolveAppShellView = function resolveAppShellView(knownViews, fallbackView) {
    const requestedView = window.location.hash.replace('#', '');
    const queryView = new URLSearchParams(window.location.search).get('view') || '';
    if (knownViews.includes(requestedView)) return requestedView;
    if (knownViews.includes(queryView)) return queryView;
    return fallbackView;
  };

  /** 页面切换视图后调用，让侧栏高亮跟画面一致。 */
  window.setAppShellActiveView = function setAppShellActiveView(activeView) {
    for (const node of document.querySelectorAll('[data-app-view]')) {
      const isActive = node.dataset.appView === activeView;
      node.classList.toggle('is-active', isActive);
      if (isActive) node.setAttribute('aria-current', 'page');
      else node.removeAttribute('aria-current');
    }
  };

  // ?capture=1 供 Hub 缩略图与产品视觉对照：隐藏评审 Dock，只留产品画面。
  if (new URLSearchParams(window.location.search).get('capture') === '1') {
    document.body.classList.add('capture-product-only');
  }
})();
