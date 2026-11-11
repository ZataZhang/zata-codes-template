/**
 * Git 历史视图：按需加载提交图，并展示提交详情与文件 diff。
 *
 * 数据由本地只读接口提供；只有用户进入 Git Log 视图或手动加载时才请求历史。
 */
(function initializeHistoryView(global) {
  "use strict";

  const HISTORY_PAGE_SIZE = 50;
  const HISTORY_GRAPH_CELL_WIDTH = 8;
  const HISTORY_GRAPH_LANE_COUNT = 6;
  const HISTORY_GRAPH_SVG_NAMESPACE = "http://www.w3.org/2000/svg";

  /**
   * @typedef {object} HistoryViewContext
   * @property {object} elements 历史视图需要操作的 DOM 节点。
   * @property {(url: string, options?: object) => Promise<{status: number, body: object}>} requestJson 读取接口。
   * @property {(action: () => Promise<unknown>) => Promise<boolean>} guardAgainstServiceExit 统一处理服务退出。
   * @property {(descriptor: object | null) => void} renderPreviewControls 更新文件预览控件。
   * @property {(rows: object[]) => HTMLElement} buildDiffRowsNode 创建逐行 diff。
   * @property {() => boolean} isActive 判断 Git 历史是否为当前视图。
   * @property {() => boolean} isDisconnected 判断本机查看器服务是否已退出。
   * @property {(commitContext: object) => void} openCommitInDiffView 在既有改动视图中查看提交。
   */

  /**
   * 创建 Git 历史视图及其事件处理器。
   * @param {HistoryViewContext} historyContext 视图状态、DOM 节点与共享读取函数。
   * @returns {{load: (options?: {reset?: boolean}) => Promise<void>, render: () => void, isLoading: () => boolean, hasLoaded: () => boolean}} 历史视图操作。
   */
  function create(historyContext) {
    const elements = historyContext.elements;
    const requestJson = historyContext.requestJson;
    const guardAgainstServiceExit = historyContext.guardAgainstServiceExit;
    const renderPreviewControls = historyContext.renderPreviewControls;
    const buildDiffRowsNode = historyContext.buildDiffRowsNode;
    const isActive = historyContext.isActive;
    const isDisconnected = historyContext.isDisconnected;
    const openCommitInDiffView = historyContext.openCommitInDiffView;
    const historyState = {
      historyPages: [],
      historyBranchRefs: [],
      historyOffset: 0,
      historyIsLoaded: false,
      isLoadingHistory: false,
      hasMoreHistory: true,
      historyLimitReached: false,
      historyErrorMessage: "",
      selectedHistoryCommitHash: "",
      selectedHistoryCommit: null,
      isLoadingHistoryCommit: false,
      historyCommitErrorMessage: "",
      selectedHistoryPath: "",
      selectedHistoryDiff: null,
      isLoadingHistoryDiff: false,
      historyDiffErrorMessage: "",
    };

    /**
     * 按需读取下一页 Git 提交图；每页单独绘制，因此只请求并追加尚未显示的提交。
     * @param {{reset?: boolean}} [requestOptions] 是否丢弃已加载页面并从最新提交重新读取。
     */
    async function loadGitHistory(requestOptions = {}) {
      if (isDisconnected() || historyState.isLoadingHistory) {
        return;
      }
      if (requestOptions.reset) {
        historyState.historyPages = [];
        historyState.historyBranchRefs = [];
        historyState.historyOffset = 0;
        historyState.historyIsLoaded = false;
        historyState.hasMoreHistory = true;
        historyState.historyLimitReached = false;
        historyState.historyErrorMessage = "";
        historyState.selectedHistoryCommitHash = "";
        historyState.selectedHistoryCommit = null;
        historyState.historyCommitErrorMessage = "";
        historyState.selectedHistoryPath = "";
        historyState.selectedHistoryDiff = null;
        historyState.historyDiffErrorMessage = "";
      }
      if (historyState.historyIsLoaded && !historyState.hasMoreHistory) {
        if (isActive()) {
          renderHistoryView();
        }
        return;
      }

      historyState.isLoadingHistory = true;
      historyState.historyErrorMessage = "";
      if (isActive()) {
        renderHistoryView();
      }
      const didLoad = await guardAgainstServiceExit(async () => {
        const historyResponse = await requestJson(
          `/api/log?offset=${historyState.historyOffset}&limit=${HISTORY_PAGE_SIZE}`
        );
        if (historyResponse.status !== 200) {
          historyState.historyErrorMessage = historyResponse.body.error || "Git 历史读取失败。";
          return;
        }

        const historyPage = historyResponse.body;
        if (historyPage.commit_count > 0) {
          historyState.historyPages.push(historyPage);
          historyState.historyOffset += historyPage.commit_count;
        }
        if (historyPage.offset === 0) {
          historyState.historyBranchRefs = historyPage.branch_refs || [];
        }
        historyState.historyIsLoaded = true;
        historyState.hasMoreHistory = historyPage.has_more;
        historyState.historyLimitReached = historyPage.limit_reached;
      });
      historyState.isLoadingHistory = false;
      if (didLoad && isActive()) {
        renderHistoryView();
        const firstCommitRow = historyState.historyPages
          .flatMap((historyPage) => historyPage.rows)
          .find((historyRow) => historyRow.kind === "commit");
        if (!historyState.selectedHistoryCommitHash && firstCommitRow) {
          await selectHistoryCommit(firstCommitRow.hash);
        }
      }
    }

    /**
     * 读取所选提交的详情，并默认显示它的第一项文件改动。
     * @param {string} commitHash 提交完整哈希。
     */
    async function selectHistoryCommit(commitHash) {
      if (
        isDisconnected() ||
        historyState.isLoadingHistoryCommit ||
        historyState.isLoadingHistoryDiff
      ) {
        return;
      }
      historyState.selectedHistoryCommitHash = commitHash;
      historyState.selectedHistoryCommit = null;
      historyState.isLoadingHistoryCommit = true;
      historyState.historyCommitErrorMessage = "";
      historyState.selectedHistoryPath = "";
      historyState.selectedHistoryDiff = null;
      historyState.historyDiffErrorMessage = "";
      renderHistoryView();

      const didLoad = await guardAgainstServiceExit(async () => {
        const commitResponse = await requestJson(
          `/api/log/commit?hash=${encodeURIComponent(commitHash)}`
        );
        if (commitResponse.status !== 200) {
          historyState.historyCommitErrorMessage = commitResponse.body.error || "提交详情读取失败。";
          return;
        }
        historyState.selectedHistoryCommit = commitResponse.body;
        const firstChangedFile = commitResponse.body.files[0];
        if (firstChangedFile) {
          await loadHistoryFileDiff(firstChangedFile.path, { renderAfterLoad: false });
        }
      });
      historyState.isLoadingHistoryCommit = false;
      if (didLoad && isActive()) {
        renderHistoryView();
      }
    }

    /**
     * 读取所选提交中一个文件的逐行改动。
     * @param {string} repositoryPath 仓库相对路径。
     * @param {{renderAfterLoad?: boolean}} [requestOptions] 是否在请求完成后重绘详情区。
     */
    async function loadHistoryFileDiff(repositoryPath, requestOptions = {}) {
      if (
        isDisconnected() ||
        historyState.isLoadingHistoryDiff
      ) {
        return;
      }
      const commitHash = historyState.selectedHistoryCommitHash;
      historyState.selectedHistoryPath = repositoryPath;
      historyState.selectedHistoryDiff = null;
      historyState.isLoadingHistoryDiff = true;
      historyState.historyDiffErrorMessage = "";
      if (requestOptions.renderAfterLoad !== false) {
        renderHistoryView();
      }

      const didLoad = await guardAgainstServiceExit(async () => {
        const diffResponse = await requestJson(
          `/api/log/diff?hash=${encodeURIComponent(commitHash)}&path=${encodeURIComponent(repositoryPath)}`
        );
        if (diffResponse.status !== 200) {
          historyState.historyDiffErrorMessage = diffResponse.body.error || "文件改动读取失败。";
          return;
        }
        historyState.selectedHistoryDiff = diffResponse.body;
      });
      historyState.isLoadingHistoryDiff = false;
      if (didLoad && isActive() && requestOptions.renderAfterLoad !== false) {
        renderHistoryView();
      }
    }

    /**
     * 渲染已加载的 Git Log 页面和增量加载入口。
     */
    function renderHistoryView() {
      const previousGraphScrollTop =
        elements.viewerBody.querySelector(".history-graph-list")?.scrollTop || 0;
      const previousDetailScrollTop =
        elements.viewerBody.querySelector(".history-detail-pane")?.scrollTop || 0;
      elements.viewerPath.textContent = "Git Log Graph";
      elements.copyPathButton.hidden = true;
      elements.openInSystemButton.hidden = true;
      elements.openFileButton.hidden = true;
      elements.openExternal.hidden = true;
      renderPreviewControls(null);
      const localBranchCount = historyState.historyBranchRefs.filter(
        (branchRef) => branchRef.kind === "local"
      ).length;
      const remoteBranchCount = historyState.historyBranchRefs.filter(
        (branchRef) => branchRef.kind === "remote"
      ).length;
      elements.viewerMeta.textContent = historyState.historyOffset
        ? `已加载 ${historyState.historyOffset} 条 · 本地 ${localBranchCount} · 远程 ${remoteBranchCount}`
        : "按需读取 · 每页 50 条";

      const historyLayout = document.createElement("div");
      historyLayout.className = "history-layout";
      const graphPane = document.createElement("section");
      graphPane.className = "history-graph-pane";
      graphPane.setAttribute("aria-label", "Git 提交图");
      const branchList = document.createElement("div");
      branchList.className = "history-branch-list";
      const localBranchRefs = historyState.historyBranchRefs.filter(
        (branchRef) => branchRef.kind === "local"
      );
      const remoteBranchRefs = historyState.historyBranchRefs.filter(
        (branchRef) => branchRef.kind === "remote"
      );
      for (const [branchKind, branchRefs] of [
        ["local", localBranchRefs],
        ["remote", remoteBranchRefs],
      ]) {
        if (!branchRefs.length) {
          continue;
        }
        const branchGroup = document.createElement("section");
        branchGroup.className = `history-branch-group is-${branchKind}`;
        const branchGroupTitle = document.createElement("h2");
        branchGroupTitle.textContent = branchKind === "local" ? "本地分支" : "远程分支";
        const branchGroupItems = document.createElement("div");
        branchGroupItems.className = "history-branch-items";
        for (const branchRef of branchRefs) {
          branchGroupItems.append(buildHistoryBranchButton(branchRef));
        }
        branchGroup.append(branchGroupTitle, branchGroupItems);
        branchList.append(branchGroup);
      }
      if (!historyState.historyBranchRefs.length) {
        const noBranchesMessage = document.createElement("span");
        noBranchesMessage.className = "history-message";
        noBranchesMessage.textContent = "没有本地或远程分支引用";
        branchList.append(noBranchesMessage);
      }

      const graphList = document.createElement("div");
      graphList.className = "history-graph-list";
      for (const historyPage of historyState.historyPages) {
        const pageSection = document.createElement("div");
        pageSection.className = "history-page";
        const firstCommitNumber = historyPage.offset + 1;
        const lastCommitNumber = historyPage.offset + historyPage.commit_count;
        const pageHeading = document.createElement("h2");
        pageHeading.textContent = `提交 ${firstCommitNumber}–${lastCommitNumber}`;
        pageSection.append(pageHeading);
        let isFirstHistoryCommit = historyPage.offset === 0;
        for (const historyRow of historyPage.rows) {
          if (historyRow.kind === "commit") {
            pageSection.append(buildHistoryCommitRow(historyRow, isFirstHistoryCommit));
            isFirstHistoryCommit = false;
          } else {
            const graphEdgeNode = document.createElement("div");
            graphEdgeNode.className = "history-edge-row";
            graphEdgeNode.append(buildHistoryGraphRail(historyRow.graph, "edge"));
            pageSection.append(graphEdgeNode);
          }
        }
        graphList.append(pageSection);
      }

      if (historyState.isLoadingHistory && !historyState.historyPages.length) {
        const loadingMessage = document.createElement("p");
        loadingMessage.className = "history-message";
        loadingMessage.textContent = "正在读取 Git 历史…";
        graphList.append(loadingMessage);
      } else if (historyState.historyIsLoaded && !historyState.historyOffset) {
        const emptyMessage = document.createElement("p");
        emptyMessage.className = "history-message";
        emptyMessage.textContent = "仓库还没有可显示的提交。";
        graphList.append(emptyMessage);
      }

      if (historyState.historyErrorMessage) {
        const errorMessage = document.createElement("p");
        errorMessage.className = "history-message is-error";
        errorMessage.textContent = `Git 历史读取失败：${historyState.historyErrorMessage}`;
        graphList.append(errorMessage);
      }

      if (historyState.isLoadingHistory && historyState.historyPages.length) {
        const loadingMessage = document.createElement("p");
        loadingMessage.className = "history-message";
        loadingMessage.textContent = "正在加载更早的提交…";
        graphList.append(loadingMessage);
      } else if (historyState.historyErrorMessage) {
        graphList.append(buildHistoryActionButton("重试加载", "load-more"));
      } else if (historyState.hasMoreHistory && historyState.historyOffset) {
        graphList.append(buildHistoryActionButton("加载更早的 50 条提交", "load-more"));
      } else if (historyState.historyLimitReached) {
        const limitMessage = document.createElement("p");
        limitMessage.className = "history-message";
        limitMessage.textContent = "已达到 100,000 条提交的查看上限。";
        graphList.append(limitMessage);
      } else if (historyState.historyOffset) {
        const endMessage = document.createElement("p");
        endMessage.className = "history-message";
        endMessage.textContent = "已到历史末尾。";
        graphList.append(endMessage);
      }

      const detailPane = document.createElement("aside");
      detailPane.className = "history-detail-pane";
      renderHistoryCommitDetails(detailPane);
      graphPane.append(branchList, graphList);
      historyLayout.append(graphPane, detailPane);
      elements.viewerBody.replaceChildren(historyLayout);
      elements.viewerBody.querySelector(".history-graph-list").scrollTop = previousGraphScrollTop;
      elements.viewerBody.querySelector(".history-detail-pane").scrollTop = previousDetailScrollTop;
      elements.statusHint.textContent = historyState.historyOffset
        ? `Git Log · ${historyState.historyOffset} 条提交`
        : "Git Log";
    }

    /**
     * 渲染一个提交图节点，可显示分支引用并选择该提交。
     * @param {object} historyRow 服务端返回的提交图行。
     * @returns {HTMLButtonElement} 可交互的提交行。
     */
    function buildHistoryCommitRow(historyRow, isHistoryTopCommit = false) {
      const commitButton = document.createElement("button");
      commitButton.type = "button";
      commitButton.className = "history-commit-row";
      commitButton.dataset.historyCommitHash = historyRow.hash;
      commitButton.setAttribute(
        "aria-pressed",
        String(historyState.selectedHistoryCommitHash === historyRow.hash)
      );

      const graphPrefixNode = buildHistoryGraphRail(
        historyRow.graph_prefix,
        "commit",
        isHistoryTopCommit
      );
      graphPrefixNode.classList.add("history-graph-prefix");
      const hasBranchRef = historyRow.refs.some(
        (refLabel) => refLabel.kind === "local" || refLabel.kind === "remote"
      );
      if (hasBranchRef) {
        graphPrefixNode.classList.add("has-branch-ref");
      }
      if (historyRow.is_head) {
        graphPrefixNode.classList.add("is-head");
      }
      const commitSummary = document.createElement("span");
      commitSummary.className = "history-commit-summary";
      const commitSubjectNode = document.createElement("span");
      commitSubjectNode.className = "history-commit-subject";
      commitSubjectNode.textContent = historyRow.subject;
      const commitRefs = document.createElement("span");
      commitRefs.className = "history-commit-refs";
      if (historyRow.is_head) {
        commitRefs.append(buildHistoryRefBadge({ name: "HEAD", kind: "head" }));
      }
      for (const refLabel of historyRow.refs) {
        commitRefs.append(buildHistoryRefBadge(refLabel));
      }
      const commitMeta = document.createElement("span");
      commitMeta.className = "history-commit-meta mono";
      commitMeta.textContent = `${historyRow.short_hash} · ${historyRow.date}`;
      commitSummary.append(commitSubjectNode, commitRefs);
      commitButton.append(graphPrefixNode, commitSummary, commitMeta);
      return commitButton;
    }

    /**
     * 把 Git 的字符图转换成彩色轨道、连接线和圆形提交节点。
     * @param {string} graphLine Git 输出的一行图形前缀。
     * @param {"commit" | "edge"} rowKind 当前行是提交行还是连接行。
     * @param {boolean} isHistoryTopCommit 是否为历史列表中的第一条提交。
     * @returns {SVGSVGElement} 装饰性提交图轨道。
     */
    function buildHistoryGraphRail(graphLine, rowKind, isHistoryTopCommit = false) {
      const isCommitRow = rowKind === "commit";
      const graphHeight = isCommitRow ? 24 : 14;
      let graphWidth = Math.max(
        HISTORY_GRAPH_CELL_WIDTH * 2,
        graphLine.length * HISTORY_GRAPH_CELL_WIDTH
      );
      for (let charIndex = 0; charIndex < graphLine.length; charIndex += 1) {
        if (graphLine[charIndex] === "/" || graphLine[charIndex] === "\\") {
          const graphStartX = Math.max(
            HISTORY_GRAPH_CELL_WIDTH / 2,
            charIndex * HISTORY_GRAPH_CELL_WIDTH - HISTORY_GRAPH_CELL_WIDTH / 2
          );
          graphWidth = Math.max(
            graphWidth,
            graphStartX + HISTORY_GRAPH_CELL_WIDTH * 2 + HISTORY_GRAPH_CELL_WIDTH / 2
          );
        }
      }

      const graphRail = document.createElementNS(HISTORY_GRAPH_SVG_NAMESPACE, "svg");
      graphRail.classList.add("history-graph-rail");
      graphRail.setAttribute("aria-hidden", "true");
      graphRail.setAttribute("focusable", "false");
      graphRail.setAttribute("viewBox", `0 0 ${graphWidth} ${graphHeight}`);
      graphRail.setAttribute("width", String(graphWidth));
      graphRail.setAttribute("height", String(graphHeight));

      for (let charIndex = 0; charIndex < graphLine.length; charIndex += 1) {
        const graphGlyph = graphLine[charIndex];
        if (graphGlyph === " ") {
          continue;
        }

        const graphLaneIndex = Math.floor(charIndex / 2) % HISTORY_GRAPH_LANE_COUNT;
        const graphCellCenter = charIndex * HISTORY_GRAPH_CELL_WIDTH + HISTORY_GRAPH_CELL_WIDTH / 2;
        const graphSegment = document.createElementNS(HISTORY_GRAPH_SVG_NAMESPACE, "path");
        graphSegment.classList.add("history-graph-segment", `is-lane-${graphLaneIndex}`);

        if (graphGlyph === "|" || graphGlyph === "*" || graphGlyph === "+") {
          const graphSegmentStartY = isHistoryTopCommit && graphGlyph === "*"
            ? graphHeight / 2
            : 1;
          graphSegment.setAttribute(
            "d",
            `M ${graphCellCenter} ${graphSegmentStartY} V ${graphHeight - 1}`
          );
          graphRail.append(graphSegment);
          if (graphGlyph === "*" || graphGlyph === "+") {
            const graphNode = document.createElementNS(HISTORY_GRAPH_SVG_NAMESPACE, "circle");
            graphNode.classList.add("history-graph-node", `is-lane-${graphLaneIndex}`);
            graphNode.setAttribute("cx", String(graphCellCenter));
            graphNode.setAttribute("cy", String(graphHeight / 2));
            graphNode.setAttribute("r", "3.2");
            graphRail.append(graphNode);
          }
        } else if (graphGlyph === "/" || graphGlyph === "\\") {
          const graphStartX = Math.max(
            HISTORY_GRAPH_CELL_WIDTH / 2,
            charIndex * HISTORY_GRAPH_CELL_WIDTH - HISTORY_GRAPH_CELL_WIDTH / 2
          );
          const graphEndX = graphStartX + HISTORY_GRAPH_CELL_WIDTH * 2;
          const graphPath =
            graphGlyph === "\\"
              ? `M ${graphStartX} 1 L ${graphEndX} ${graphHeight - 1}`
              : `M ${graphEndX} 1 L ${graphStartX} ${graphHeight - 1}`;
          graphSegment.setAttribute("d", graphPath);
          graphRail.append(graphSegment);
        }
      }

      return graphRail;
    }

    /**
     * 创建区分本地分支、远程分支、标签与 HEAD 的引用徽标。
     * @param {{name: string, kind: string}} refLabel Git 引用标签。
     * @returns {HTMLSpanElement} 引用徽标。
     */
    function buildHistoryRefBadge(refLabel) {
      const refBadge = document.createElement("span");
      refBadge.className = `history-ref is-${refLabel.kind}`;
      refBadge.textContent = refLabel.name;
      refBadge.title =
        refLabel.kind === "remote"
          ? `远程跟踪分支：${refLabel.name}`
          : refLabel.kind === "local"
            ? `本地分支：${refLabel.name}`
            : refLabel.kind === "head"
              ? "当前 HEAD"
              : `Git 标签：${refLabel.name}`;
      return refBadge;
    }

    /**
     * 创建可直接打开分支尖端提交的引用按钮。
     * @param {{name: string, kind: string, hash: string}} branchRef 分支引用及其尖端提交。
     * @returns {HTMLButtonElement} 分支引用按钮。
     */
    function buildHistoryBranchButton(branchRef) {
      const branchButton = document.createElement("button");
      branchButton.type = "button";
      branchButton.className = `history-branch-button is-${branchRef.kind}`;
      branchButton.dataset.historyBranchHash = branchRef.hash;
      branchButton.setAttribute(
        "aria-pressed",
        String(historyState.selectedHistoryCommitHash === branchRef.hash)
      );
      branchButton.title = `查看 ${branchRef.name} 的最新提交`;
      branchButton.append(buildHistoryRefBadge(branchRef));
      return branchButton;
    }

    /**
     * 渲染所选提交的信息、文件列表与逐行 diff。
     * @param {HTMLElement} detailPane 提交详情侧栏。
     */
    function renderHistoryCommitDetails(detailPane) {
      if (historyState.isLoadingHistoryCommit) {
        detailPane.append(buildHistoryMessage("正在读取提交详情…"));
        return;
      }
      if (historyState.historyCommitErrorMessage) {
        detailPane.append(buildHistoryMessage(historyState.historyCommitErrorMessage, true));
        return;
      }
      const selectedCommit = historyState.selectedHistoryCommit;
      if (!selectedCommit) {
        detailPane.append(buildHistoryMessage("点击左侧任一提交查看提交说明和文件改动。"));
        return;
      }

      const commitHeader = document.createElement("header");
      commitHeader.className = "history-detail-header";
      const commitTitle = document.createElement("h2");
      commitTitle.textContent = `提交 ${selectedCommit.short_hash}`;
      const commitSubject = document.createElement("p");
      commitSubject.className = "history-detail-subject";
      commitSubject.textContent = selectedCommit.message.split("\n")[0] || "（无提交说明）";
      const commitHash = document.createElement("code");
      commitHash.className = "history-detail-hash mono";
      commitHash.textContent = selectedCommit.hash;
      commitHeader.append(commitTitle, commitSubject, commitHash);
      detailPane.append(commitHeader);

      const commitMetadata = document.createElement("dl");
      commitMetadata.className = "history-commit-metadata";
      appendHistoryMetadata(commitMetadata, "作者", `${selectedCommit.author_name} <${selectedCommit.author_email}>`);
      appendHistoryMetadata(commitMetadata, "日期", selectedCommit.authored_at);
      appendHistoryMetadata(
        commitMetadata,
        "比较基线",
        selectedCommit.parents.length ? `首个父提交 ${selectedCommit.parents[0].slice(0, 12)}` : "空树（根提交）"
      );
      detailPane.append(commitMetadata);

      const fullMessage = document.createElement("pre");
      fullMessage.className = "history-commit-message";
      fullMessage.textContent = selectedCommit.message;
      detailPane.append(fullMessage);

      const changeHeading = document.createElement("h3");
      changeHeading.className = "history-change-heading";
      const fileFilterText = elements.filterInput.value.trim().toLowerCase();
      const matchingChangedFiles = selectedCommit.files.filter((changedFile) => {
        if (!fileFilterText) {
          return true;
        }
        return [changedFile.path, changedFile.old_path]
          .filter(Boolean)
          .some((changedPath) => changedPath.toLowerCase().includes(fileFilterText));
      });
      changeHeading.textContent = fileFilterText
        ? `改动文件（${matchingChangedFiles.length}/${selectedCommit.files.length}）`
        : `改动文件（${selectedCommit.files.length}）`;
      detailPane.append(changeHeading);
      if (!selectedCommit.files.length) {
        detailPane.append(buildHistoryMessage("该提交相对首个父提交没有文件差异。"));
        return;
      }
      if (!matchingChangedFiles.length) {
        detailPane.append(buildHistoryMessage("没有匹配的改动文件。"));
        return;
      }

      const changedFilesList = document.createElement("div");
      changedFilesList.className = "history-changed-files";
      for (const changedFile of matchingChangedFiles) {
        const changedFileButton = document.createElement("button");
        changedFileButton.type = "button";
        changedFileButton.className = "history-changed-file";
        changedFileButton.dataset.historyFilePath = changedFile.path;
        changedFileButton.setAttribute(
          "aria-pressed",
          String(historyState.selectedHistoryPath === changedFile.path)
        );
        const statusBadge = document.createElement("span");
        statusBadge.className = `history-file-status is-${changedFile.status[0].toLowerCase()}`;
        statusBadge.textContent = changedFile.status;
        const filePathNode = document.createElement("span");
        filePathNode.className = "history-file-path mono";
        filePathNode.textContent = changedFile.old_path
          ? `${changedFile.old_path} → ${changedFile.path}`
          : changedFile.path;
        changedFileButton.append(statusBadge, filePathNode);
        changedFilesList.append(changedFileButton);
      }
      detailPane.append(changedFilesList);

      const showCommitChangesButton = buildHistoryActionButton(
        "在改动视图查看全部改动",
        "show-in-diff-view"
      );
      showCommitChangesButton.classList.add("history-diff-view-button");
      detailPane.append(showCommitChangesButton);

      const selectedFileMatchesFilter =
        !fileFilterText ||
        matchingChangedFiles.some(
          (changedFile) => changedFile.path === historyState.selectedHistoryPath
        );
      if (fileFilterText && !selectedFileMatchesFilter) {
        detailPane.append(buildHistoryMessage("从筛选结果中选择一个文件查看改动。"));
      } else if (historyState.isLoadingHistoryDiff) {
        detailPane.append(buildHistoryMessage("正在读取文件改动…"));
      } else if (historyState.historyDiffErrorMessage) {
        detailPane.append(buildHistoryMessage(historyState.historyDiffErrorMessage, true));
      } else if (historyState.selectedHistoryDiff) {
        const selectedDiff = historyState.selectedHistoryDiff;
        const diffHeading = document.createElement("h3");
        diffHeading.className = "history-change-heading";
        diffHeading.textContent = selectedDiff.old_path
          ? `${selectedDiff.old_path} → ${selectedDiff.path}`
          : selectedDiff.path;
        detailPane.append(diffHeading);
        if (selectedDiff.binary) {
          detailPane.append(buildHistoryMessage("二进制文件不提供逐行 diff。"));
        } else if (selectedDiff.empty) {
          detailPane.append(buildHistoryMessage("该文件没有可显示的逐行改动。"));
        } else {
          if (selectedDiff.truncated) {
            detailPane.append(buildHistoryMessage("改动较大，已截断到 4,000 行。"));
          }
          detailPane.append(buildDiffRowsNode(selectedDiff.rows));
        }
      }
    }

    /**
     * 向提交元信息列表追加一组标签和值。
     * @param {HTMLDListElement} metadataList 元信息列表。
     * @param {string} label 元信息标签。
     * @param {string} value 元信息值。
     */
    function appendHistoryMetadata(metadataList, label, value) {
      const metadataLabel = document.createElement("dt");
      metadataLabel.textContent = label;
      const metadataValue = document.createElement("dd");
      metadataValue.textContent = value;
      metadataList.append(metadataLabel, metadataValue);
    }

    /**
     * 创建提交详情里的状态消息。
     * @param {string} messageText 消息文案。
     * @param {boolean} [isFailure] 是否作为错误显示。
     * @returns {HTMLParagraphElement} 消息节点。
     */
    function buildHistoryMessage(messageText, isFailure = false) {
      const messageNode = document.createElement("p");
      messageNode.className = isFailure ? "history-message is-error" : "history-message";
      messageNode.textContent = messageText;
      return messageNode;
    }

    /**
     * 创建 Git 历史分页操作按钮。
     * @param {string} label 按钮文案。
     * @param {string} action 按钮动作。
     * @returns {HTMLButtonElement} 新建的按钮。
     */
    function buildHistoryActionButton(label, action) {
      const actionButton = document.createElement("button");
      actionButton.type = "button";
      actionButton.className = "head-action history-load-more";
      actionButton.dataset.historyAction = action;
      actionButton.textContent = label;
      return actionButton;
    }

    elements.viewerBody.addEventListener("click", (clickEvent) => {
      if (!isActive()) {
        return;
      }
      const selectedCommitButton = clickEvent.target.closest("[data-history-commit-hash]");
      if (selectedCommitButton) {
        void selectHistoryCommit(selectedCommitButton.dataset.historyCommitHash);
        return;
      }
      const selectedBranchButton = clickEvent.target.closest("[data-history-branch-hash]");
      if (selectedBranchButton) {
        void selectHistoryCommit(selectedBranchButton.dataset.historyBranchHash);
        return;
      }
      const selectedFileButton = clickEvent.target.closest("[data-history-file-path]");
      if (selectedFileButton) {
        void loadHistoryFileDiff(selectedFileButton.dataset.historyFilePath);
        return;
      }
      const historyActionButton = clickEvent.target.closest("[data-history-action]");
      if (historyActionButton) {
        if (historyActionButton.dataset.historyAction === "show-in-diff-view") {
          openCommitInDiffView({
            commit: historyState.selectedHistoryCommit,
            selectedPath: historyState.selectedHistoryPath,
            selectedDiff: historyState.selectedHistoryDiff,
          });
        } else {
          void loadGitHistory();
        }
      }
    });

    return {
      load: loadGitHistory,
      render: renderHistoryView,
      isLoading: () =>
        historyState.isLoadingHistory ||
        historyState.isLoadingHistoryCommit ||
        historyState.isLoadingHistoryDiff,
      hasLoaded: () => historyState.historyIsLoaded,
    };
  }

  global.LocalViewHistory = { create };
})(window);
