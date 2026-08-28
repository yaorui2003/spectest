---

description: "Task list template for feature implementation (testing-tdd preset: TDD REQUIRED)"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), specs/<feature>/docs/test-plan.md (REQUIRED if speckit.testing.plan has been run — UT 用例清单与验收阈值；缺失时测试任务按 contracts/ 与 spec.md FR 段推导，并在 tasks.md 中注明), research.md, data-model.md, contracts/

**Tests**: Tests are **REQUIRED** (NON-NEGOTIABLE). Every functional/implementation task MUST have a corresponding test task generated BEFORE it. Do not skip test generation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] [Rule] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- **[Rule]**: 该任务追溯的规则编号（如 FR-001），支撑 gate 的规则对齐校验
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  The __SPECKIT_COMMAND_TASKS__ command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment

  TDD IS MANDATORY (testing-tdd preset): for every implementation task, a test
  task MUST be generated first and ordered BEFORE the implementation task.
  Skeletons (Phase 2) MUST be created first and MUST pass `mvn test-compile`
  (EXIT=0, 测试骨架存在时) before any test task -- TDD's Red = assertion
  failure per the 3 conditions (see each test zone below), NOT compile failure.
  DO NOT keep these sample tasks in the generated tasks.md file.

  双标签说明：每个任务带 [USx] 与 [FR-xxx] 两个标签——
  - [USx] 是 spec-kit 的 user-story 组织索引键（核心 tasks 工作流按 story
    组织任务，去掉会破坏核心工作流）
  - [FR-xxx] 是 testing 扩展的规则追溯维度，标注该任务实现的 spec.md FR 段
    规则编号（如 FR-001），支撑 gate 的规则对齐校验

  测试任务 MUST 参考 test-plan.md 用例清单生成（存在时）：
  - 单测任务引用 UT-xx 编号（如 "per test-plan.md UT-01..UT-03 (FR-001
    正常/异常/边界)"），用例数量与 test-plan.md 对齐（每条 SpecRule 至少 3 条
    单测：正常/异常/边界），不得臆造用例数量
  - test-plan.md 缺失时（未运行 speckit.testing.plan）：按 contracts/ 与
    spec.md FR 段推导测试任务，并在生成的 tasks.md 顶部注明"未参考
    test-plan.md（未运行 speckit.testing.plan）"
  ============================================================================
  -->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize [language] project with [framework] dependencies
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on your project):

- [ ] T004 Setup database schema and migrations framework
- [ ] T005 [P] Implement authentication/authorization framework
- [ ] T006 [P] Setup API routing and middleware structure
- [ ] T007 Create base models/entities that all stories depend on
- [ ] T008 Configure error handling and logging infrastructure
- [ ] T009 Setup environment configuration management
- [ ] T010 [P] Create interface skeletons in src/main/java/{{package}}/ (from contracts/ — method signatures + return types, no implementation)
- [ ] T011 [P] Create data model skeletons in src/main/java/{{package}}/model/ (entities, enums, value objects — fields only, no logic)
- [ ] T012 [P] Create enum skeletons for error codes / status codes (from spec.md Error Code Definitions)
- [ ] T013 [P] Create Service skeletons in src/main/java/{{package}}/service/ (empty method bodies throwing UnsupportedOperationException)
- [ ] T014 Run `mvn test-compile` checkpoint -- skeletons MUST compile WITH test skeletons present (EXIT=0; compiles main + test sources so test signatures match skeleton interfaces)

**Checkpoint**: Foundation + skeletons ready -- `mvn test-compile` passes (EXIT=0, 测试骨架存在时), user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (REQUIRED - TDD) ⚠️

> **MANDATORY: Write these tests FIRST, ensure they FAIL (Red) before ANY implementation task (Green).** Do not skip this subsection.
> 测试任务数量与内容以 test-plan.md 用例清单为准（存在时）：单测按 UT-xx（每规则至少 3 条：正常/异常/边界）；下方为样板，生成时按实际用例展开。
> 规则标注双通道：JUnit5 `@DisplayName("FR-xxx-Rm-<描述>")`；JUnit4 测试方法级 `@Spec(rule="FR-xxx")`。

> **Red evidence -- ALL 3 MUST hold（Red 判定三条件，命令级硬规则）**：
> ① `mvn test-compile` EXIT=0（骨架接口与测试签名一致）；
> ② `mvn test -Dtest=<XxxTest>` 输出含断言失败特征（`Failures: N>0` 或
>    `AssertionFailedError` / `expected: ... but was: ...`）；
> ③ 编译错误（COMPILATION ERROR / cannot find symbol）**不是 Red**——骨架未
>    完成，回补骨架后再验 ①+②。
> **禁止**：用 `mvn compile`（仅 main）或 `mvn test-compile` 通过汇报 Red；
> 禁止在编译失败时陈述"断言失败"（编译失败时断言未运行）。

