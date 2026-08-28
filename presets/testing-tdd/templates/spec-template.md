# [FEATURE_NAME]

## User Stories

### US1: [Story Title]
As a [role], I want to [action], so that [benefit].

**Acceptance Criteria:**
- [Criterion 1]
- [Criterion 2]

## Functional Requirements

<!-- REQUIRED: List all business rules with FR-xxx numbering (FR-001, FR-002, ...). -->
<!-- Numbers MUST be sequential with leading zeros (FR-001, FR-002, FR-003...). -->
<!-- The testing extension's scan_spec_annotations script parses this section to extract rule IDs. -->
<!-- The validate_spec_format script checks for sequential numbering. -->
<!-- 老项目兼容回落（可选）: 若项目已有 ## Business Rules 段（R1, R2...）且无本节，
     扫描器自动回落该段；新项目一律使用本节 FR-001 格式，无需 Business Rules。 -->

- FR-001: [Rule description]
- FR-002: [Rule description]
- FR-003: [Rule description]

## Requirements

### Non-Functional Requirements
- NFR1: [Requirement]

### Error Code Definitions

<!-- OPTIONAL: Only include this section if the feature defines API error codes. -->
<!-- The validate_spec_format script issues a warning (not error) if this section is absent. -->
<!-- Unit tests use these error codes for negative test cases. -->

| Error Code | HTTP Status | Description | Related Rule |
|------------|------------|-------------|--------------|
| INVALID_AMOUNT | 400 | [Description] | FR-001 |
| ACCOUNT_NOT_FOUND | 404 | [Description] | FR-002 |

## API Endpoints

### [Endpoint Name]
- **Method**: POST
- **Path**: /api/v1/[resource]
- **Request**: [Request body structure]
- **Response**: [Response body structure]
- **Rules**: FR-001, FR-002

## Data Model

[Data model description, link to data-model.md if separate]