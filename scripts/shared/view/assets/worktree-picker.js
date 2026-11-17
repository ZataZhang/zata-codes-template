/** zview 顶部工作区分支选择器。 */
(() => {
  "use strict";

  /**
   * 创建顶部 worktree 选择器，并在页面初始化或手动刷新时加载选项。
   * @param {{branchChip: HTMLElement, branchPicker: HTMLSelectElement, statusHint: HTMLElement,
   * requestJson: (url: string, options?: object) => Promise<{status: number, body: object}>,
   * isGitAvailable: () => boolean, getCurrentView: () => string,
   * getBusyMessage: () => string, hasUnsavedFileEdits: () => boolean,
   * getEditDraftText: () => string, setOpeningWorktree: (isOpening: boolean) => void}}
   * pickerConfiguration 页面状态与查看器接口。
   * @returns {{load: () => Promise<void>}} 加载 worktree 选项的方法。
   */
  function createWorktreePicker(pickerConfiguration) {
    let currentWorktreeId = "";
    let isOpeningWorktree = false;

    /**
     * 读取当前仓库已检出的 worktree；有多个时显示选择器。
     */
    async function loadWorktreeOptions() {
      currentWorktreeId = "";
      pickerConfiguration.branchPicker.hidden = true;
      pickerConfiguration.branchPicker.disabled = false;
      const gitAvailable = pickerConfiguration.isGitAvailable();
      pickerConfiguration.branchChip.hidden = !gitAvailable;
      if (!gitAvailable) {
        pickerConfiguration.branchPicker.replaceChildren();
        return;
      }

      try {
        const worktreeResponse = await pickerConfiguration.requestJson("/api/worktrees");
        const worktreeOptions = Array.isArray(worktreeResponse.body.worktrees)
          ? worktreeResponse.body.worktrees.filter(
              (worktreeOption) =>
                typeof worktreeOption.id === "string" &&
                typeof worktreeOption.label === "string" &&
                typeof worktreeOption.current === "boolean",
            )
          : [];
        const currentWorktreeOption = worktreeOptions.find(
          (worktreeOption) => worktreeOption.current,
        );
        if (
          worktreeResponse.status !== 200 ||
          worktreeOptions.length < 2 ||
          !currentWorktreeOption
        ) {
          pickerConfiguration.branchChip.hidden = false;
          return;
        }

        const branchOptionNodes = worktreeOptions.map((worktreeOption) => {
          const branchOptionNode = document.createElement("option");
          branchOptionNode.value = worktreeOption.id;
          branchOptionNode.textContent = worktreeOption.label;
          return branchOptionNode;
        });
        pickerConfiguration.branchPicker.replaceChildren(...branchOptionNodes);
        currentWorktreeId = currentWorktreeOption.id;
        pickerConfiguration.branchPicker.value = currentWorktreeId;
        pickerConfiguration.branchPicker.hidden = false;
        pickerConfiguration.branchChip.hidden = true;
      } catch {
        // worktree 查询失败时保留分支徽标，不影响文件与改动浏览。
        pickerConfiguration.branchChip.hidden = !pickerConfiguration.isGitAvailable();
      }
    }

    /** 打开另一个已检出的 worktree 对应的 zview 实例。 */
    async function openSelectedWorktree() {
      const selectedWorktreeId = pickerConfiguration.branchPicker.value;
      if (
        !selectedWorktreeId ||
        selectedWorktreeId === currentWorktreeId ||
        isOpeningWorktree
      ) {
        return;
      }

      const busyMessage = pickerConfiguration.getBusyMessage();
      if (busyMessage) {
        pickerConfiguration.statusHint.textContent = busyMessage;
        pickerConfiguration.branchPicker.value = currentWorktreeId;
        return;
      }

      const previouslyConfirmedDraftText = pickerConfiguration.hasUnsavedFileEdits()
        ? pickerConfiguration.getEditDraftText()
        : null;
      if (
        previouslyConfirmedDraftText !== null &&
        !window.confirm("文件有未保存的修改，要放弃草稿并切换工作区吗？")
      ) {
        pickerConfiguration.branchPicker.value = currentWorktreeId;
        return;
      }

      pickerConfiguration.branchPicker.disabled = true;
      pickerConfiguration.statusHint.textContent = "正在打开另一个 worktree…";
      try {
        const worktreeResponse = await pickerConfiguration.requestJson("/api/open", {
          method: "POST",
          body: {
            worktree_id: selectedWorktreeId,
            view: pickerConfiguration.getCurrentView(),
          },
        });
        if (worktreeResponse.status !== 200 || typeof worktreeResponse.body.url !== "string") {
          throw new Error(worktreeResponse.body.error || "无法打开所选工作区。");
        }

        const targetViewerUrl = new URL(worktreeResponse.body.url);
        if (targetViewerUrl.protocol !== "http:" || targetViewerUrl.hostname !== "127.0.0.1") {
          throw new Error("目标查看器地址无效。");
        }
        const operationBusyMessage = pickerConfiguration.getBusyMessage();
        if (operationBusyMessage) {
          throw new Error(operationBusyMessage);
        }
        if (
          pickerConfiguration.hasUnsavedFileEdits() &&
          pickerConfiguration.getEditDraftText() !== previouslyConfirmedDraftText &&
          !window.confirm("文件有新的未保存修改，要放弃草稿并切换工作区吗？")
        ) {
          return;
        }

        isOpeningWorktree = true;
        pickerConfiguration.setOpeningWorktree(true);
        try {
          window.location.assign(targetViewerUrl.href);
        } catch (navigationError) {
          isOpeningWorktree = false;
          pickerConfiguration.setOpeningWorktree(false);
          throw navigationError;
        }
      } catch (worktreeOpenError) {
        pickerConfiguration.statusHint.textContent =
          `打开工作区失败：${worktreeOpenError.message}`;
      } finally {
        if (!isOpeningWorktree) {
          pickerConfiguration.branchPicker.disabled = false;
          pickerConfiguration.branchPicker.value = currentWorktreeId;
        }
      }
    }

    pickerConfiguration.branchPicker.addEventListener("change", () => {
      void openSelectedWorktree();
    });
    return { load: loadWorktreeOptions };
  }

  window.zviewWorktreePicker = Object.freeze({ create: createWorktreePicker });
})();
