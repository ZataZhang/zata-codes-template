/**
 * 只读文件与改动查看器的前端交互。
 *
 * 数据全部来自本机只读接口（/api/info、/api/tree、/api/file、/api/changes、/api/diff、
 * /api/markdown），页面不做任何写入，也不做心跳轮询——一旦开始轮询，服务端的空闲自动
 * 回收就会静默失效（见 docs/guides/file-viewer.md 的回收策略一节）。
 *
 * 改动视图按 `git status` 的三段口径展示：已暂存、未暂存、未跟踪。**同一个文件可以同时
 * 出现在两段里**（暂存了几个 hunk 之后又改了几行），因此条目的身份是「路径 + 分区」而不是
 * 路径；选中态、请求参数与直达路径的归属都按这个二元组走。
 *
 * 两个视图各自记一份「上一次看的那一个」（成功读到内容才记），切视图时还原，而不是每次
 * 都回到空态。改动视图头部的「查看文件」是显式指定，优先于记忆。
 *
 * 预览默认关闭：文件视图打开任何文件先看到的是源码。Markdown 由服务端渲染、由「预览」
 * 开关按需取回；HTML 不内联渲染，只在新标签页里打开服务端原样供出的文件（/raw/）。哪
 * 个文件支持哪种预览由服务端在 /api/file 的 `preview` 字段里给出，本文件不复制那张后缀表。
 */
