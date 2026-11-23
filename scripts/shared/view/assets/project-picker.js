(() => {
  "use strict";
  /** 注册当前标签页，使用每次加载生成的标识以区分复制出来的页面。 */
  async function connectProjectPicker({ requestJson, busy, hasUnsavedFileEdits, elements }) {
    const tab = crypto.randomUUID();
    const picker = document.getElementById("project-picker");
    const post = (action, fields = {}) => requestJson("/api/project-tabs", {
      method: "POST", body: { action, tab, ...fields },
    });
    let renderedProjects;
    const render = (projects) => {
      const signature = JSON.stringify(projects);
      if (signature === renderedProjects) return;
      renderedProjects = signature;
      const names = projects.map((project) => project.name);
      picker.replaceChildren(...projects.map((project) => {
        const label = names.indexOf(project.name) === names.lastIndexOf(project.name)
          ? project.name : project.root;
        const option = new Option(label, String(project.port));
        option.title = project.root;
        return option;
      }));
      picker.value = location.port;
      picker.hidden = projects.length < 2;
      elements.repoName.hidden = !picker.hidden;
    };
    picker.onchange = () => {
      const port = picker.value;
      picker.value = location.port;
      if (busy()) {
        elements.statusHint.textContent = "操作进行中，请稍后切换项目。";
        return;
      }
      location.assign(`http://127.0.0.1:${port}/`);
    };
    const focus = () => { void post("focus").catch(() => {}); };
    window.addEventListener("focus", focus);
    const leave = () => {
      const payload = new Blob([JSON.stringify({ action: "leave", tab })], { type: "application/json" });
      navigator.sendBeacon("/api/project-tabs", payload);
    };
    window.addEventListener("pagehide", leave);
    if (document.hasFocus()) focus();
    try {
      const initial = await requestJson("/api/projects");
      if (initial.status !== 200) return;
      render(initial.body.projects);
      for (;;) {
        const response = await post("wait");
        if (response.status !== 200) return;
        render(response.body.projects);
        const command = response.body.command;
        if (!command) continue;
        const ack = await post("ack", { id: command.id });
        if (!ack.body.accepted) continue;
        window.focus();
        if (hasUnsavedFileEdits() || busy()) {
          elements.statusHint.textContent = "已收到项目打开请求，可在左上角切换项目。";
        } else {
          location.assign(command.url);
          return;
        }
      }
    } catch {
      // 服务退出或网络中断时保留当前页面，恢复后重新登记。
      window.removeEventListener("focus", focus);
      window.removeEventListener("pagehide", leave);
      window.setTimeout(() => connectProjectPicker({ requestJson, busy, hasUnsavedFileEdits, elements }), 3000);
    }
  }

  window.connectZviewProjects = connectProjectPicker;
})();
