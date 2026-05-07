# SDD Agent Instructions

You are working with the SDD tool repository.

## Core Rule

Design comes before implementation. Do not jump into code changes until the feature brief, design document, design pack, and gates are in the expected state.

## Workflow

1. Inspect the current state first:

```powershell
sdd-pipeline.show_attachment
sdd-pipeline.flow_status {"feature_dir":"specs/<feature_name>"}
```

2. For PRD or requirement input, generate a feature brief:

```powershell
python scripts/run_pipeline.py generate-feature-brief <source_file_path> <feature_name>
```

3. Do not proceed while `[AMBIGUOUS: ...]` items remain unresolved.

4. For design generation and validation, use:

```powershell
python scripts/run_pipeline.py generate-design specs/<feature_name>
python scripts/run_pipeline.py gate2 specs/<feature_name>
python scripts/run_pipeline.py gate3 specs/<feature_name>
```

5. For implementation traceability, use:

```powershell
python scripts/run_pipeline.py gate4 specs/<feature_name>
sdd-pipeline.gate5 {"feature_dir":"specs/<feature_name>"}
```

## MCP Usage

Use `sdd-project-explorer` before referencing existing classes, modules, or methods.

Use `sdd-arch-standard` before writing or reviewing architecture-sensitive design sections.

Use `sdd-pipeline` as the preferred entry for attachment lookup, flow-status, task-slice generation, Gate 5, release-gate, and report validation. If the host environment blocks Node subprocess execution, fall back to direct `python scripts/run_pipeline.py ...` commands.

Never invent brownfield classes, tables, APIs, or state machines without evidence from project facts or explicit user confirmation.