(() => {
  "use strict";

  const FILES_VIEW = "files";
  const DIFF_VIEW = "diff";
  const SOURCE_MODE = "source";
  const PREVIEW_MODE = "preview";

  const elements = {
    repoName: document.getElementById("repo-name"),
    branchChip: document.getElementById("branch-chip"),
    tabFiles: document.getElementById("tab-files"),
    tabDiff: document.getElementById("tab-diff"),
    diffCount: document.getElementById("diff-count"),
    filterInput: document.getElementById("filter-input"),
    treeTitle: document.getElementById("tree-title"),
    treeNote: document.getElementById("tree-note"),
    treeBody: document.getElementById("tree-body"),
    viewerPath: document.getElementById("viewer-path"),
    copyPathButton: document.getElementById("copy-path"),
    previewSwitch: document.getElementById("preview-switch"),
    tabSource: document.getElementById("tab-source"),
    tabPreview: document.getElementById("tab-preview"),
    openFileButton: document.getElementById("open-file"),
    openExternal: document.getElementById("open-external"),
    viewerMeta: document.getElementById("viewer-meta"),
    viewerBody: document.getElementById("viewer-body"),
    statusDot: document.getElementById("status-dot"),
    statusText: document.getElementById("status-text"),
    statusHint: document.getElementById("status-hint"),
  };

  /** 页面的全部可变状态；渲染只读它，用户操作只改它。默认落在改动视图。 */
  const viewState = {
    view: DIFF_VIEW,
    selectedPath: "",
    selectedSection: "",
    collapsedDirectories: new Set(),
    filterText: "",
    filePaths: [],
    changedSections: [],
    isDisconnected: false,
    // --- 两个视图各自记住「上一次看的那一个」，切视图时还原（见 switchView） ---
    /** 文件视图里上一次成功读到正文的路径；空串表示还没看过任何文件。 */
    lastFileViewPath: "",
    /** 改动视图里上一次成功读到改动的「路径 + 分区」；分区一起记，否则同一文件的两段会串。 */
    lastDiffViewSelection: { path: "", section: "" },
    // --- 当前选中文件的预览状态，换文件或切视图时由 resetFilePreview 清空 ---
    /** 当前正文来自 /api/file 的应答；没有可显示正文时为 null。 */
    loadedFile: null,
    /** 服务端给出的预览能力：{mode: 'markdown'} / {mode: 'external', url} / null。 */
    previewDescriptor: null,
    /** 当前显示源码还是预览。 */
    renderMode: SOURCE_MODE,
    /** 已取回的 Markdown 预览片段；null 表示还没取过。 */
    markdownHtml: null,
  };

  /**
   * 请求一个只读接口。
   * @param {string} requestUrl 接口地址。
   * @returns {Promise<{status: number, body: object}>} 应答状态码与 JSON 正文。
   */
  async function requestJson(requestUrl) {
    const response = await fetch(requestUrl, { headers: { Accept: "application/json" } });
    const responseBody = await response.json();
    return { status: response.status, body: responseBody };
  }

  /**
   * 切换到「服务已退出」状态：左树置灰不可点，内容区给出重新连接指引。
   * @param {string} failureMessage 失败说明，用于状态条。
   */
  function enterDisconnectedState(failureMessage) {
    viewState.isDisconnected = true;
    elements.treeBody.classList.add("is-stale");
    elements.statusDot.classList.add("down");
    elements.statusText.textContent = "服务已退出 · 运行 just view 重新连接";
    renderDisconnectedNotice(failureMessage);
  }

  /**
   * 在内容区渲染服务退出提示。
   * @param {string} failureMessage 失败说明。
   */
  function renderDisconnectedNotice(failureMessage) {
    elements.viewerPath.textContent = "服务已退出";
    elements.copyPathButton.hidden = true;
    elements.copyPathButton.dataset.copied = "false";
    renderPreviewControls(null);
    elements.viewerMeta.textContent = "";
    elements.viewerBody.replaceChildren(
      buildNotice({
        isFailure: true,
        title: "服务已退出",
        paragraphs: [
          "查看器空闲到时限后会自动退出（默认 30 分钟无任何请求），也可以用 just view --stop 立刻回收。",
          "在仓库里重新执行 just view 会新起一个实例并打开新标签页，本页不再自动恢复。",
        ],
        hint: failureMessage ? `本次请求失败原因：${failureMessage}` : "",
      })
    );
  }

  /**
   * 转义要拼进 innerHTML 的文本。
   *
   * 提示块的段落走 innerHTML，而界面上的路径来自 git、文件名本身可以含 `& < >`
   * （例如 `a<b.md`），不转义会让提示块结构错乱。
   * @param {string} rawText 原始文本。
   * @returns {string} 转义后的文本。
   */
  function escapeHtmlText(rawText) {
    return rawText
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  /**
   * 构造一个内容区提示块。
   * @param {{isFailure?: boolean, title: string, paragraphs: string[], hint?: string}} noticeInput 提示内容。
   * @returns {HTMLElement} 提示块节点。
   */
  function buildNotice(noticeInput) {
    const noticeNode = document.createElement("div");
    noticeNode.className = noticeInput.isFailure ? "notice down" : "notice";
    const titleNode = document.createElement("h3");
    titleNode.textContent = noticeInput.title;
    noticeNode.append(titleNode);
    for (const paragraphText of noticeInput.paragraphs) {
      const paragraphNode = document.createElement("p");
      paragraphNode.innerHTML = paragraphText;
      noticeNode.append(paragraphNode);
    }
    if (noticeInput.hint) {
      const hintNode = document.createElement("p");
      hintNode.textContent = noticeInput.hint;
      noticeNode.append(hintNode);
    }
    return noticeNode;
  }

  /**
   * 执行一次接口调用并把网络失败统一转成「服务已退出」。
   * @param {() => Promise<unknown>} action 需要保护的调用。
   * @returns {Promise<boolean>} 调用是否成功完成。
   */
  async function guardAgainstServiceExit(action) {
    if (viewState.isDisconnected) {
      return false;
    }
    try {
      await action();
      return true;
    } catch (networkError) {
      enterDisconnectedState(networkError instanceof Error ? networkError.message : "");
      return false;
    }
  }

  /**
   * 读取 URL 上的初始视图与直达路径。
   *
   * 直达路径不带分区：一个路径可能同时出现在多个分区里，归属在改动列表加载完之后
   * 按分区顺序解析（见 `resolveSectionForPath`）。
   */
  function applyInitialQueryParameters() {
    const searchParameters = new URLSearchParams(window.location.search);
    const requestedView = searchParameters.get("view");
    if (requestedView === DIFF_VIEW || requestedView === FILES_VIEW) {
      viewState.view = requestedView;
    }
    viewState.selectedPath = searchParameters.get("path") || "";
  }

  /**
   * 初始化页面：拉取仓库信息与文件树，然后按初始状态渲染。
   */
  async function initializeViewer() {
    applyInitialQueryParameters();
    const didLoad = await guardAgainstServiceExit(async () => {
      const infoResponse = await requestJson("/api/info");
      elements.repoName.textContent = infoResponse.body.repo_name;
      elements.branchChip.textContent = infoResponse.body.branch;
      window.document.title = `${infoResponse.body.repo_name} · 只读查看器`;

      const treeResponse = await requestJson("/api/tree");
      viewState.filePaths = treeResponse.body.paths;
    });
    if (!didLoad) {
      return;
    }

    expandToSelectedPath();
    if (viewState.view === DIFF_VIEW) {
      await loadChangedFiles();
    } else {
      renderTree();
      if (viewState.selectedPath) {
        await selectPath(viewState.selectedPath);
      } else {
        renderPlaceholder();
      }
    }
    renderViewTabs();
  }

  /**
   * 展开直达路径上的全部祖先目录。
   */
  function expandToSelectedPath() {
    if (!viewState.selectedPath) {
      return;
    }
    const pathSegments = viewState.selectedPath.split("/");
    for (let segmentIndex = 0; segmentIndex < pathSegments.length; segmentIndex += 1) {
      viewState.collapsedDirectories.delete(pathSegments.slice(0, segmentIndex + 1).join("/"));
    }
  }

  /**
   * 找出某个路径当前所属的分区，用于给不带分区的直达路径定归属。
   *
   * 同一路径可能同时在「已暂存」与「未暂存」两段里，这里取分区顺序上的第一个（已暂存
   * 优先），与列表的展示顺序一致——点开哪一段都能看到改动，但不能没有确定答案。
   * @param {string} repositoryPath 仓库相对路径。
   * @returns {string} 分区取值；该路径不在任何分区里时为空串。
   */
  function resolveSectionForPath(repositoryPath) {
    const matchedSection = viewState.changedSections.find((section) =>
      section.files.some((changedFile) => changedFile.path === repositoryPath)
    );
    return matchedSection ? matchedSection.section : "";
  }

  /**
   * 变更是否仍出现在改动列表里——路径与分区都要对得上。
   * @param {string} repositoryPath 仓库相对路径。
   * @param {string} sectionName 分区取值。
   * @returns {boolean} 该条目当前是否可见。
   */
  function isSelectableChange(repositoryPath, sectionName) {
    return viewState.changedSections.some(
      (section) =>
        section.section === sectionName &&
        section.files.some((changedFile) => changedFile.path === repositoryPath)
    );
  }

  /**
   * 读取三个分区的改动文件列表。
   */
  async function loadChangedFiles() {
    const didLoad = await guardAgainstServiceExit(async () => {
      const changesResponse = await requestJson("/api/changes");
      if (changesResponse.status !== 200) {
        viewState.changedSections = [];
        renderNotice(buildNotice({ title: "无法列出改动", paragraphs: [changesResponse.body.error] }));
        return;
      }
      viewState.changedSections = changesResponse.body.sections;
      elements.diffCount.textContent = String(changesResponse.body.totals.files);
      elements.diffCount.hidden = false;
      // 增删只跟在提供统计的分区后面：未跟踪那一段的数拿不到，就不把它的文件数混进
      // 一个看起来覆盖全部的 `+N -M` 里。
      elements.statusHint.textContent = viewState.changedSections
        .map((section) =>
          section.stats_available
            ? `${section.label} ${section.totals.files} (+${section.totals.add} -${section.totals.del})`
            : `${section.label} ${section.totals.files}`
        )
        .join(" · ");
    });
    if (!didLoad) {
      return;
    }
    renderTree();
    if (!viewState.selectedPath) {
      renderPlaceholder();
      return;
    }
    // 直达路径（或切换视图前的选中项）不带分区时，按分区顺序补一个。
    const resolvedSection =
      viewState.selectedSection || resolveSectionForPath(viewState.selectedPath);
    if (resolvedSection && isSelectableChange(viewState.selectedPath, resolvedSection)) {
      await selectPath(viewState.selectedPath, resolvedSection);
      return;
    }
    // 还原过来的那条改动已经不在列表里（提交了、撤销了、换过 worktree）：清掉选中态
    // 再报空态。不清的话「内容区是空态、selectedPath 却还指着某个文件」，复制与跳转
    // 按钮的开关就跟内容对不上了。
    viewState.selectedPath = "";
    viewState.selectedSection = "";
    renderPlaceholder();
  }

  /**
   * 渲染视图切换按钮。
   */
  function renderViewTabs() {
    const isDiffView = viewState.view === DIFF_VIEW;
    elements.tabFiles.setAttribute("aria-selected", String(!isDiffView));
    elements.tabDiff.setAttribute("aria-selected", String(isDiffView));
    const treeTitleNode = document.createElement("b");
    treeTitleNode.textContent = isDiffView ? "改动文件" : "文件树";
    elements.treeTitle.replaceChildren(treeTitleNode);
  }

  /**
   * 写内容区头部的路径，并同步「复制路径」与「查看文件」的可见性。
   *
   * 头部没有真实路径（占位符、服务已退出、提示块）时必须把按钮收起来：留一个复制
   * 不到东西的按钮比没有按钮更糟。「查看文件」只在**改动视图**里有意义——文件视图本来
   * 就在看正文，那里摆一个跳回自己的按钮是纯噪音。两个按钮都取
   * `viewState.selectedPath`，因此这里不另存一份路径，只负责显示与按钮的开关。
   * @param {string} repositoryPath 仓库相对路径；空串表示只显示占位符。
   */
  function setViewerPath(repositoryPath) {
    elements.viewerPath.textContent = repositoryPath || "—";
    elements.copyPathButton.hidden = !repositoryPath;
    elements.copyPathButton.dataset.copied = "false";
    elements.openFileButton.hidden = !repositoryPath || viewState.view !== DIFF_VIEW;
  }

  /**
   * 把内容区当前文件的仓库相对路径复制到剪贴板。
   */
  async function copyCurrentViewerPath() {
    const pathToCopy = viewState.selectedPath;
    if (!pathToCopy) {
      return;
    }
    if (!navigator.clipboard) {
      elements.statusHint.textContent = "当前环境不支持剪贴板写入，请手动选中路径复制";
      return;
    }
    try {
      await navigator.clipboard.writeText(pathToCopy);
    } catch (copyError) {
      elements.statusHint.textContent = `复制路径失败：${
        copyError instanceof Error ? copyError.message : copyError
      }，请手动选中路径复制`;
      return;
    }
    // 成功后只做图标反馈，不动状态条：那行的语法高亮说明是常驻信息，覆盖掉反而丢信息。
    elements.copyPathButton.dataset.copied = "true";
    window.setTimeout(() => {
      elements.copyPathButton.dataset.copied = "false";
    }, 1200);
  }

  /**
   * 在内容区渲染一个提示块。
   * @param {HTMLElement} noticeNode 提示块节点。
   */
  function renderNotice(noticeNode) {
    setViewerPath("");
    // 提示块不是文件正文，预览控件必须跟着收起：留一个点到没有内容的开关比没有更糟。
    renderPreviewControls(null);
    elements.viewerMeta.textContent = "";
    elements.viewerBody.replaceChildren(noticeNode);
  }

  /**
   * 渲染未选中文件时的空态。
   */
  function renderPlaceholder() {
    if (viewState.view === DIFF_VIEW) {
      const hasChangedFiles = countChangedFiles() > 0;
      renderNotice(
        buildNotice({
          title: hasChangedFiles ? "选择一个改动文件" : "工作区没有改动",
          paragraphs: [
            hasChangedFiles
              ? "左侧按「已暂存 / 未暂存 / 未跟踪」分段列出有改动的文件，点开任意一个查看逐行改动。"
              : "索引与工作区都与 HEAD 一致，也没有未跟踪文件。",
          ],
          hint: hasChangedFiles
            ? "提示：同一个文件可以同时出现在两段里——暂存之后又改的那几行属于未暂存。"
            : "",
        })
      );
      return;
    }
    renderNotice(
      buildNotice({
        title: "选择一个文件",
        paragraphs: ["左侧是本仓库的文件树，点开任意文件即可在右侧查看带行号与语法高亮的正文。"],
        hint: "快捷键：f 切文件视图、d 切改动视图、/ 聚焦过滤框。",
      })
    );
  }

  /**
   * 统计三个分区里的改动文件总数。
   * @returns {number} 改动文件数。
   */
  function countChangedFiles() {
    return viewState.changedSections.reduce((fileCount, section) => {
      return fileCount + section.files.length;
    }, 0);
  }

  /**
   * 渲染左侧树；两个视图共用同一套目录树，只有叶子行与空态文案不同。
   *
   * 改动视图先按分区分段、段内再按目录分组，而不是铺成一长条扁平行：改动文件动辄成百
   * 上千，扁平列表既看不出改动落在哪些目录，也分不清哪几行已经进过索引。
   */
  function renderTree() {
    const isDiffView = viewState.view === DIFF_VIEW;
    const filterText = viewState.filterText.trim().toLowerCase();
    const treeFragment = document.createDocumentFragment();

    if (isDiffView) {
      appendChangedSections(treeFragment, filterText);
      elements.treeNote.textContent = `${countChangedFiles()} 个文件`;
    } else {
      const directoryTree = buildDirectoryTree(
        viewState.filePaths.map((filePath) => ({ path: filePath }))
      );
      elements.treeNote.textContent = `${viewState.filePaths.length} 个文件`;
      appendDirectoryChildren(treeFragment, directoryTree, 0, filterText);
    }

    if (!treeFragment.childNodes.length) {
      elements.treeBody.replaceChildren(buildTreeEmpty(emptyTreeMessage(isDiffView)));
      return;
    }
    elements.treeBody.replaceChildren(treeFragment);
  }

  /**
   * 按分区追加改动列表：每个分区一条标题行，后面跟该分区自己的目录树。
   *
   * 段内那棵树先建进临时片段再判断有没有内容——空分区（或被过滤掉全部分区的分区）不该
   * 留下一条孤零零的标题行。
   * @param {DocumentFragment} treeFragment 目标片段。
   * @param {string} filterText 小写过滤词。
   */
  function appendChangedSections(treeFragment, filterText) {
    for (const changedSection of viewState.changedSections) {
      const sectionFragment = document.createDocumentFragment();
      // 分区取值与「本段是否提供 +N -M」随条目一起进树：叶子行需要它们才能把「路径 +
      // 分区」这个身份还原出来、并按段决定统计列的显示，而递归渲染函数自己不知道当前
      // 在哪一段。
      appendDirectoryChildren(
        sectionFragment,
        buildDirectoryTree(
          changedSection.files.map((changedFile) => ({
            ...changedFile,
            section: changedSection.section,
            statsAvailable: changedSection.stats_available,
          }))
        ),
        0,
        filterText
      );
      if (!sectionFragment.childNodes.length) {
        continue;
      }
      treeFragment.append(buildChangedSectionHeader(changedSection));
      treeFragment.append(sectionFragment);
    }
  }

  /**
   * 构造一条分区标题行。
   * @param {{section: string, label: string, files: Array<object>}} changedSection 分区数据。
   * @returns {HTMLElement} 标题行节点。
   */
  function buildChangedSectionHeader(changedSection) {
    const headerNode = document.createElement("div");
    headerNode.className = "section-head";
    headerNode.dataset.section = changedSection.section;

    const labelNode = document.createElement("span");
    labelNode.className = "section-label";
    labelNode.textContent = changedSection.label;
    headerNode.append(labelNode);

    const countNode = document.createElement("span");
    countNode.className = "chip";
    countNode.textContent = String(changedSection.files.length);
    headerNode.append(countNode);
    return headerNode;
  }

  /**
   * 左树的空态文案。
   * @param {boolean} isDiffView 是否处于改动视图。
   * @returns {string} 空态说明。
   */
  function emptyTreeMessage(isDiffView) {
    if (!isDiffView) {
      return "没有匹配过滤条件的文件。";
    }
    return countChangedFiles()
      ? "没有匹配过滤条件的改动文件。"
      : "工作区没有改动文件。";
  }

  /**
   * 构造一个改动文件叶子行：状态徽标 + 文件名 + 增删统计。
   * 目录上下文由所在层级表达，行内不再重复完整路径。
   *
   * 统计列有三种状态：给出 `+N -M`、标成「二进制」（git 不逐行给）、以及整段不提供
   * （未跟踪那一段，git 的列表命令不报这个数）。后两者不能混：二进制是「有改动但数不出
   * 行」，不提供是「本轮没取」。
   * @param {{path: string, status: string, add: number|null, del: number|null, section: string, statsAvailable: boolean}} changedFile 改动文件（含所属分区与统计可用性）。
   * @param {number} depth 缩进层级。
   * @returns {HTMLElement} 条目节点。
   */
  function buildChangedFileRow(changedFile, depth) {
    const rowButton = document.createElement("button");
    rowButton.type = "button";
    rowButton.className = "node";
    rowButton.style.paddingLeft = `${8 + depth * 14}px`;
    rowButton.title = changedFile.path;
    rowButton.setAttribute(
      "aria-selected",
      String(
        changedFile.path === viewState.selectedPath &&
          changedFile.section === viewState.selectedSection
      )
    );
    rowButton.append(buildCaretPlaceholder());

    const badgeNode = document.createElement("span");
    badgeNode.className = `badge ${changedFile.status}`;
    badgeNode.textContent = changedFile.status;
    rowButton.append(badgeNode);

    const nameNode = document.createElement("span");
    nameNode.className = "name";
    const lastSlashIndex = changedFile.path.lastIndexOf("/");
    nameNode.textContent =
      lastSlashIndex >= 0 ? changedFile.path.slice(lastSlashIndex + 1) : changedFile.path;
    rowButton.append(nameNode);

    if (changedFile.statsAvailable) {
      const statNode = document.createElement("span");
      statNode.className = "stat";
      if (changedFile.add === null || changedFile.del === null) {
        const binaryNode = document.createElement("span");
        binaryNode.className = "badge";
        binaryNode.textContent = "二进制";
        statNode.append(binaryNode);
      } else {
        statNode.append(buildStatNode("add", `+${changedFile.add}`));
        statNode.append(buildStatNode("del", `-${changedFile.del}`));
      }
      rowButton.append(statNode);
    }

    rowButton.addEventListener("click", () => {
      void selectPath(changedFile.path, changedFile.section);
    });
    return rowButton;
  }

  /**
   * 构造一个增删统计节点。
   * @param {"add"|"del"} statKind 统计类型。
   * @param {string} statText 统计文本。
   * @returns {HTMLElement} 统计节点。
   */
  function buildStatNode(statKind, statText) {
    const statNode = document.createElement("span");
    statNode.className = statKind;
    statNode.textContent = statText;
    return statNode;
  }

  /**
   * 构造占位用的折叠箭头，让改动视图的条目与文件树条目左缘对齐。
   * @returns {HTMLElement} 占位节点。
   */
  function buildCaretPlaceholder() {
    const caretNode = document.createElement("span");
    caretNode.className = "caret";
    return caretNode;
  }

  /**
   * 构造文件树的空态节点。
   * @param {string} emptyMessage 空态说明。
   * @returns {HTMLElement} 空态节点。
   */
  function buildTreeEmpty(emptyMessage) {
    const emptyNode = document.createElement("div");
    emptyNode.className = "tree-empty";
    emptyNode.textContent = emptyMessage;
    return emptyNode;
  }

  /**
   * 把扁平的条目列表组装成目录树。
   *
   * 文件视图传 `{path}`，改动视图传改动文件对象；叶子节点把原条目留在 `payload` 里，
   * 于是两种叶子行都能从同一棵树渲染。
   * @param {Array<{path: string}>} treeEntries 每条含仓库相对路径。
   * @returns {{name: string, path: string, isDirectory: boolean, children: Map, payload: object|null}} 根节点。
   */
  function buildDirectoryTree(treeEntries) {
    const rootNode = {
      name: "",
      path: "",
      isDirectory: true,
      children: new Map(),
      payload: null,
    };
    for (const treeEntry of treeEntries) {
      const pathSegments = treeEntry.path.split("/");
      let currentNode = rootNode;
      for (let segmentIndex = 0; segmentIndex < pathSegments.length; segmentIndex += 1) {
        const pathSegment = pathSegments[segmentIndex];
        if (!currentNode.children.has(pathSegment)) {
          currentNode.children.set(pathSegment, {
            name: pathSegment,
            path: pathSegments.slice(0, segmentIndex + 1).join("/"),
            isDirectory: segmentIndex < pathSegments.length - 1,
            children: new Map(),
            payload: null,
          });
        }
        currentNode = currentNode.children.get(pathSegment);
      }
      currentNode.payload = treeEntry;
    }
    return rootNode;
  }

  /**
   * 递归追加目录下的可见节点。
   * @param {DocumentFragment} treeFragment 目标片段。
   * @param {{name: string, path: string, isDirectory: boolean, children: Map}} directoryNode 当前目录。
   * @param {number} depth 缩进层级。
   * @param {string} filterText 小写过滤词；非空时只保留命中路径及其祖先。
   */
  function appendDirectoryChildren(treeFragment, directoryNode, depth, filterText) {
    const sortedChildren = [...directoryNode.children.values()].sort(compareTreeNode);
    for (const childNode of sortedChildren) {
      if (!matchesFilter(childNode, filterText)) {
        continue;
      }
      if (childNode.isDirectory) {
        treeFragment.append(buildDirectoryRow(childNode, depth, filterText));
        if (!viewState.collapsedDirectories.has(childNode.path)) {
          appendDirectoryChildren(treeFragment, childNode, depth + 1, filterText);
        }
      } else if (viewState.view === DIFF_VIEW) {
        treeFragment.append(buildChangedFileRow(childNode.payload, depth));
      } else {
        treeFragment.append(buildFileRow(childNode, depth));
      }
    }
  }

  /**
   * 判断节点是否命中过滤条件；目录在本目录自身或任一后代命中时保留。
   * @param {{name: string, path: string, isDirectory: boolean, children: Map}} treeNode 待判定节点。
   * @param {string} filterText 小写过滤词。
   * @returns {boolean} 是否应当显示。
   */
  function matchesFilter(treeNode, filterText) {
    if (!filterText) {
      return true;
    }
    if (treeNode.path.toLowerCase().includes(filterText)) {
      return true;
    }
    if (!treeNode.isDirectory) {
      return false;
    }
    return [...treeNode.children.values()].some((childNode) =>
      matchesFilter(childNode, filterText)
    );
  }

  /**
   * 排序：目录在前，同类按名称排序。
   * @param {{name: string, isDirectory: boolean}} leftNode 左节点。
   * @param {{name: string, isDirectory: boolean}} rightNode 右节点。
   * @returns {number} 排序比较值。
   */
  function compareTreeNode(leftNode, rightNode) {
    if (leftNode.isDirectory !== rightNode.isDirectory) {
      return leftNode.isDirectory ? -1 : 1;
    }
    return leftNode.name.localeCompare(rightNode.name);
  }

  /**
   * 构造目录行。
   * @param {{name: string, path: string, children: Map}} directoryNode 目录节点。
   * @param {number} depth 缩进层级。
   * @param {string} filterText 小写过滤词；命中目录强制展开，便于看到命中项。
   * @returns {HTMLElement} 目录行。
   */
  function buildDirectoryRow(directoryNode, depth, filterText) {
    const isCollapsed =
      !filterText && viewState.collapsedDirectories.has(directoryNode.path);
    const rowButton = document.createElement("button");
    rowButton.type = "button";
    rowButton.className = "node";
    rowButton.style.paddingLeft = `${8 + depth * 14}px`;
    rowButton.setAttribute("aria-expanded", String(!isCollapsed));

    const caretNode = document.createElement("span");
    caretNode.className = "caret";
    caretNode.textContent = isCollapsed ? "▸" : "▾";
    rowButton.append(caretNode);

    const nameNode = document.createElement("span");
    nameNode.className = "name";
    nameNode.textContent = `${directoryNode.name}/`;
    rowButton.append(nameNode);

    if (!filterText) {
      const countNode = document.createElement("span");
      countNode.className = "chip";
      countNode.textContent = String(countFileLeaves(directoryNode));
      rowButton.append(countNode);
    }

    rowButton.addEventListener("click", () => {
      if (viewState.collapsedDirectories.has(directoryNode.path)) {
        viewState.collapsedDirectories.delete(directoryNode.path);
      } else {
        viewState.collapsedDirectories.add(directoryNode.path);
      }
      renderTree();
    });
    return rowButton;
  }

  /**
   * 统计目录下的文件数。
   * @param {{isDirectory: boolean, children: Map}} treeNode 目录节点。
   * @returns {number} 文件数。
   */
  function countFileLeaves(treeNode) {
    if (!treeNode.isDirectory) {
      return 1;
    }
    let fileCount = 0;
    for (const childNode of treeNode.children.values()) {
      fileCount += countFileLeaves(childNode);
    }
    return fileCount;
  }

  /**
   * 构造文件行。
   * @param {{name: string, path: string}} fileNode 文件节点。
   * @param {number} depth 缩进层级。
   * @returns {HTMLElement} 文件行。
   */
  function buildFileRow(fileNode, depth) {
    const rowButton = document.createElement("button");
    rowButton.type = "button";
    rowButton.className = "node";
    rowButton.style.paddingLeft = `${8 + depth * 14}px`;
    rowButton.setAttribute("aria-selected", String(fileNode.path === viewState.selectedPath));
    rowButton.append(buildCaretPlaceholder());

    const nameNode = document.createElement("span");
    nameNode.className = "name";
    nameNode.textContent = fileNode.name;
    rowButton.append(nameNode);

    rowButton.addEventListener("click", () => {
      void selectPath(fileNode.path);
    });
    return rowButton;
  }

  /**
   * 选中一个条目并按当前视图加载内容。
   *
   * 改动视图下条目的身份是「路径 + 分区」：同一个文件可以同时在已暂存与未暂存两段里，
   * 只给路径会拿到错误的 diff。分区缺省时按分区顺序解析。
   * @param {string} repositoryPath 仓库相对路径。
   * @param {string} sectionName 分区取值；文件视图不用。
   */
  async function selectPath(repositoryPath, sectionName = "") {
    viewState.selectedPath = repositoryPath;
    viewState.selectedSection =
      viewState.view === DIFF_VIEW
        ? sectionName || resolveSectionForPath(repositoryPath)
        : "";
    renderTree();
    await guardAgainstServiceExit(async () => {
      if (viewState.view === DIFF_VIEW) {
        await loadDiffForPath(repositoryPath, viewState.selectedSection);
      } else {
        await loadFileContent(repositoryPath);
      }
    });
  }

  /**
   * 加载并渲染单个文件正文。默认渲染源码，预览要由用户显式切换。
   * @param {string} repositoryPath 仓库相对路径。
   */
  async function loadFileContent(repositoryPath) {
    resetFilePreview();
    const fileResponse = await requestJson(`/api/file?path=${encodeURIComponent(repositoryPath)}`);
    setViewerPath(repositoryPath);
    if (fileResponse.status !== 200) {
      renderNotice(buildNotice({ isFailure: true, title: "无法读取", paragraphs: [fileResponse.body.error] }));
      return;
    }
    // 读到了才算「在文件视图里看过这个文件」：读失败的提示块不该被记下来，否则每次切回
    // 文件视图都会重新弹同一个错误。
    viewState.lastFileViewPath = repositoryPath;
    const fileBody = fileResponse.body;
    if (fileBody.kind !== "text") {
      elements.viewerMeta.textContent = fileBody.size_label;
      renderNotice(
        buildNotice({
          title: fileBody.kind === "binary" ? "二进制文件" : "文件过大",
          paragraphs: [fileBody.note],
          hint:
            fileBody.kind === "binary"
              ? "二进制文件没有可读正文，查看器不猜测它的内容。"
              : "大文件在浏览器里渲染既慢又难读，请用本地编辑器打开。",
        })
      );
      return;
    }
    viewState.loadedFile = fileBody;
    viewState.previewDescriptor = fileBody.preview || null;
    renderPreviewControls(viewState.previewDescriptor);
    await renderLoadedFile();
  }

  /**
   * 加载并渲染单个文件在某个分区下的逐行改动。
   * @param {string} repositoryPath 仓库相对路径。
   * @param {string} sectionName 分区取值。
   */
  async function loadDiffForPath(repositoryPath, sectionName) {
    const diffResponse = await requestJson(
      `/api/diff?path=${encodeURIComponent(repositoryPath)}&section=${encodeURIComponent(sectionName)}`
    );
    setViewerPath(repositoryPath);
    if (diffResponse.status !== 200) {
      elements.viewerMeta.textContent = "";
      renderNotice(buildNotice({ isFailure: true, title: "无法读取改动", paragraphs: [diffResponse.body.error] }));
      return;
    }
    // 与文件视图同一条口径：读到了才算「在改动视图里看过这条」，读失败的应答不记。
    viewState.lastDiffViewSelection = { path: repositoryPath, section: sectionName };
    const diffBody = diffResponse.body;
    // 头部在空态下会被 renderNotice 清成占位符，所以来源只在有逐行改动时才写头部，
    // 纯重命名与二进制那两支交给提示块正文自己说。
    if (diffBody.empty) {
      renderNotice(
        buildNotice(
          // 纯重命名没有逐行改动可看，但它并不是「与当前内容一致」——路径确实变了，
          // 说成「没有改动」会把人引向错误结论。二进制同理：内容确实变了，只是
          // git 不逐行给。
          diffBody.rename_from
            ? {
                title: "重命名，内容未变",
                paragraphs: [
                  `该文件在「${diffBody.section_label}」里由 <code>${escapeHtmlText(diffBody.rename_from)}</code> 重命名而来，正文没有变化，因此没有逐行改动可看。`,
                ],
              }
            : diffBody.binary
              ? {
                  title: "二进制文件，无逐行改动",
                  paragraphs: [
                    `该文件在「${diffBody.section_label}」里的内容有变化，但 git 判定它是二进制，不提供逐行 diff。`,
                  ],
                  hint: "要对比二进制内容，请在本机用专门工具打开这两个版本。",
                }
              : {
                  title: "该文件在此区段下没有改动",
                  paragraphs: [`「${diffBody.section_label}」中没有这个文件的改动。`],
                }
        )
      );
      return;
    }
    elements.viewerMeta.textContent = diffBody.rename_from
      ? `${diffBody.section_label} · 重命名自 ${diffBody.rename_from}`
      : diffBody.section_label;
    if (diffBody.truncated) {
      elements.statusHint.textContent = "只读视图 · 改动过大，仅显示前若干行";
    }
    renderDiffRows(diffBody.rows);
  }

  /**
   * 渲染带行号的正文；行内容来自服务端已转义的 HTML 片段。
   * @param {string[]} highlightedLines 逐行 HTML。
   */
  function renderCodeLines(highlightedLines) {
    const codeBlock = document.createElement("div");
    codeBlock.className = "code";
    const codeFragment = document.createDocumentFragment();
    highlightedLines.forEach((highlightedLine, lineIndex) => {
      const rowNode = document.createElement("div");
      rowNode.className = "row";
      const lineNumberNode = document.createElement("span");
      lineNumberNode.className = "lineno";
      lineNumberNode.textContent = String(lineIndex + 1);
      const sourceNode = document.createElement("span");
      sourceNode.className = "src";
      // 服务端产出的是 Pygments 转义后的行级 HTML 或转义后的纯文本，不含未转义的源码字符。
      sourceNode.innerHTML = highlightedLine;
      rowNode.append(lineNumberNode, sourceNode);
      codeFragment.append(rowNode);
    });
    codeBlock.append(codeFragment);
    elements.viewerBody.replaceChildren(codeBlock);
  }

  /**
   * 清空当前文件的预览状态，并把界面上的预览控件一起收掉。
   *
   * 换文件、切视图都要走一遍：不清的话上一个文件的预览能力（以及已取回的 HTML）会跟着
   * 新文件一起留着，点出来的预览与内容区的正文不是同一个文件。
   *
   * **状态和控件必须一起清。** 两个预览控件的可见性只由 `renderPreviewControls` 决定，
   * 只把 `previewDescriptor` 置空而不同步界面，上一个 `.md` 留下的「源码 / 预览」开关
   * （以及 HTML 留下的「在新标签页打开」）就会滞留在头部——切到改动视图时最明显，那里
   * 根本没有正文可预览。所以这里自己收尾，而不是指望每个调用方都记得再调一次。
   */
  function resetFilePreview() {
    viewState.loadedFile = null;
    viewState.previewDescriptor = null;
    viewState.renderMode = SOURCE_MODE;
    viewState.markdownHtml = null;
    renderPreviewControls(null);
  }

  /**
   * 同步预览控件的可见性与选中态。
   *
   * 两种能力各自对应一个控件：Markdown 给「源码 / 预览」开关，HTML 给「在新标签页
   * 打开」。非 Markdown 文件不显示开关，非 HTML 文件不显示链接——一个点了没反应或
   * 给出错误内容的控件比没有更糟。
   * @param {{mode: string, url?: string}|null} previewDescriptor 服务端给出的预览能力。
   */
  function renderPreviewControls(previewDescriptor) {
    const previewMode = previewDescriptor ? previewDescriptor.mode : "";
    elements.previewSwitch.hidden = previewMode !== "markdown";
    elements.openExternal.hidden = previewMode !== "external";
    if (previewMode === "external") {
      elements.openExternal.href = previewDescriptor.url;
    } else {
      elements.openExternal.removeAttribute("href");
    }
    const isPreview = viewState.renderMode === PREVIEW_MODE;
    elements.tabSource.setAttribute("aria-selected", String(!isPreview));
    elements.tabPreview.setAttribute("aria-selected", String(isPreview));
  }

  /**
   * 按当前模式渲染已加载的文件正文。
   */
  async function renderLoadedFile() {
    const fileBody = viewState.loadedFile;
    elements.viewerMeta.textContent = `${fileBody.language} · ${fileBody.line_count} 行 · ${fileBody.size_label}`;
    if (viewState.renderMode === PREVIEW_MODE) {
      await renderMarkdownPreview();
      return;
    }
    elements.statusHint.textContent = fileBody.highlighted
      ? "只读视图 · 服务端语法高亮"
      : "只读视图 · 未安装语法高亮依赖，已降级为纯文本";
    renderCodeLines(fileBody.lines);
  }

  /**
   * 渲染 Markdown 预览。
   *
   * 预览片段向服务端要一次并缓存：来回切换是查看 Markdown 的常规动作，每次都重新请求
   * 既慢又要多跑一遍服务端渲染。取不到时退回源码并说明原因，不把空白预览留在那里。
   */
  async function renderMarkdownPreview() {
    if (viewState.markdownHtml === null) {
      const markdownResponse = await requestJson(
        `/api/markdown?path=${encodeURIComponent(viewState.loadedFile.path)}`
      );
      if (markdownResponse.status !== 200) {
        await setRenderMode(SOURCE_MODE);
        elements.statusHint.textContent = `只读视图 · 无法生成预览：${markdownResponse.body.error}`;
        return;
      }
      viewState.markdownHtml = markdownResponse.body.html;
    }
    const previewNode = document.createElement("div");
    previewNode.className = "preview markdown";
    // 服务端渲染出的 HTML 片段。Markdown 正文里的 raw HTML 会在这里执行——预览是用户
    // 主动点开的一次，且查看器是绑在回环上的本机只读工具，详见 docs/guides/file-viewer.md。
    previewNode.innerHTML = viewState.markdownHtml;
    elements.viewerBody.replaceChildren(previewNode);
    elements.statusHint.textContent = "只读视图 · Markdown 预览（服务端渲染）";
  }

  /**
   * 切换源码与预览。
   * @param {"source"|"preview"} nextMode 目标模式。
   */
  async function setRenderMode(nextMode) {
    if (!viewState.loadedFile || viewState.renderMode === nextMode) {
      return;
    }
    viewState.renderMode = nextMode;
    renderPreviewControls(viewState.previewDescriptor);
    await guardAgainstServiceExit(async () => {
      await renderLoadedFile();
    });
  }

  /**
   * 渲染逐行 diff。
   * @param {Array<{kind: string, old_no: number|null, new_no: number|null, text: string}>} diffRows 逐行改动。
   */
  function renderDiffRows(diffRows) {
    const codeBlock = document.createElement("div");
    codeBlock.className = "code diff";
    const codeFragment = document.createDocumentFragment();
    for (const diffRow of diffRows) {
      const rowNode = document.createElement("div");
      rowNode.className = `row ${diffRow.kind}`;
      if (diffRow.kind === "hunk") {
        rowNode.textContent = diffRow.text;
        codeFragment.append(rowNode);
        continue;
      }
      const lineNumberNode = document.createElement("span");
      lineNumberNode.className = "lineno";
      lineNumberNode.append(
        document.createTextNode(diffRow.old_no === null ? "" : String(diffRow.old_no)),
        document.createElement("em"),
        document.createTextNode(diffRow.new_no === null ? "" : String(diffRow.new_no))
      );
      const sourceNode = document.createElement("span");
      sourceNode.className = "src";
      sourceNode.textContent = diffRow.text;
      rowNode.append(lineNumberNode, sourceNode);
      codeFragment.append(rowNode);
    }
    codeBlock.append(codeFragment);
    elements.viewerBody.replaceChildren(codeBlock);
  }

  /**
   * 切换视图。
   *
   * 两个视图各记一份「上一次看的那一个」，切过去时还原，而不是每次都回到空态：在改动里
   * 看到一半切去翻文件、再切回来，本该还在原来那条改动上。`pathToSelect` 是显式指定，
   * 优先级高于记忆——改动视图头部的「查看文件」就是靠它跳到当前这条改动对应的文件（那
   * 是「看你点的这一条」，不是「回到上次看的那个文件」）。还原是尽力而为：文件可能已经
   * 被删、改动可能已经提交，两种情况都由下游给出明确结果（未找到文件 / 空态）。
   * @param {string} nextView 目标视图。
   * @param {string} pathToSelect 显式要选中的仓库相对路径；空串表示用目标视图的记忆。
   */
  async function switchView(nextView, pathToSelect = "") {
    if (viewState.isDisconnected || viewState.view === nextView) {
      return;
    }
    viewState.view = nextView;
    resetFilePreview();
    renderViewTabs();
    if (nextView === DIFF_VIEW) {
      // 分区也要一起还原：同一个文件可以同时出现在已暂存与未暂存两段，只带路径回去会
      // 落到按分区顺序解析出来的另一段。
      viewState.selectedPath = pathToSelect || viewState.lastDiffViewSelection.path;
      viewState.selectedSection = pathToSelect ? "" : viewState.lastDiffViewSelection.section;
      await loadChangedFiles();
      return;
    }
    viewState.selectedPath = pathToSelect || viewState.lastFileViewPath;
    viewState.selectedSection = "";
    elements.statusHint.textContent = "";
    // 先展开祖先目录再渲染树，否则文件落在折叠的目录里时树上看不到选中态。
    expandToSelectedPath();
    renderTree();
    if (viewState.selectedPath) {
      await selectPath(viewState.selectedPath);
    } else {
      renderPlaceholder();
    }
  }

  elements.tabFiles.addEventListener("click", () => {
    void switchView(FILES_VIEW);
  });
  elements.copyPathButton.addEventListener("click", () => {
    void copyCurrentViewerPath();
  });
  elements.tabSource.addEventListener("click", () => {
    void setRenderMode(SOURCE_MODE);
  });
  elements.tabPreview.addEventListener("click", () => {
    void setRenderMode(PREVIEW_MODE);
  });
  // 从改动跳到文件：这里现取 selectedPath，而不是在渲染时就把它捕获进闭包——改动视图
  // 里每点一个条目都会换一份路径，捕获的那份会跳错文件。
  elements.openFileButton.addEventListener("click", () => {
    void switchView(FILES_VIEW, viewState.selectedPath);
  });
  elements.tabDiff.addEventListener("click", () => {
    void switchView(DIFF_VIEW);
  });
  elements.filterInput.addEventListener("input", () => {
    viewState.filterText = elements.filterInput.value;
    renderTree();
  });
  window.document.addEventListener("keydown", (keyboardEvent) => {
    if (keyboardEvent.target === elements.filterInput) {
      if (keyboardEvent.key === "Escape") {
        elements.filterInput.blur();
      }
      return;
    }
    if (keyboardEvent.key === "f") {
      void switchView(FILES_VIEW);
    } else if (keyboardEvent.key === "d") {
      void switchView(DIFF_VIEW);
    } else if (keyboardEvent.key === "/") {
      keyboardEvent.preventDefault();
      elements.filterInput.focus();
    }
  });

  void initializeViewer();
})();
