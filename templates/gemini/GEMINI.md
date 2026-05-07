# SDD Gemini Instructions

Use this repository as the SDD workflow controller.

Before generating or changing implementation code, inspect the SDD state and follow the pipeline gates:

```powershell
sdd-pipeline.show_attachment
sdd-pipeline.flow_status {"feature_dir":"specs/<feature_name>"}
```

When requirements are unclear, mark unresolved items as `[AMBIGUOUS: ...]` and stop before design generation.

Use the MCP tools:

- `sdd-project-explorer` for real project classes, methods, and module facts.
- `sdd-arch-standard` for architecture rules and capability-tag constraints.
- `sdd-pipeline` for attachment lookup, flow-status, Gate 5, release-gate, and report validation.

For design flow:

```powershell
python scripts/run_pipeline.py generate-feature-brief <source_file_path> <feature_name>
python scripts/run_pipeline.py generate-design specs/<feature_name>
python scripts/run_pipeline.py gate2 specs/<feature_name>
python scripts/run_pipeline.py gate3 specs/<feature_name>
```

For implementation traceability:

```powershell
python scripts/run_pipeline.py gate4 specs/<feature_name>
sdd-pipeline.gate5 {"feature_dir":"specs/<feature_name>"}
```

If the host environment blocks Node subprocess execution, fall back to direct `python scripts/run_pipeline.py ...` commands.
