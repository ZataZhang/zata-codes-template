#!/usr/bin/env python3
"""功能链路导航内联到报告中的样式与交互脚本。"""

FEATURE_STYLE = """
  /* ── 功能链路导航：功能 → 步骤/文件 → diff ─────────────── */
  .feature-grid { grid-template-columns: 220px minmax(310px, 390px) minmax(0, 1fr); }
  .feature-nav {
    display: flex; min-height: 0; flex-direction: column; gap: 5px; padding: 9px;
    overflow-y: auto; overscroll-behavior: contain;
  }
  .feature-nav-heading {
    display: flex; align-items: baseline; justify-content: space-between;
    padding: 4px 6px 7px; color: var(--foreground); font-size: 12px;
  }
  .feature-nav-heading span {
    color: var(--muted-foreground); font-size: 10.5px; font-weight: 400;
  }
  .feature-nav-button {
    display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 8px;
    width: 100%; padding: 9px 8px; border: 1px solid transparent; border-radius: 8px;
    background: transparent; text-align: left; cursor: pointer;
  }
  .feature-nav-button:hover { background: var(--secondary); }
  .feature-nav-button.active {
    background: color-mix(in oklab, var(--primary) 9%, var(--card));
    border-color: color-mix(in oklab, var(--primary) 20%, var(--border));
  }
  .feature-nav-number {
    display: grid; width: 24px; height: 24px; place-items: center; border-radius: 7px;
    background: var(--secondary); color: var(--muted-foreground); font-family: var(--mono);
    font-size: 10px; font-weight: 650;
  }
  .feature-nav-button.active .feature-nav-number {
    background: var(--primary); color: var(--primary-foreground);
  }
  .feature-nav-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .feature-nav-copy strong { font-size: 12px; font-weight: 620; line-height: 1.35; }
  .feature-nav-copy > span { color: var(--muted-foreground); font-size: 10.5px; }
  .feature-nav-all {
    margin-top: auto; border-top: 1px solid var(--border); border-radius: 0 0 8px 8px;
  }
  .feature-aside { padding-bottom: 9px; }
  .feature-flow-list {
    flex: 1; min-height: 0; overflow-y: auto; padding: 0 3px; overscroll-behavior: contain;
  }
  .feature-flow-card { padding: 0 5px 12px; }
  .feature-flow-heading { padding: 3px 4px 10px; border-bottom: 1px solid var(--border); }
  .feature-flow-heading > span {
    color: var(--rename-mark); font-size: 10px; font-weight: 650; letter-spacing: .04em;
  }
  .feature-flow-heading h2 { margin: 3px 0 0; font-size: 15px; line-height: 1.35; }
  .feature-flow-summary {
    margin: 6px 0 0; color: var(--muted-foreground); font-size: 11px; line-height: 1.5;
  }
  .core-change {
    margin: 10px 1px 8px; padding: 9px 10px; border-left: 3px solid var(--primary);
    border-radius: 0 7px 7px 0; background: color-mix(in oklab, var(--primary) 6%, var(--card));
  }
  .core-change > span { color: var(--rename-mark); font-size: 10px; font-weight: 700; }
  .core-change p { margin: 3px 0 0; font-size: 11.5px; font-weight: 560; line-height: 1.5; }
  .feature-flow-chart {
    margin: 10px 1px 9px; padding: 9px; border: 1px solid var(--border); border-radius: 11px;
    background: color-mix(in oklab, var(--secondary) 34%, var(--card));
  }
  .feature-diagram-heading {
    display: flex; align-items: baseline; justify-content: space-between; gap: 6px;
    margin: 0 1px 8px; color: var(--foreground); font-size: 10.5px;
  }
  .feature-diagram-heading strong { font-weight: 700; }
  .feature-diagram-heading span { color: var(--muted-foreground); font-size: 9.5px; }
  .feature-diagram-track { display: flex; flex-direction: column; }
  .feature-step { position: relative; }
  .feature-step-node {
    display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 9px;
    padding: 9px 8px; border: 1px solid var(--border); border-left: 3px solid var(--primary);
    border-radius: 9px; background: var(--card);
    box-shadow: 0 1px 2px color-mix(in oklab, var(--foreground) 5%, transparent);
  }
  .feature-step-content { min-width: 0; }
  .feature-step-kicker {
    display: block; margin: 0 0 2px; color: var(--primary); font-size: 9px;
    font-weight: 700; letter-spacing: .02em;
  }
  .feature-step-number {
    display: grid; width: 24px; height: 24px; place-items: center; border-radius: 8px;
    background: color-mix(in oklab, var(--primary) 11%, var(--card));
    color: var(--primary); font-family: var(--mono); font-size: 10px; font-weight: 750;
  }
  .feature-step h3 {
    margin: 0; color: var(--foreground); font-size: 11.5px; font-weight: 680; line-height: 1.4;
  }
  .feature-step-change {
    margin: 3px 0 5px; color: var(--muted-foreground); font-size: 10.5px; line-height: 1.45;
  }
  .feature-step-core-files { margin: 3px 0 0 -4px; }
  .feature-svg-figure {
    margin: 10px 1px 8px; padding: 9px; border: 1px solid var(--border); border-radius: 11px;
    background: color-mix(in oklab, var(--secondary) 34%, var(--card));
  }
  .feature-svg-figure > figcaption {
    display: flex; align-items: baseline; justify-content: space-between; gap: 6px;
    margin: 0 1px 8px; color: var(--foreground); font-size: 10.5px;
  }
  .feature-svg-figure > figcaption strong { font-weight: 700; }
  .feature-svg-figure > figcaption span { color: var(--muted-foreground); font-size: 9.5px; }
  .feature-svg-diagram { display: block; width: 100%; height: auto; overflow: visible; }
  .feature-svg-edge {
    fill: none; stroke: color-mix(in oklab, var(--primary) 60%, var(--muted-foreground));
    stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
  }
  .feature-svg-edges marker path { fill: var(--primary); }
  .feature-svg-edge-label {
    fill: var(--muted-foreground); font-family: var(--sans); font-size: 9px;
    paint-order: stroke; stroke: var(--card); stroke-linejoin: round; stroke-width: 5px;
  }
  .feature-svg-node rect:first-of-type {
    fill: var(--card); stroke: var(--border); stroke-width: 1.1;
  }
  .feature-svg-node .feature-svg-node-accent { fill: var(--primary); stroke: none; }
  .feature-svg-kind {
    fill: var(--primary); font-family: var(--sans); font-size: 9px; font-weight: 700;
  }
  .feature-svg-label {
    fill: var(--foreground); font-family: var(--sans); font-size: 12px; font-weight: 680;
  }
  .feature-svg-detail {
    fill: var(--muted-foreground); font-family: var(--sans); font-size: 9.5px;
  }
  .feature-svg-node-link { cursor: pointer; outline: none; }
  .feature-svg-node-link:hover .feature-svg-node rect:first-of-type,
  .feature-svg-node-link:focus-visible .feature-svg-node rect:first-of-type {
    stroke: var(--ring); stroke-width: 2;
  }
  .feature-core-paths {
    margin: 6px 1px 8px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--code-bg);
  }
  .feature-core-paths > summary {
    padding: 7px 9px; cursor: pointer; color: var(--muted-foreground);
    font-size: 10.5px; font-weight: 600;
  }
  .feature-core-paths[open] > summary { border-bottom: 1px solid var(--border); }
  .feature-core-step-list { padding: 8px; }
  .feature-flow-arrow {
    display: flex; height: 23px; align-items: center; margin-left: 10px;
    color: color-mix(in oklab, var(--primary) 70%, var(--muted-foreground));
  }
  .feature-flow-arrow svg { width: 22px; height: 22px; overflow: visible; }
  .feature-flow-arrow path {
    fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round;
    stroke-width: 2.2;
  }
  .feature-file-row {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 8px;
    margin: 2px 0; padding: 6px 7px; border: 1px solid transparent; border-radius: 7px;
    color: var(--foreground); text-decoration: none;
  }
  .feature-file-row:hover { background: var(--secondary); }
  .feature-file-row.active {
    background: color-mix(in oklab, var(--primary) 8%, var(--card));
    border-color: color-mix(in oklab, var(--primary) 20%, var(--border));
  }
  .feature-file-path {
    overflow-wrap: anywhere; font-family: var(--mono); font-size: 10.5px; line-height: 1.4;
  }
  .feature-file-stats {
    display: flex; gap: 4px; font-family: var(--mono); font-size: 9.5px;
    font-style: normal; white-space: nowrap;
  }
  .feature-file-stats i { font-style: normal; }
  .feature-file-summary {
    grid-column: 1 / -1; color: var(--muted-foreground); font-size: 10.5px; line-height: 1.4;
  }
  .feature-step-core-files .feature-file-row { margin: 2px 0; padding: 5px 5px; }
  .feature-support {
    margin: 5px 2px 7px; border: 1px solid var(--border); border-radius: 7px;
    background: var(--code-bg);
  }
  .feature-support > summary {
    padding: 6px 8px; cursor: pointer; color: var(--muted-foreground);
    font-size: 10.5px; font-weight: 600;
  }
  .feature-support[open] > summary { border-bottom: 1px solid var(--border); }
  .feature-support .feature-file-row { margin: 2px 4px; }
  .feature-detail-toggle {
    width: 100%; margin-top: 4px; padding: 7px 8px; border: 1px solid var(--border);
    border-radius: 7px; background: var(--secondary); cursor: pointer;
    color: var(--foreground); font-size: 10.5px; font-weight: 600;
  }
  .feature-detail-toggle:hover { border-color: var(--ring); background: var(--card); }
  [hidden] { display: none !important; }

  @media (max-width: 1100px) {
    .feature-grid { grid-template-columns: 180px minmax(265px, 320px) minmax(0, 1fr); }
  }
  @media (max-width: 760px) {
    .feature-grid {
      grid-template-columns: minmax(0, 1fr); grid-template-rows: 180px 260px minmax(0, 1fr);
    }
    .feature-nav { flex-direction: row; overflow-x: auto; overflow-y: hidden; }
    .feature-nav-heading { display: none; }
    .feature-nav-button { flex: 0 0 220px; align-content: start; }
    .feature-nav-all { margin-top: 0; border-top: 0; border-left: 1px solid var(--border); }
  }
"""

