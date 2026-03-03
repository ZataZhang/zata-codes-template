(function initPrototype() {
  "use strict";

  const scenarioStateMap = {
    normal: [
      {
        title: "需求输入",
        description: "业务方提交需求并明确目标。",
        risk: "Low",
      },
      {
        title: "上下文分析",
        description: "扫描代码和文档，确定改动边界。",
        risk: "Low",
      },
      {
        title: "改动设计",
        description: "输出 Change Matrix、流程图与原型链接。",
        risk: "Medium",
      },
      {
        title: "实现与验证",
        description: "落地代码并执行构建验证。",
        risk: "Low",
      },
    ],
    edge: [
      {
        title: "需求输入",
        description: "输入信息不完整，目标模糊。",
        risk: "Medium",
      },
      {
        title: "上下文分析",
        description: "发现跨模块改动和潜在兼容风险。",
        risk: "High",
      },
      {
        title: "改动设计",
        description: "需要补充例外流程与回滚策略。",
        risk: "High",
      },
      {
        title: "实现与验证",
        description: "优先做分阶段发布和回归验证。",
        risk: "Medium",
      },
    ],
  };

  const phaseTitleElement = document.getElementById("phaseTitle");
  const phaseDescriptionElement = document.getElementById("phaseDescription");
  const progressFillElement = document.getElementById("progressFill");
  const stepNumberElement = document.getElementById("stepNumber");
  const riskLabelElement = document.getElementById("riskLabel");
  const timelineListElement = document.getElementById("timelineList");
  const startButtonElement = document.getElementById("startBtn");
  const nextButtonElement = document.getElementById("nextBtn");
  const resetButtonElement = document.getElementById("resetBtn");
  const toggleButtonElements = document.querySelectorAll(".toggle-btn");

  let currentScenarioKey = "normal";
  let currentStepIndex = -1;

  function getCurrentScenarioSteps() {
    return scenarioStateMap[currentScenarioKey];
  }

  function getNowTimeLabel() {
    const nowDate = new Date();
    return nowDate.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  function appendTimelineEntry(eventMessageText) {
    const timelineItemElement = document.createElement("li");
    const timelineTimeLabel = getNowTimeLabel();
    timelineItemElement.innerHTML =
      "<span class='timeline-time'>" +
      timelineTimeLabel +
      "</span><br />" +
      eventMessageText;
    timelineListElement.prepend(timelineItemElement);
  }

  function renderIdleState() {
    phaseTitleElement.textContent = "待开始";
    phaseDescriptionElement.textContent = "点击 Start 开始模拟需求到交付的流程。";
    progressFillElement.style.width = "0%";
    stepNumberElement.textContent = "0 / 4";
    riskLabelElement.textContent = "Low";
  }

  function renderCurrentStep() {
    const currentScenarioSteps = getCurrentScenarioSteps();
    if (currentStepIndex < 0 || currentStepIndex >= currentScenarioSteps.length) {
      renderIdleState();
      return;
    }

    const currentPhaseObject = currentScenarioSteps[currentStepIndex];
    const progressPercent = ((currentStepIndex + 1) / currentScenarioSteps.length) * 100;
    phaseTitleElement.textContent = currentPhaseObject.title;
    phaseDescriptionElement.textContent = currentPhaseObject.description;
    progressFillElement.style.width = progressPercent + "%";
    stepNumberElement.textContent = String(currentStepIndex + 1) + " / " + String(currentScenarioSteps.length);
    riskLabelElement.textContent = currentPhaseObject.risk;
  }

  function setScenario(nextScenarioKey) {
    currentScenarioKey = nextScenarioKey;
    currentStepIndex = -1;
    renderCurrentStep();
    toggleButtonElements.forEach((buttonElement) => {
      const buttonScenarioKey = buttonElement.getAttribute("data-scenario");
      buttonElement.classList.toggle("is-active", buttonScenarioKey === nextScenarioKey);
    });
    appendTimelineEntry("切换场景为 " + nextScenarioKey + "。");
  }

  function startFlow() {
    if (currentStepIndex === -1) {
      currentStepIndex = 0;
      renderCurrentStep();
      appendTimelineEntry("流程已启动。");
      return;
    }
    appendTimelineEntry("流程已在运行，继续点击 Next。");
  }

  function nextFlowStep() {
    const currentScenarioSteps = getCurrentScenarioSteps();
    if (currentStepIndex === -1) {
      appendTimelineEntry("请先点击 Start。");
      return;
    }

    if (currentStepIndex < currentScenarioSteps.length - 1) {
      currentStepIndex += 1;
      renderCurrentStep();
      appendTimelineEntry("进入下一阶段。");
      return;
    }

    appendTimelineEntry("流程已完成。");
  }

  function resetFlow() {
    currentStepIndex = -1;
    renderCurrentStep();
    appendTimelineEntry("流程已重置。");
  }

  toggleButtonElements.forEach((toggleButtonElement) => {
    toggleButtonElement.addEventListener("click", function onToggleClick() {
      const selectedScenarioKey = toggleButtonElement.getAttribute("data-scenario");
      if (selectedScenarioKey && selectedScenarioKey !== currentScenarioKey) {
        setScenario(selectedScenarioKey);
      }
    });
  });
  startButtonElement.addEventListener("click", startFlow);
  nextButtonElement.addEventListener("click", nextFlowStep);
  resetButtonElement.addEventListener("click", resetFlow);

  renderCurrentStep();
  appendTimelineEntry("原型已加载，可开始操作。");
})();
