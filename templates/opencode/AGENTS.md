# SDD OpenCode Instructions

This workspace uses SDD as the design-first workflow.

Start by checking the attached project and feature state:

```powershell
sdd-pipeline.show_attachment
sdd-pipeline.flow_status {"feature_dir":"specs/<feature_name>"}
```

Use `sdd-project-explorer` whenever you need existing class, module, method, or design-participant facts.

Use `sdd-arch-standard` whenever a feature touches API, payment, idempotency, external calls, database changes, transactions, or layering.

Use `sdd-pipeline` as the preferred entry for flow control and governance artifacts such as task slices, Gate 5, release-gate, and report validation.

Do not produce implementation changes until the relevant SDD gates have passed or the user explicitly asks for exploratory code.

For the normal flow:

```powershell
python scripts/run_pipeline.py generate-feature-brief <source_file_path> <feature_name>
python scripts/run_pipeline.py generate-design specs/<feature_name>
python scripts/run_pipeline.py gate2 specs/<feature_name>
python scripts/run_pipeline.py gate3 specs/<feature_name>
python scripts/run_pipeline.py gate4 specs/<feature_name>
sdd-pipeline.gate5 {"feature_dir":"specs/<feature_name>"}
```

If the host environment blocks Node subprocess execution, fall back to direct `python scripts/run_pipeline.py ...` commands.
