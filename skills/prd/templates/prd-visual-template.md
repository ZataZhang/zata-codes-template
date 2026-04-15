# PRD: [Feature Name]

## 1. Introduction & Goals

[Brief problem statement and feature objective.]

### Measurable Objectives
- [Objective 1]
- [Objective 2]
- [Objective 3]

---

## 2. Requirement Shape

- Actor: [Who needs this behavior]
- Trigger: [When the behavior happens]
- Expected behavior: [What the system should do]
- Scope boundary: [What this PRD does not cover]

---

## 3. Repository Context And Architecture Fit

- Existing path: [Closest current module or code path]
- Reuse candidates: [Files/modules to extend directly]
- Architecture pattern to preserve: [Relevant boundary or dependency direction]
- Constraints: [Runtime, dependency, coding standard, workflow, or rollout constraints]
- Redundancy risks: [Likely duplication or parallel abstraction risks]

---

## 4. Options And Recommendation

### Option A: Minimal Change
- Approach: [Extend existing path]
- Pros: [Why it is smaller/safer]
- Cons: [Known tradeoff]

### Option B: Heavier Change
- Approach: [New abstraction/module/service/dependency]
- Pros: [Potential benefit]
- Cons: [Added complexity]

### Recommendation
- Recommended option: [A or B]
- Why: [Why this best fits the current architecture]
- Rejected redundancy: [What extra layer or file was intentionally avoided]

---

## 5. Implementation Guide

### 5.1 Core Logic
- [How data and control move through the existing system]

### 5.2 Change Matrix

| Change Target | Current State | Target State | How to Modify | Why This Fits Existing Architecture | Affected Files |
|---|---|---|---|---|---|
| [Target 1] | [Current] | [Target] | [Implementation approach] | [Architecture-fit rationale] | `[path/a]`, `[path/b]` |
| [Target 2] | [Current] | [Target] | [Implementation approach] | [Architecture-fit rationale] | `[path/c]` |

### 5.3 Flow Or Architecture Diagram

```mermaid
flowchart TD
    USER[User Request] --> EXISTING[Existing Module Boundary]
    EXISTING --> CHANGE[Minimal Change Path]
    CHANGE --> VALIDATE[Validation And Tests]
    VALIDATE --> OUTPUT[Deliver]
```

### 5.4 Low-Fidelity Prototype (Only When Required)

```text
+--------------------------------------------------+
| [Main Screen/Module Name]                        |
+--------------------------------------------------+
| [Section A]                                      |
| [Section B]                                      |
| [Section C]                                      |
+--------------------------------------------------+
```

If not required:
- No low-fidelity prototype required for this PRD.

### 5.5 ER Diagram (Only When Data Model Changes)

```mermaid
erDiagram
    ENTITY_A ||--o{ ENTITY_B : relates_to
    ENTITY_A {
        string id
        string field_a
    }
    ENTITY_B {
        string id
        string field_b
    }
```

If not required:
- No data model changes in this PRD.

### 5.6 Affected Files

| File | Change Type | Description |
|---|---|---|
| `[path/to/file]` | Modify/Add/Delete | [What changes and why] |

### 5.7 Interactive Prototype Change Log (Only When Files Actually Changed)

| File Path | Change Type | Before | After | Why |
|---|---|---|---|---|
| `docs/prototypes/[feature]-demo.html` | Modify/Add | [Old behavior] | [New behavior] | [Reason] |

If no prototype changes:
- No interactive prototype file changes in this PRD.

### 5.8 External Validation (Only When Web Research Was Used)

| Topic | Source | Checked On | Relevant Finding | Impact On Recommendation |
|---|---|---|---|---|
| [Vendor/API/standard] | [URL or doc title] | [YYYY-MM-DD] | [Fact] | [Constraint or risk] |

If no external validation was needed:
- No external validation required; repository evidence was sufficient.

---

## 6. Definition Of Done

- [ ] Recommended option is fully implemented without introducing unapproved parallel abstractions
- [ ] All Acceptance Checklist items are satisfied
- [ ] Relevant tests and validation commands pass
- [ ] Documentation and operational notes are updated where needed
- [ ] No open regression or rollout blocker remains

---

## 7. Acceptance Checklist

Use task-relevant groups. For architecture-heavy or refactor work, start with the groups below and rename or replace groups only when another grouping is more precise.
This checklist must validate the final target state, not only an interim first phase.

### Architecture Acceptance

- [ ] [Concrete boundary, directory, ownership, or entry-point outcome]
- [ ] [Concrete layering or composition-root outcome]

### Dependency Acceptance

- [ ] [Concrete import, port, adapter, or dependency-direction constraint]
- [ ] [Concrete contract-compatibility or forbidden-dependency constraint]

### Behavior Acceptance

- [ ] [Concrete API, workflow, runtime, or business behavior outcome]
- [ ] [Concrete compatibility or invariance that must remain true]

### Documentation Acceptance

- [ ] [Concrete doc page or reference updated to match the target design]
- [ ] [PRD and repository docs stay aligned with the final architecture direction]

### Validation Acceptance

- [ ] `[validation command]` passes
- [ ] [Repository search confirms no legacy entry point, duplicate path, or compatibility shim remains]

---

## 8. User Stories

### US-001: [Story Title]
**Description:** As a [role], I want [feature], so that [benefit].

**Acceptance Criteria:**
- [ ] [Unique business logic 1]
- [ ] [Unique business logic 2]

---

## 9. Functional Requirements

- FR-1: [Requirement statement]
- FR-2: [Requirement statement]
- FR-3: [Requirement statement]

---

## 10. Non-Goals

- [Out-of-scope item 1]
- [Out-of-scope item 2]

---

## 11. Risks And Follow-Ups

- [Unavoidable risk or explicitly approved non-blocking follow-up]

---

## 12. Decision Log

每条记录对应本 PRD 中做出的一个关键决策，归档后作为永久参考。

| # | 决策问题 | 选择 | 放弃的方案 | 理由 |
|---|---|---|---|---|
| D-01 | [决策问题，如"架构模式选择"] | [最终选择] | [放弃的方案] | [一句话说明为什么] |
