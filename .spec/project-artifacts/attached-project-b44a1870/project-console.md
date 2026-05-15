# Project Console

- Feature count: `3`

## Project Context

- Project ID: `attached-project-b44a1870`
- Project Name: `attached-project`
- Artifacts Dir: `D:\project\SDD\.spec\project-artifacts\attached-project-b44a1870`

## Workspace

- Active Profile: `attached-project`
- Active Project ID: `attached-project-b44a1870`
- Profile Count: `2`

## Stage Distribution

- `implementation-needs-attention`: 1
- `release-ready`: 2

## State Sources

- `project-state.json`: 3

## Gate Summary

- `gate2.PASS`: 3
- `gate3.WARN`: 0
- `gate3_ai.WARN`: 0
- `gate5.FAIL`: 1

## Current Recommendation

- Feature: `admin-management`
- Stage: `implementation-needs-attention`
- Source: `project-state.json`
- Risk: `high`
- Strict: `strict`
- Reason: implementation-stage gates contain failures; implementation traceability=WARN; real-test admission=FAIL missingReq=3; attached execution=FAIL; gate5 admission=FAIL
- Command: `python scripts/run_pipeline.py approved-implementation-cycle D:\project\SDD\specs\admin-management --strict`

## Recent Execution

- None

## Recent Operations

- None

## Tooling Hygiene

- tooling-hygiene artifact is not available yet.

## Resolution Preview


## Features

| Feature | Stage | Source | Risk | Strict | Approval | gate2 | gate3 | gate4 | gate5 | impl | Gate3 AI | Gate5 Admission | Real Test Admission | Attached Execution | Component Execution | Framework Evidence | Resource Claims | Release Exception | Missing | Blockers | Next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| admin-management | implementation-needs-attention | project-state.json | high | strict | APPROVED | PASS | PASS | PASS | FAIL | WARN | SKIPPED not-configured | FAIL fail=attached_execution,real_test_req | FAIL high-risk-p0-req missing=3 | FAIL required explicit-cli | PASS | N/A | op=1 | N/A | 0 | 10 | `python scripts/run_pipeline.py approved-implementation-cycle D:\project\SDD\specs\admin-management --strict` |
| payment-review-control | release-ready | project-state.json | high | recommended | APPROVED | PASS | PASS | PASS | PASS | PASS | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 | 0 | `None` |
| task-board | release-ready | project-state.json | high | recommended | APPROVED | PASS | PASS | PASS | PASS | WARN | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 | 6 | `None` |