FEATURE_SCRIPT = """
  var featureButtons = Array.prototype.slice.call(document.querySelectorAll('.feature-nav-button'));
  var featureDetailButtons = Array.prototype.slice.call(
    document.querySelectorAll('.feature-detail-toggle')
  );
  var featureCards = Array.prototype.slice.call(document.querySelectorAll('.feature-flow-card'));
  var featureSections = sections.filter(function (section) {
    return section.hasAttribute('data-feature-groups');
  });
  var featureTree = document.querySelector('.feature-aside .tree');
  var featureFlowList = document.querySelector('.feature-flow-list');
  var selectedFeatureIndex = '0';
  var showFeatureSupport = false;
  function selectFeature(index, includeSupport) {
    var showAll = index === 'all';
    selectedFeatureIndex = String(index);
    showFeatureSupport = Boolean(includeSupport);
    featureButtons.forEach(function (button) {
      var selected = button.dataset.featureIndex === selectedFeatureIndex;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    if (featureTree && featureFlowList) {
      featureTree.hidden = !showAll;
      featureFlowList.hidden = showAll;
    }
    featureCards.forEach(function (card) {
      var selectedCard = !showAll && card.dataset.featureIndex === selectedFeatureIndex;
      card.hidden = !selectedCard;
      var supportDetails = card.querySelector('.feature-support');
      if (supportDetails) { supportDetails.open = selectedCard && showFeatureSupport; }
      var detailButton = card.querySelector('.feature-detail-toggle');
      if (detailButton) {
        detailButton.textContent = showFeatureSupport
          ? detailButton.dataset.coreLabel
          : detailButton.dataset.allLabel;
      }
    });
    featureSections.forEach(function (section) {
      var groups = (section.dataset.featureGroups || '').split(' ');
      var coreGroups = (section.dataset.featureCoreGroups || '').split(' ');
      var belongsToFeature = groups.indexOf(selectedFeatureIndex) !== -1;
      var belongsToCore = coreGroups.indexOf(selectedFeatureIndex) !== -1;
      section.hidden = !showAll && (!belongsToFeature || (!showFeatureSupport && !belongsToCore));
    });
    activeId = null;
    scroller.scrollTop = 0;
    if (featureFlowList) { featureFlowList.scrollTop = 0; }
    window.requestAnimationFrame(syncActive);
  }
  featureButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectFeature(button.dataset.featureIndex, false);
    });
  });
  featureDetailButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectFeature(button.dataset.featureIndex, !showFeatureSupport);
    });
  });
  featureCards.forEach(function (card) {
    var supportDetails = card.querySelector('.feature-support');
    if (!supportDetails) { return; }
    supportDetails.addEventListener('toggle', function () {
      if (!card.hidden && card.dataset.featureIndex === selectedFeatureIndex) {
        selectFeature(card.dataset.featureIndex, supportDetails.open);
      }
    });
  });
  if (featureButtons.length) { selectFeature('0', false); }
"""
