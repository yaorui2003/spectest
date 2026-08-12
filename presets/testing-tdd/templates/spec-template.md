# [FEATURE_NAME]

## User Stories

### US1: [Story Title]
As a [role], I want to [action], so that [benefit].

**Acceptance Criteria:**
- [Criterion 1]
- [Criterion 2]

## Business Rules

<!-- REQUIRED: List all business rules with R\d+ numbering. Numbers MUST be sequential (R1, R2, R3...). -->
<!-- The testing extension's scan_spec_annotations script parses this section to extract rule IDs. -->
<!-- The validate_spec_format script checks for sequential numbering. -->

- R1: [Rule description]
- R2: [Rule description]
- R3: [Rule description]

## Requirements

### Functional Requirements
- FR1: [Requirement]

### Non-Functional Requirements
- NFR1: [Requirement]

### Error Code Definitions

<!-- OPTIONAL: Only include this section if the feature defines API error codes. -->
<!-- The validate_spec_format script issues a warning (not error) if this section is absent. -->
<!-- Contract tests use these error codes for negative test cases. -->

| Error Code | HTTP Status | Description | Related Rule |
|------------|------------|-------------|--------------|
| INVALID_AMOUNT | 400 | [Description] | R1 |
| ACCOUNT_NOT_FOUND | 404 | [Description] | R2 |

## API Endpoints

### [Endpoint Name]
- **Method**: POST
- **Path**: /api/v1/[resource]
- **Request**: [Request body structure]
- **Response**: [Response body structure]
- **Rules**: R1, R2

## Data Model

[Data model description, link to data-model.md if separate]