- [ ] T015 [P] [US1] [FR-001] Unit test per test-plan.md UT-xx for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java (JUnit4/5 + Mockito, 规则标注 @DisplayName 或测试方法级 @Spec)

### Implementation for User Story 1

> These tasks MUST come AFTER the test tasks above (Red-Green order).

- [ ] T016 [P] [US1] [FR-001] Create [Entity1] model in src/main/java/{{package}}/model/[Entity1].java
- [ ] T017 [P] [US1] [FR-001] Create [Entity2] model in src/main/java/{{package}}/model/[Entity2].java
- [ ] T018 [US1] [FR-001] Implement [Service] in src/main/java/{{package}}/service/[Service].java (depends on T016, T017)
- [ ] T019 [US1] [FR-001] Implement [endpoint/feature] in src/main/java/{{package}}/[location]/[File].java
- [ ] T020 [US1] [FR-001] Add validation and error handling
- [ ] T021 [US1] [FR-001] Add logging for user story 1 operations

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (REQUIRED - TDD) ⚠️

> **MANDATORY: Write these tests FIRST, ensure they FAIL (Red) before implementation.**
> 按 test-plan.md UT-xx 用例清单生成，缺失时按 contracts/ + spec.md FR 段推导。
> Red 判定三条件同 User Story 1（① test-compile EXIT=0 ② 断言失败特征 ③ 编译错误不是 Red）。

- [ ] T022 [P] [US2] [FR-002] Unit test per test-plan.md UT-xx for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java (JUnit4/5 + Mockito, 规则标注 @DisplayName 或测试方法级 @Spec)

### Implementation for User Story 2

> These tasks MUST come AFTER the test tasks above (Red-Green order).

- [ ] T023 [P] [US2] [FR-002] Create [Entity] model in src/main/java/{{package}}/model/[Entity].java
- [ ] T024 [US2] [FR-002] Implement [Service] in src/main/java/{{package}}/service/[Service].java
- [ ] T025 [US2] [FR-002] Implement [endpoint/feature] in src/main/java/{{package}}/[location]/[File].java
- [ ] T026 [US2] [FR-002] Integrate with User Story 1 components (if needed)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (REQUIRED - TDD) ⚠️

> **MANDATORY: Write these tests FIRST, ensure they FAIL (Red) before implementation.**
> 按 test-plan.md UT-xx 用例清单生成，缺失时按 contracts/ + spec.md FR 段推导。
> Red 判定三条件同 User Story 1。

- [ ] T027 [P] [US3] [FR-003] Unit test per test-plan.md UT-xx for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java (JUnit4/5 + Mockito, 规则标注 @DisplayName 或测试方法级 @Spec)

### Implementation for User Story 3

> These tasks MUST come AFTER the test tasks above (Red-Green order).

- [ ] T028 [P] [US3] [FR-003] Create [Entity] model in src/main/java/{{package}}/model/[Entity].java
- [ ] T029 [US3] [FR-003] Implement [Service] in src/main/java/{{package}}/service/[Service].java
- [ ] T030 [US3] [FR-003] Implement [endpoint/feature] in src/main/java/{{package}}/[location]/[File].java

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern: Tests (REQUIRED, first) -> Implementation (after)]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit tests in src/test/java/{{package}}/unit/
- [ ] TXXX Security hardening
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories (includes skeletons T010-T014 which MUST pass `mvn test-compile` (EXIT=0) before any test tasks)
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 -> P2 -> P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story (TDD - MANDATORY)

- Skeletons (Phase 2) MUST pass `mvn test-compile` (EXIT=0) before any test tasks (TDD's Red = assertion failure per the 3 conditions, not compile failure)
- Unit tests MUST be written and confirmed to FAIL before implementation (Red phase)
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories, includes compiling skeletons)
3. Complete Phase 3: User Story 1 (tests FIRST, then implementation)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready (skeletons compile)
2. Add User Story 1 (TDD) -> Test independently -> Deploy/Demo (MVP!)
3. Add User Story 2 (TDD) -> Test independently -> Deploy/Demo
4. Add User Story 3 (TDD) -> Test independently -> Deploy/Demo
5. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- **Tests are REQUIRED (testing-tdd preset): 单测先行 -- verify unit tests FAIL (Red) before implementation**
- **Skeletons (Phase 2) MUST pass `mvn test-compile`（EXIT=0）before any test task -- TDD's Red = Red 判定三条件（断言失败特征），编译错误不是 Red**
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- NEVER skip test tasks - TDD is non-negotiable in this preset