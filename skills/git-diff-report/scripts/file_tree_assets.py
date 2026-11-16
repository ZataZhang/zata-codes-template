#!/usr/bin/env python3
"""文件树导航内联到报告中的样式与交互脚本。"""

TREE_STYLE = """
  /* ── 文件树搜索与计数 ─────────────────────────────────── */
  .tree-toolbar { display: flex; flex: none; flex-direction: column; gap: 6px; padding: 0 2px; }
  .tree-search {
    display: flex; min-width: 0; align-items: center; gap: 7px;
    border: 1px solid var(--border); border-radius: 7px; background: var(--card); padding: 0 8px;
  }
  .tree-search:focus-within { border-color: var(--ring); }
  .tree-search > span { color: var(--muted-foreground); font-size: 15px; }
  .tree-search input {
    min-width: 0; min-height: 31px; flex: 1; border: 0; outline: 0;
    background: transparent; color: var(--foreground); font: inherit; font-size: 11.5px;
  }
  .tree-search input::placeholder { color: var(--muted-foreground); opacity: .85; }
  .tree-search kbd {
    border: 1px solid var(--border); border-radius: 4px; padding: 0 4px;
    color: var(--muted-foreground); font-family: var(--mono); font-size: 10px;
  }
  .tree-toolbar-meta {
    display: flex; min-height: 22px; align-items: center; justify-content: space-between; gap: 8px;
  }
  .tree-count { padding-left: 3px; color: var(--muted-foreground); font-size: 10.5px; }
  .tree-feature-back {
    border: 0; border-radius: 5px; background: transparent; padding: 3px 6px;
    color: var(--primary); font-size: 10.5px; font-weight: 600; cursor: pointer;
  }
  .tree-feature-back:hover { background: var(--secondary); }
  .tree-feature-back:focus-visible { outline: 2px solid var(--ring); outline-offset: 1px; }
  .tree-empty {
    padding: 18px 8px; color: var(--muted-foreground); font-size: 12px; text-align: center;
  }
"""

TREE_SCRIPT = """
  // 全文件视图保留目录树，同时按完整路径或文件摘要筛选；目录会跟着命中项自动展开。
  var treeSearchInput = document.querySelector('.tree-search-input');
  var treeCountNode = document.querySelector('.tree-count');
  var treeEmptyNode = treeScroller ? treeScroller.querySelector('.tree-empty') : null;
  var treeFileRows = treeScroller
    ? Array.prototype.slice.call(treeScroller.querySelectorAll('.node.file-row'))
    : [];
  var treeDirectoryNodes = treeScroller
    ? Array.prototype.slice.call(treeScroller.querySelectorAll('details.node.dir')).reverse()
    : [];
  function filterTreeRows() {
    if (!treeSearchInput || !treeScroller) { return; }
    var query = treeSearchInput.value.trim().toLocaleLowerCase();
    var visibleFileCount = 0;
    treeFileRows.forEach(function (row) {
      var searchableText = (row.dataset.search || row.title || row.textContent).toLocaleLowerCase();
      var featureGroup = row.closest('.feature-tree-group');
      var groupTitle = featureGroup
        ? (featureGroup.dataset.featureTitle || '').toLocaleLowerCase()
        : '';
      var matches = !query || searchableText.indexOf(query) !== -1
        || groupTitle.indexOf(query) !== -1;
      row.hidden = !matches;
      if (matches) { visibleFileCount += 1; }
    });
    treeDirectoryNodes.forEach(function (directory) {
      var featureTitle = directory.classList.contains('feature-tree-group')
        ? (directory.dataset.search || directory.dataset.featureTitle || '').toLocaleLowerCase()
        : '';
      var hasMatch = Boolean(query && featureTitle.indexOf(query) !== -1)
        || Array.prototype.some.call(
        directory.querySelectorAll('.node.file-row'),
        function (row) { return !row.hidden; }
      );
      directory.hidden = !hasMatch;
      if (query && hasMatch) { directory.open = true; }
    });
    if (treeCountNode) {
      var totalFileCount = Number(treeCountNode.dataset.total || treeFileRows.length);
      treeCountNode.textContent = query
        ? visibleFileCount + ' / ' + totalFileCount + ' 个文件'
        : totalFileCount + ' 个文件';
    }
    if (treeEmptyNode) { treeEmptyNode.hidden = visibleFileCount > 0; }
  }
  if (treeSearchInput) {
    treeSearchInput.addEventListener('input', filterTreeRows);
    filterTreeRows();
  }
  document.addEventListener('keydown', function (event) {
    var target = event.target;
    var isTyping = target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
    if (event.key === '/' && !isTyping && treeSearchInput
      && treeSearchInput.getClientRects().length) {
      event.preventDefault();
      treeSearchInput.focus();
    }
  });
"""
