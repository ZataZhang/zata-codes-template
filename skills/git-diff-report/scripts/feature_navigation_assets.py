#!/usr/bin/env python3
"""功能改动树与核心/全部文件切换的内联资源。"""

FEATURE_STYLE = """
  /* ── 按功能浏览的代码改动树 ───────────────────────────── */
  .feature-grid { grid-template-columns: minmax(285px, 340px) minmax(0, 1fr); }
  .feature-aside { padding: 12px 10px; gap: 9px; }
  .feature-tree-heading { padding: 0 3px; }
  .feature-tree-title-row {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
  }
  .feature-tree-title { font-size: 14px; font-weight: 700; }
  .feature-tree-count {
    border-radius: 99px; background: var(--secondary); padding: 3px 8px;
    color: var(--muted-foreground); font-size: 10.5px; white-space: nowrap;
  }
  .feature-tree-intro {
    margin: 5px 0 0; color: var(--muted-foreground); font-size: 11px; line-height: 1.45;
  }
  .feature-tree-controls { display: grid; gap: 8px; flex: none; }
  .feature-tree-switch, .feature-scope-switch {
    display: inline-flex; gap: 3px; padding: 3px; border-radius: 8px; background: var(--secondary);
  }
  .feature-tree-switch { display: grid; grid-template-columns: 1fr 1fr; }
  .feature-tree-switch button, .feature-scope-switch button {
    border: 0; border-radius: 6px; min-height: 29px; padding: 0 9px;
    background: transparent; color: var(--muted-foreground); font-size: 10.5px; font-weight: 650;
    cursor: pointer;
  }
  .feature-tree-switch button.active, .feature-scope-switch button.active {
    background: var(--card); color: var(--foreground); box-shadow: 0 1px 3px #182a451a;
  }
  .feature-tree-switch button:focus-visible, .feature-scope-switch button:focus-visible {
    outline: 2px solid var(--ring); outline-offset: 1px;
  }
  .feature-tree .feature-tree-group { margin-bottom: 3px; }
  .feature-tree-group > summary.feature-group-head {
    min-height: 42px; padding: 6px 8px; gap: 6px; background: transparent;
  }
  .feature-tree-group > summary.feature-group-head:hover { background: var(--secondary); }
  .feature-tree-group.selected > summary.feature-group-head {
    background: color-mix(in oklab, var(--primary) 8%, var(--card)); color: var(--primary);
  }
  .feature-group-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
  .feature-group-copy strong { font-size: 11.5px; line-height: 1.35; }
  .feature-group-copy > span { color: var(--muted-foreground); font-size: 9.5px; font-weight: 400; }
  .feature-tree-group > .children { margin-left: 8px; }
  .feature-tree .file-row { gap: 2px 7px; padding-top: 5px; padding-bottom: 5px; }
  .feature-tree .file-name { font-size: 11px; }
  .feature-tree .file-summary { font-size: 10px; line-height: 1.35; -webkit-line-clamp: 2; }
  .feature-tree .file-row.core-file .file-name { font-weight: 650; }
  .feature-tree .file-row.active {
    background: color-mix(in oklab, var(--primary) 9%, var(--card));
  }
  .feature-tree .tree-must { font-size: 9px; }
  .feature-grid.is-path-mode .feature-tree { display: none; }
  .feature-grid.is-path-mode .path-tree { display: block; }
  .path-tree .file-summary {
    display: -webkit-box; -webkit-line-clamp: 2; font-size: 10.5px; line-height: 1.35;
  }
  .path-tree .file-move-path { display: none; }

  /* 总览中的 SVG 保留横向阅读宽度；窄屏可以横向滚动查看完整流程。 */
  .feature-svg-figure {
    width: 100%; margin: 8px 0; padding: 9px; overflow-x: auto;
    border: 1px solid var(--border); border-radius: 8px; background: var(--code-bg);
  }
  .feature-svg-figure figcaption {
    display: flex; justify-content: space-between; gap: 8px; margin-bottom: 7px;
    color: var(--muted-foreground); font-size: 10px;
  }
  .feature-svg-figure figcaption strong { color: var(--foreground); }
  .feature-svg-figure figcaption span { font-size: 9px; }
  .feature-svg-diagram {
    display: block; width: auto; max-width: 100%; height: auto; overflow: visible;
  }
  .feature-svg-edge { fill: none; stroke: var(--muted-foreground); stroke-width: 1.5; }
  .feature-svg-edge-label { fill: var(--muted-foreground); font: 9px var(--sans); }
  .feature-svg-diagram marker path { fill: var(--muted-foreground); }
  .feature-svg-node rect:first-of-type {
    fill: var(--card); stroke: var(--border); stroke-width: 1;
  }
  .feature-svg-node-accent { fill: var(--primary); }
  .feature-svg-kind { fill: var(--primary); font: 600 9px var(--sans); }
  .feature-svg-label { fill: var(--foreground); font: 600 10px var(--sans); }
  .feature-svg-detail { fill: var(--muted-foreground); font: 9px var(--sans); }
  .feature-svg-node-link { cursor: pointer; }
  .feature-svg-node-link:hover rect:first-of-type,
  .feature-svg-node-link:focus-visible rect:first-of-type {
    stroke: var(--primary); stroke-width: 2;
  }

  /* ── 功能摘要与核心/全部文件分段切换 ─────────────────── */
  main.feature-viewer {
    display: flex; min-width: 0; min-height: 0; flex-direction: column; padding: 0;
  }
  .feature-view-header {
    flex: none; padding: 12px 16px 10px; border-bottom: 1px solid var(--border);
  }
  .feature-crumb { color: var(--muted-foreground); font-size: 10.5px; }
  .feature-hero-line { display: flex; align-items: flex-start; gap: 12px; margin-top: 7px; }
  .feature-hero-copy { min-width: 0; flex: 1; }
  .feature-hero-copy h2 { margin: 0; font-size: 17px; line-height: 1.35; }
  .feature-hero-copy p {
    margin: 4px 0 0; color: var(--muted-foreground); font-size: 11px; line-height: 1.5;
  }
  .feature-ask-button, .feature-back-button {
    flex: none; border: 1px solid var(--border); border-radius: 7px; padding: 6px 10px;
    background: var(--primary); color: var(--primary-foreground);
    font-size: 10.5px; font-weight: 650;
    cursor: pointer;
  }
  .feature-back-button { background: var(--card); color: var(--foreground); }
  .feature-ask-button:hover { filter: brightness(.94); }
  .feature-back-button:hover { background: var(--secondary); }
  .feature-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
  .feature-badge {
    border: 1px solid var(--border); border-radius: 99px; padding: 3px 7px;
    color: var(--muted-foreground); font-size: 9.5px;
  }
  .feature-badge strong { color: var(--foreground); }
  .feature-badge.core {
    border-color: color-mix(in oklab, var(--primary) 18%, var(--border));
    background: color-mix(in oklab, var(--primary) 6%, var(--card)); color: var(--primary);
  }
  .feature-scope-row { display: flex; align-items: center; gap: 8px; margin-top: 9px; }
  .feature-scope-switch { flex: none; }
  .feature-scope-switch button { min-height: 26px; font-size: 10px; }
  .feature-scope-switch .scope-count {
    margin-left: 4px; color: var(--muted-foreground); font: 9px var(--mono);
  }
  .feature-scope-hint { margin-left: auto; color: var(--muted-foreground); font-size: 10px; }
  .feature-scope-note {
    display: flex; align-items: center; gap: 7px; margin-top: 9px;
    color: var(--muted-foreground); font-size: 10px;
  }
  .feature-scope-note::before {
    content: ""; width: 7px; height: 7px; flex: none; border-radius: 50%;
    background: var(--add-mark);
  }
  .feature-view-header.is-single-file .feature-badges,
  .feature-view-header.is-single-file .feature-scope-row,
  .feature-view-header.is-single-file .feature-scope-note { display: none; }
  .feature-view-header.is-single-file .feature-hero-copy h2 {
    font-family: var(--mono); font-size: 14px; overflow-wrap: anywhere;
  }
  .feature-view-header.is-single-file .feature-hero-copy p { font-family: var(--mono); }
  .feature-view-header.is-single-file .feature-back-button[hidden] { display: none; }
  .feature-view-header.is-single-file .feature-ask-button { margin-left: auto; }

  /* ── 围绕功能或文件提问：静态报告只复制上下文 ─────────── */
  .question-scrim { position: fixed; inset: 0; z-index: 20; background: #18253a45; }
  .question-panel {
    position: fixed; z-index: 21; inset: 0 0 0 auto; width: min(430px, 94vw);
    display: flex; flex-direction: column; border-left: 1px solid var(--border);
    background: var(--card); box-shadow: -15px 0 45px #14243a24;
  }
  .question-head {
    display: flex; align-items: center; justify-content: space-between; padding: 14px 17px;
    border-bottom: 1px solid var(--border);
  }
  .question-head h2 { margin: 0; font-size: 14px; }
  .question-close {
    width: 28px; height: 28px; border: 0; border-radius: 6px;
    background: var(--secondary); cursor: pointer;
  }
  .question-body { flex: 1; overflow: auto; padding: 15px 17px; }
  .question-scope {
    padding: 9px 10px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--secondary);
  }
  .question-scope small {
    display: block; margin-bottom: 4px; color: var(--muted-foreground); font-size: 9.5px;
  }
  .question-scope strong {
    display: block; font-size: 10.5px; line-height: 1.45; overflow-wrap: anywhere;
  }
  .question-body h3 { margin: 17px 0 7px; color: var(--muted-foreground); font-size: 10px; }
  .question-prompts { display: grid; gap: 6px; }
  .question-prompts button {
    border: 1px solid var(--border); border-radius: 7px; padding: 7px 8px;
    background: var(--card); color: var(--foreground); text-align: left;
    font-size: 10.5px; cursor: pointer;
  }
  .question-prompts button:hover { background: var(--secondary); }
  .question-body textarea {
    display: block; width: 100%; min-height: 100px; resize: vertical;
    border: 1px solid var(--border); border-radius: 8px; padding: 8px;
    font: inherit; font-size: 10.5px; line-height: 1.5;
  }
  .question-foot { padding: 11px 17px 14px; border-top: 1px solid var(--border); }
  .question-foot button {
    width: 100%; min-height: 34px; border: 0; border-radius: 7px;
    background: var(--primary); color: var(--primary-foreground);
    font-size: 10.5px; font-weight: 650; cursor: pointer;
  }
  .question-foot p {
    margin: 7px 0 0; color: var(--muted-foreground); font-size: 9.5px;
    line-height: 1.4; text-align: center;
  }
  .question-toast {
    position: fixed; z-index: 30; left: 50%; bottom: 20px; transform: translateX(-50%);
    border-radius: 8px; padding: 8px 12px; background: var(--primary);
    color: var(--primary-foreground); font-size: 10.5px; box-shadow: 0 4px 18px #18253a35;
  }
  [hidden] { display: none !important; }

  @media (max-width: 1100px) {
    .feature-grid { grid-template-columns: minmax(260px, 310px) minmax(0, 1fr); }
  }
  @media (max-width: 760px) {
    .feature-grid {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: minmax(190px, 42%) minmax(0, 1fr);
    }
    .feature-aside { padding: 9px; }
    .feature-tree-switch { display: none; }
    .feature-hero-line { display: block; }
    .feature-ask-button, .feature-back-button { margin-top: 8px; }
    .feature-scope-row { align-items: flex-start; flex-direction: column; }
    .feature-scope-hint { margin-left: 0; }
    .feature-svg-figure { width: 100%; }
    .feature-svg-diagram { max-width: none; }
  }
"""

