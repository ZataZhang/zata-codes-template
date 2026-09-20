/**
 * 原型目录（Hub）渲染逻辑。
 *
 * 条目只从 `prototype-registry.js` 读取，本文件不内联任何原型数据。
 * 点击语义（见 prototype-hub-contract.md）：
 * - 缩略图/名称：直接打开原型（新标签页，保留 Hub 的搜索/筛选/滚动状态）
 * - 行内其他区域：切换右侧详情抽屉
 * - 链接点击不得同时触发行选择
 */
(() => {
  const prototypes = window.PROTOTYPE_REGISTRY ?? [];
  const FORM_LABELS = { "code-native": "交互原型", "image-state": "图片原型" };

  const state = { query: "", project: "all", module: "all", form: "all", availability: "all", selectedId: "" };

  const el = {
    catalog: document.querySelector("#catalog"),
    empty: document.querySelector("#empty"),
    detail: document.querySelector("#detail"),
    search: document.querySelector("#search"),
    project: document.querySelector("#project"),
    module: document.querySelector("#module"),
    form: document.querySelector("#form"),
    availability: document.querySelector("#availability"),
    total: document.querySelector("[data-total]"),
    countCode: document.querySelector("[data-count-code]"),
    countImage: document.querySelector("[data-count-image]"),
    countAvailable: document.querySelector("[data-count-available]"),
    heading: document.querySelector("[data-heading]"),
    filters: [...document.querySelectorAll("[data-filter]")],
  };

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>'"]/g, (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);

  /** 缩略图：加载失败退回占位块，不留破图。 */
  const thumbMarkup = (prototype, className) =>
    prototype.preview
      ? `<img class="${className}" src="${escapeHtml(prototype.preview)}" alt="${escapeHtml(prototype.title)} 预览" loading="lazy"
           onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'${className} placeholder',textContent:'预览缺失'}))">`
      : `<span class="${className} placeholder">HTML</span>`;

  const matches = (prototype) => {
    const text = `${prototype.title} ${prototype.description} ${prototype.project} ${prototype.module} ${(prototype.flows ?? []).join(" ")}`.toLowerCase();
    return (
      (!state.query || text.includes(state.query)) &&
      (state.project === "all" || prototype.project === state.project) &&
      (state.module === "all" || prototype.module === state.module) &&
      (state.form === "all" || prototype.form === state.form) &&
      (state.availability === "all" || prototype.availability === state.availability)
    );
  };

  const statusPill = (prototype) =>
    prototype.availability === "available"
      ? '<span class="pill success">可用</span>'
      : '<span class="pill danger">不可用</span>';

  const renderDetail = () => {
    const prototype = prototypes.find((candidate) => candidate.id === state.selectedId);
    if (!prototype) {
      el.detail.innerHTML = '<p class="empty">左侧选择一个原型查看详情。</p>';
      return;
    }
    const openAction = prototype.availability === "available"
      ? `<a class="primary" href="${escapeHtml(prototype.entry)}" target="_blank" rel="noopener">打开原型</a>`
      : `<a class="secondary" href="${escapeHtml(prototype.entry)}" target="_blank" rel="noopener">仍要打开（已知失效）</a>`;
    const sourceAction = prototype.source
      ? `<a class="secondary" href="${escapeHtml(prototype.source)}">查看说明</a>`
      : '<span class="secondary" aria-disabled="true">暂无说明</span>';

    el.detail.innerHTML = `
      ${thumbMarkup(prototype, "detail-preview")}
      <h2>${escapeHtml(prototype.title)}</h2>
      <p>${escapeHtml(prototype.description)}</p>
      <p class="detail-project">${statusPill(prototype)}
        <span class="pill neutral">${escapeHtml(FORM_LABELS[prototype.form] ?? prototype.form)}</span>
        <span class="pill neutral">${escapeHtml(prototype.project)}</span>
      </p>
      <dl>
        <div><dt>所属模块</dt><dd>${escapeHtml(prototype.module)}</dd></div>
        <div><dt>验证层级</dt><dd>${escapeHtml(prototype.validationLevel)}</dd></div>
        <div><dt>版本</dt><dd>${escapeHtml(prototype.version)}</dd></div>
        <div><dt>更新时间</dt><dd>${escapeHtml(prototype.updatedAt)}</dd></div>
        <div><dt>说明来源</dt><dd>${prototype.source ? `<a href="${escapeHtml(prototype.source)}">${escapeHtml(prototype.sourceLabel ?? "查看")}</a>` : "—"}</dd></div>
        <div><dt>旁车</dt><dd>${prototype.provenance ? `<code>${escapeHtml(prototype.provenance)}</code>` : "—"}</dd></div>
      </dl>
      ${(prototype.flows ?? []).length ? `<p style="margin-top:16px;font-weight:700;color:var(--ink)">主要流程</p><ul>${prototype.flows.map((flow) => `<li>${escapeHtml(flow)}</li>`).join("")}</ul>` : ""}
      <div class="detail-actions">${sourceAction}${openAction}</div>
      ${prototype.availabilityNote ? `<p class="detail-alert">不可用原因：${escapeHtml(prototype.availabilityNote)}</p>` : ""}
      <p class="detail-note">Hub 只负责原型资产目录：列出有哪些原型、属于哪里、什么形式、能否打开、如何追溯来源。PRD 执行状态、Issue、CI/CD 与运行监控不属于这里。</p>`;
  };

  const render = () => {
    const visible = prototypes.filter(matches);
    if (!visible.some((prototype) => prototype.id === state.selectedId)) {
      state.selectedId = visible[0]?.id ?? "";
    }
    el.empty.hidden = visible.length > 0;
    el.catalog.innerHTML = visible
      .map((prototype) => `
        <tr data-id="${escapeHtml(prototype.id)}" tabindex="0" aria-selected="${prototype.id === state.selectedId}"
            class="${prototype.id === state.selectedId ? "selected" : ""}">
          <td><a href="${escapeHtml(prototype.entry)}" target="_blank" rel="noopener"
                 aria-label="打开 ${escapeHtml(prototype.title)}（新标签）">${thumbMarkup(prototype, "thumb")}</a></td>
          <td><a class="title-link" href="${escapeHtml(prototype.entry)}" target="_blank" rel="noopener"
                 aria-label="打开 ${escapeHtml(prototype.title)}（新标签）">${escapeHtml(prototype.title)}</a></td>
          <td>${escapeHtml(prototype.project)}</td>
          <td>${escapeHtml(prototype.module)}</td>
          <td><span class="pill neutral">${escapeHtml(FORM_LABELS[prototype.form] ?? prototype.form)}</span></td>
          <td>${escapeHtml(prototype.updatedAt)}</td>
          <td>${statusPill(prototype)}</td>
        </tr>`)
      .join("");
    renderDetail();
  };

  const addOptions = (select, values) =>
    [...new Set(values)].sort().forEach((value) => select.add(new Option(value, value)));

  // 侧栏计数与筛选选项都从 registry 推导
  addOptions(el.project, prototypes.map((prototype) => prototype.project));
  addOptions(el.module, prototypes.map((prototype) => prototype.module));
  el.total.textContent = String(prototypes.length);
  el.countCode.textContent = String(prototypes.filter((prototype) => prototype.form === "code-native").length);
  el.countImage.textContent = String(prototypes.filter((prototype) => prototype.form === "image-state").length);
  el.countAvailable.textContent = String(prototypes.filter((prototype) => prototype.availability === "available").length);

  el.search.addEventListener("input", (event) => { state.query = event.target.value.trim().toLowerCase(); render(); });
  [["project", el.project], ["module", el.module], ["form", el.form], ["availability", el.availability]].forEach(
    ([key, select]) => select.addEventListener("change", (event) => { state[key] = event.target.value; render(); }),
  );

  el.catalog.addEventListener("click", (event) => {
    if (event.target.closest("a,button")) return;
    const row = event.target.closest("[data-id]");
    if (row) { state.selectedId = row.dataset.id; render(); }
  });
  el.catalog.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (event.target.closest("a,button")) return;
    const row = event.target.closest("[data-id]");
    if (!row) return;
    event.preventDefault();
    state.selectedId = row.dataset.id;
    render();
  });

  el.filters.forEach((button) =>
    button.addEventListener("click", () => {
      const filter = button.dataset.filter;
      state.form = FORM_LABELS[filter] ? filter : "all";
      state.availability = filter === "available" ? "available" : "all";
      el.form.value = state.form;
      el.availability.value = state.availability;
      el.heading.textContent = button.dataset.label ?? "全部原型";
      el.filters.forEach((candidate) => candidate.classList.toggle("active", candidate === button));
      render();
    }),
  );

  // 可复制 URL：prototype-hub.html?prototype=<id>
  const requestedId = new URLSearchParams(window.location.search).get("prototype");
  if (requestedId && prototypes.some((prototype) => prototype.id === requestedId)) {
    state.selectedId = requestedId;
  }
  render();
})();
