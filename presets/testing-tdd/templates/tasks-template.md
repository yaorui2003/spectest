---

description: "Task list template for feature implementation (testing-tdd preset: TDD REQUIRED)"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are **REQUIRED** (NON-NEGOTIABLE). Every functional/implementation task MUST have a corresponding test task generated BEFORE it. Do not skip test generation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
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
  Skeletons (Phase 2) MUST be created first so tests compile (Red = assertion
  failure, not compile failure).
  DO NOT keep these sample tasks in the generated tasks.md file.
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
- [ ] T014 Run `mvn compile` checkpoint -- skeletons MUST compile (no test code yet, just compile main sources)

**Checkpoint**: Foundation + skeletons ready -- `mvn compile` passes, user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (REQUIRED - TDD) ⚠️

> **MANDATORY: Write these tests FIRST, ensure they FAIL (Red) before ANY implementation task (Green).** Do not skip this subsection.

- [ ] T015 [P] [US1] Unit test for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java (JUnit5 + Mockito, @DisplayName("R<n>-<描述>"))
- [ ] T016 [P] [US1] Contract test for [endpoint] in src/test/java/{{package}}/contract/[Contract]ContractTest.java (WireMock, @DisplayName("R<n>-<描述>"))

### Implementation for User Story 1

> These tasks MUST come AFTER the test tasks above (Red-Green order).

- [ ] T017 [P] [US1] Create [Entity1] model in src/main/java/{{package}}/model/[Entity1].java
- [ ] T018 [P] [US1] Create [Entity2] model in src/main/java/{{package}}/model/[Entity2].java
- [ ] T019 [US1] Implement [Service] in src/main/java/{{package}}/service/[Service].java (depends on T017, T018)
- [ ] T020 [US1] Implement [endpoint/feature] in src/main/java/{{package}}/[location]/[File].java
- [ ] T021 [US1] Add validation and error handling
- [ ] T022 [US1] Add logging for user story 1 operations

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (REQUIRED - TDD) ⚠️

> **MANDATORY: Write these tests FIRST, ensure they FAIL (Red) before implementation.**

- [ ] T023 [P] [US2] Unit test for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java (JUnit5 + Mockito, @DisplayName("R<n>-<描述>"))
- [ ] T024 [P] [US2] Contract test for [endpoint] in src/test/java/{{package}}/contract/[Contract]ContractTest.java (WireMock, @DisplayName("R<n>-<描述>"))

### Implementation for User Story 2

> These tasks MUST come AFTER the test tasks above (Red-Green order).

- [ ] T025 [P] [US2] Create [Entity] model in src/main/java/{{package}}/model/[Entity].java
- [ ] T026 [US2] Implement [Service] in src/main/java/{{package}}/service/[Service].java
- [ ] T027 [US2] Implement [endpoint/feature] in src/main/java/{{package}}/[location]/[File].java
- [ ] T028 [US2] Integrate with User Story 1 components (if needed)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (REQUIRED - TDD) ⚠️

> **MANDATORY: Write these tests FIRST, ensure they FAIL (Red) before implementation.**

- [ ] T029 [P] [US3] Unit test for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java (JUnit5 + Mockito, @DisplayName("R<n>-<描述>"))
- [ ] T030 [P] [US3] Contract test for [endpoint] in src/test/java/{{package}}/contract/[Contract]ContractTest.java (WireMock, @DisplayName("R<n>-<描述>"))

### Implementation for User Story 3

> These tasks MUST come AFTER the test tasks above (Red-Green order).

- [ ] T031 [P] [US3] Create [Entity] model in src/main/java/{{package}}/model/[Entity].java
- [ ] T032 [US3] Implement [Service] in src/main/java/{{package}}/service/[Service].java
- [ ] T033 [US3] Implement [endpoint/feature] in src/main/java/{{package}}/[location]/[File].java

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
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories (includes skeletons T010-T014 which MUST compile before any test tasks)
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 -> P2 -> P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story (TDD - MANDATORY)

- Skeletons (Phase 2) MUST compile before any test tasks (TDD's Red = assertion failure, not compile failure)
- Unit tests MUST be written and confirmed to FAIL before implementation (Red phase)
- Unit test tasks MUST be ordered before contract test tasks (单测先行)
- Contract test tasks MUST be ordered before implementation tasks
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

## Parallel Example: User Story 1

```bash
# Launch all unit tests for User Story 1 together (MUST complete before contract tests):
Task: "Unit test for [user journey] in src/test/java/{{package}}/unit/[Service]Test.java"

# After unit tests FAIL (Red), launch contract tests:
Task: "Contract test for [endpoint] in src/test/java/{{package}}/contract/[Name]ContractTest.java"

# After all tests FAIL (Red), launch implementation:
Task: "Create [Entity1] model in src/main/java/{{package}}/model/[Entity1].java"
Task: "Create [Entity2] model in src/main/java/{{package}}/model/[Entity2].java"
```

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

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently (each follows TDD: tests first)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- **Tests are REQUIRED (testing-tdd preset): 单测先行 -- verify unit tests FAIL before contract tests, contract tests before implementation**
- **Skeletons (Phase 2) MUST compile before test tasks -- TDD's Red = assertion failure, not compile failure**
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- NEVER skip test tasks - TDD is non-negotiable in this preset
