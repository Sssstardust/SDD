# Project Flow Overview

- Feature count: `3`

## Project Context

- Project ID: `arc-web-a602642e`
- Project Name: `attached-project`
- Artifacts Dir: `D:\project\SDD\.spec\project-artifacts\arc-web-a602642e`

## Workspace

- Active Profile: `arc-web`
- Active Project ID: `arc-web-a602642e`
- Profile Count: `2`

## Stage Distribution

- `approved-ready-for-implementation`: 1
- `feature-brief-ready`: 1
- `uninitialized`: 1

## State Sources

- `project-state.json`: 3

## Gate Summary

- `gate2.PASS`: 1
- `gate3.WARN`: 1
- `gate3_ai.WARN`: 0
- `gate5.FAIL`: 0

## Resolution Preview


## Features

| Feature | Stage | Source | Risk | Strict | Approval | gate2 | gate3 | gate4 | gate5 | impl | Gate3 AI | Gate5 Admission | Real Test Admission | Attached Execution | Component Execution | Framework Evidence | Resource Claims | Release Exception | Missing | Blockers | Next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tariff-audit-sync-task-center | uninitialized | project-state.json | low | no | None | None | None | None | None | None | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 1 | 0 | `python scripts/run_pipeline.py init-feature tariff-audit-sync-task-center` |
| order-create | feature-brief-ready | project-state.json | high | strict | None | None | None | None | None | None | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 1 | 0 | `python scripts/run_pipeline.py design-cycle D:\project\PDC2\pdc_src\pdc-arc-root\arc-web\specs\test-naming-convention --strict` |
| vrm-product-integration | approved-ready-for-implementation | project-state.json | low | no | None | PASS | WARN | None | None | None | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 2 | 7 | `python scripts/run_pipeline.py approved-implementation-cycle D:\project\PDC2\pdc_src\pdc-arc-root\arc-web\specs\vrm-product-integration` |
