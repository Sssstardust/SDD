# SDD Standard Agent Instructions

You are an expert developer using the **SDD (Spec-Driven Development)** methodology.

## 🛡️ Core Mandate: Design First
**Design comes before implementation.** Never modify implementation code until the requirements are structured and the architecture design is validated.

## 🚀 Unified Workflow (Semantic Actions)

Use the following semantic actions via `sdd_core/run_pipeline.py` or the `sdd-pipeline` MCP:

### 1. Analyze (PRD -> Structured Requirements)
Transform raw PRD into a validated `需求规格.md`.
```powershell
python sdd_core/run_pipeline.py analyze <source_file_path> <feature_name>
```
*   **Ambiguity Check**: Identify and mark unresolved items as `[AMBIGUOUS: ...]`. Do not proceed to design while open ambiguities exist.

### 2. Design (Requirements -> Technical Solution)
Generate technical design documents and design packs.
```powershell
python sdd_core/run_pipeline.py design <feature_name>
```
*   **Fact-Based**: Never invent classes, tables, or APIs. Use `sdd-project-explorer` to fetch real project facts.

### 3. Validate (Design -> Architecture Audit)
Run comprehensive multi-gate validation (Gate 1/2/3).
```powershell
python sdd_core/run_pipeline.py validate <feature_name>
```
*   **Standard Alignment**: Use `sdd-arch-standard` to ensure compliance with layering, naming, and security rules.

## 🛠️ Tooling & MCPs

- **`sdd-project-explorer`**: Use before referencing existing code elements to ensure factual accuracy.
- **`sdd-arch-standard`**: Use for auditing design chapters against architecture guidelines.
- **`sdd-pipeline`**: Preferred entry for status tracking (`flow-status`), task slicing, and high-level orchestration.

## 📝 Troubleshooting
If the host environment blocks Node subprocesses, fall back to direct execution: `python sdd_core/run_pipeline.py <command>`.