FEATURE_SCRIPT = """
  (function () {
    "use strict";
    var featureGrid = document.querySelector('.feature-grid');
    if (!featureGrid) { return; }
    var groupNodes = Array.prototype.slice.call(
      featureGrid.querySelectorAll('.feature-tree-group')
    );
    var groupByIndex = {};
    groupNodes.forEach(function (groupNode) {
      groupByIndex[groupNode.dataset.featureIndex] = groupNode;
    });
    var fileSections = Array.prototype.slice.call(
      featureGrid.querySelectorAll('.viewer-body > .file')
    );
    var fileByIndex = {};
    fileSections.forEach(function (section) {
      fileByIndex[section.id.slice(1)] = section;
    });
    var featureTree = featureGrid.querySelector('.feature-tree');
    var pathTree = featureGrid.querySelector('.path-tree');
    var treeModeButtons = Array.prototype.slice.call(
      featureGrid.querySelectorAll('[data-tree-mode]')
    );
    var scopeButtons = Array.prototype.slice.call(
      featureGrid.querySelectorAll('[data-feature-scope]')
    );
    var header = featureGrid.querySelector('.feature-view-header');
    var titleNode = header.querySelector('[data-feature-title]');
    var summaryNode = header.querySelector('[data-feature-summary]');
    var crumbNode = header.querySelector('[data-feature-crumb]');
    var fileCountNode = header.querySelector('[data-feature-file-count]');
    var coreCountNodes = header.querySelectorAll('[data-feature-core-count]');
    var supportCountNode = header.querySelector('[data-feature-support-count]');
    var addedNode = header.querySelector('[data-feature-added]');
    var removedNode = header.querySelector('[data-feature-removed]');
    var scopeNote = header.querySelector('.feature-scope-note');
    var askButton = header.querySelector('.feature-ask-button');
    var backButton = header.querySelector('.feature-back-button');
    var viewerBody = featureGrid.querySelector('.viewer-body');
    var selectedFeatureIndex = groupNodes.length ? groupNodes[0].dataset.featureIndex : '0';
    var selectedFileIndex = null;
    var featureScope = 'core';
    var treeMode = 'feature';
    var questionPanel = document.querySelector('.question-panel');
    var questionScrim = document.querySelector('.question-scrim');
    var questionText = document.querySelector('.question-panel textarea');
    var questionToast = document.querySelector('.question-toast');
    var toastTimer;

    function listIndexes(value) {
      return (value || '').split(' ').filter(Boolean);
    }

    function selectedGroup() {
      return groupByIndex[selectedFeatureIndex] || groupNodes[0];
    }

    function groupSections(groupIndex, coreOnly) {
      return fileSections.filter(function (section) {
        var groups = listIndexes(section.dataset.featureGroups);
        var coreGroups = listIndexes(section.dataset.featureCoreGroups);
        return groups.indexOf(String(groupIndex)) !== -1
          && (!coreOnly || coreGroups.indexOf(String(groupIndex)) !== -1);
      });
    }

    function setTreeMode(mode) {
      treeMode = mode;
      featureGrid.classList.toggle('is-path-mode', mode === 'path');
      if (featureTree) { featureTree.hidden = mode !== 'feature'; }
      if (pathTree) { pathTree.hidden = mode !== 'path'; }
      treeModeButtons.forEach(function (button) {
        var selected = button.dataset.treeMode === treeMode;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
    }

    function renderHeader() {
      var groupNode = selectedGroup();
      if (!groupNode) { return; }
      var isSingleFile = selectedFileIndex !== null;
      header.classList.toggle('is-single-file', isSingleFile);
      askButton.textContent = isSingleFile ? '问这个文件' : '问这个功能';
      backButton.hidden = !isSingleFile;
      if (isSingleFile) {
        var section = fileByIndex[selectedFileIndex];
        var path = section ? section.querySelector('.file-head h2').textContent : '';
        var fileName = path.split('/').pop();
        var summary = section && section.querySelector('.summary');
        var isCore = section
          && listIndexes(section.dataset.featureCoreGroups).indexOf(selectedFeatureIndex) !== -1;
        crumbNode.textContent = '改动树 / 按功能 / ' + groupNode.dataset.featureTitle + ' / 单文件';
        titleNode.textContent = fileName;
        summaryNode.textContent = path;
        fileCountNode.textContent = '1';
        coreCountNodes.forEach(function (node) { node.textContent = isCore ? '1' : '0'; });
        supportCountNode.textContent = isCore ? '0' : '1';
        var stats = section && section.querySelector('.stats');
        var added = stats && stats.querySelector('.add-stat');
        var removed = stats && stats.querySelector('.del-stat');
        addedNode.textContent = added ? added.textContent : '+0';
        removedNode.textContent = removed ? removed.textContent : '-0';
        if (summary) { summaryNode.setAttribute('data-file-summary', summary.textContent); }
        return;
      }
      crumbNode.textContent = '改动树 / 按功能 / ' + groupNode.dataset.featureTitle;
      titleNode.textContent = groupNode.dataset.featureTitle;
      summaryNode.textContent = groupNode.dataset.featureSummary;
      summaryNode.removeAttribute('data-file-summary');
      fileCountNode.textContent = groupNode.dataset.fileCount;
      coreCountNodes.forEach(function (node) { node.textContent = groupNode.dataset.coreCount; });
      supportCountNode.textContent = groupNode.dataset.supportCount;
      addedNode.textContent = '+' + groupNode.dataset.added;
      removedNode.textContent = '-' + groupNode.dataset.removed;
      scopeButtons.forEach(function (button) {
        var count = button.querySelector('.scope-count');
        if (count) {
          count.textContent = button.dataset.featureScope === 'core'
            ? groupNode.dataset.coreCount
            : groupNode.dataset.fileCount;
        }
      });
      if (scopeNote) {
        scopeNote.textContent = featureScope === 'core'
          ? '先展示核心 diff；配套文件仍可在左侧树中浏览，或点「全部文件」。'
          : '正在显示所选功能下的全部文件。';
      }
    }

    function renderSections() {
      fileSections.forEach(function (section) {
        var show = false;
        if (selectedFileIndex !== null) {
          show = section.id === 'f' + selectedFileIndex;
        } else {
          var groups = listIndexes(section.dataset.featureGroups);
          var coreGroups = listIndexes(section.dataset.featureCoreGroups);
          show = groups.indexOf(selectedFeatureIndex) !== -1
            && (featureScope === 'all' || coreGroups.indexOf(selectedFeatureIndex) !== -1);
        }
        section.hidden = !show;
      });
      featureGrid.querySelectorAll('.file-row').forEach(function (row) {
        var active = selectedFileIndex !== null && row.dataset.index === selectedFileIndex;
        row.classList.toggle('active', active);
        if (active) { row.setAttribute('aria-current', 'true'); }
        else { row.removeAttribute('aria-current'); }
      });
      groupNodes.forEach(function (groupNode) {
        groupNode.classList.toggle(
          'selected', groupNode.dataset.featureIndex === selectedFeatureIndex
        );
      });
      scopeButtons.forEach(function (button) {
        var selected = button.dataset.featureScope === featureScope;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
      renderHeader();
      if (viewerBody) { viewerBody.scrollTop = 0; }
    }

    function selectGroup(groupIndex) {
      if (!groupByIndex[groupIndex]) { return; }
      selectedFeatureIndex = String(groupIndex);
      selectedFileIndex = null;
      featureScope = 'core';
      renderSections();
    }

    function selectFile(fileIndex, featureIndex) {
      var section = fileByIndex[String(fileIndex)];
      if (!section) { return; }
      var groupIndexes = listIndexes(section.dataset.featureGroups);
      var resolvedGroup = featureIndex && groupIndexes.indexOf(String(featureIndex)) !== -1
        ? String(featureIndex)
        : (groupIndexes.indexOf(selectedFeatureIndex) !== -1
          ? selectedFeatureIndex
          : (groupIndexes[0] || selectedFeatureIndex));
      selectedFeatureIndex = resolvedGroup;
      selectedFileIndex = String(fileIndex);
      featureScope = 'core';
      renderSections();
    }

    groupNodes.forEach(function (groupNode) {
      var summary = groupNode.querySelector(':scope > summary');
      summary.addEventListener('click', function () {
        selectGroup(groupNode.dataset.featureIndex);
      });
    });
    featureGrid.querySelectorAll('.file-row').forEach(function (row) {
      row.addEventListener('click', function (event) {
        event.preventDefault();
        selectFile(row.dataset.index, row.dataset.featureIndex);
      });
    });
    treeModeButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        selectedFileIndex = null;
        setTreeMode(button.dataset.treeMode);
        renderSections();
      });
    });
    scopeButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        selectedFileIndex = null;
        featureScope = button.dataset.featureScope;
        renderSections();
      });
    });
    if (backButton) {
      backButton.addEventListener('click', function () {
        selectedFileIndex = null;
        featureScope = 'core';
        setTreeMode('feature');
        renderSections();
      });
    }
    document.querySelectorAll('.overview .ov-feature-diagram .feature-svg-node-link').forEach(
      function (link) {
        link.addEventListener('click', function (event) {
          event.preventDefault();
          var diagramGroup = link.closest('.ov-feature-diagram');
          var fileIndex = (link.getAttribute('href').match(/^#f(\\d+)$/) || [])[1];
          if (diagramGroup && fileIndex) {
            setTreeMode('feature');
            selectFile(fileIndex, diagramGroup.dataset.featureIndex);
          }
        });
      }
    );

    function questionSections() {
      if (selectedFileIndex !== null) { return [fileByIndex[selectedFileIndex]]; }
      return groupSections(selectedFeatureIndex, false);
    }

    function openQuestion() {
      if (!questionPanel || !questionScrim) { return; }
      var groupNode = selectedGroup();
      var title = selectedFileIndex !== null
        ? fileByIndex[selectedFileIndex].querySelector('.file-head h2').textContent
        : groupNode.dataset.featureTitle;
      var scopeNode = questionPanel.querySelector('.question-scope strong');
      scopeNode.textContent = selectedFileIndex !== null
        ? '文件：' + title
        : '功能：' + title + '（' + groupNode.dataset.fileCount + ' 个文件）';
      questionPanel.hidden = false;
      questionScrim.hidden = false;
      questionText.focus();
    }

    function closeQuestion() {
      if (questionPanel) { questionPanel.hidden = true; }
      if (questionScrim) { questionScrim.hidden = true; }
    }

    function showToast(message) {
      if (!questionToast) { return; }
      questionToast.textContent = message;
      questionToast.hidden = false;
      window.clearTimeout(toastTimer);
      toastTimer = window.setTimeout(function () { questionToast.hidden = true; }, 2200);
    }

    function buildQuestionContext() {
      var groupNode = selectedGroup();
      var title = selectedFileIndex !== null
        ? fileByIndex[selectedFileIndex].querySelector('.file-head h2').textContent
        : groupNode.dataset.featureTitle;
      var context = questionSections().map(function (section) {
        var path = section.querySelector('.file-head h2').textContent;
        var summary = section.querySelector('.summary');
        return '- ' + path + '：' + (summary ? summary.textContent : '无摘要');
      }).join('\\n');
      var question = questionText.value.trim()
        || '请解释这组代码改动的目的、关键流程和需要注意的风险。';
      return '请只根据下面给出的改动上下文回答；如果信息不足，请明确指出。\\n\\n'
        + '当前范围：' + title + '\\n\\n改动文件与摘要：\\n' + context
        + '\\n\\n我的问题：\\n' + question;
    }

    function copyQuestionContext() {
      var value = buildQuestionContext();
      function fallbackCopy() {
        var field = document.createElement('textarea');
        field.value = value;
        field.style.position = 'fixed';
        field.style.opacity = '0';
        document.body.appendChild(field);
        field.select();
        var copied = false;
        try { copied = document.execCommand('copy'); } catch (error) { copied = false; }
        field.remove();
        showToast(copied ? '问题和改动上下文已复制' : '复制失败，请手动选择并复制问题');
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value)
          .then(function () { showToast('问题和改动上下文已复制'); })
          .catch(fallbackCopy);
      } else { fallbackCopy(); }
    }

    if (askButton) { askButton.addEventListener('click', openQuestion); }
    if (questionScrim) { questionScrim.addEventListener('click', closeQuestion); }
    var closeButton = document.querySelector('.question-close');
    if (closeButton) { closeButton.addEventListener('click', closeQuestion); }
    var copyButton = document.querySelector('.question-copy');
    if (copyButton) { copyButton.addEventListener('click', copyQuestionContext); }
    document.querySelectorAll('.question-prompts button').forEach(function (button) {
      button.addEventListener('click', function () {
        questionText.value = button.dataset.prompt;
        questionText.focus();
      });
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { closeQuestion(); }
    });

    setTreeMode('feature');
    renderSections();
  }());
"""
