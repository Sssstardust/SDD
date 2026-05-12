from __future__ import annotations

from pathlib import Path

from versioning import detect_latest_design_path, reports_dir_for_design


def assert_feature_within_attachment(feature_dir: Path, attachment_cfg: dict[str, object] | None) -> None:
    if not isinstance(attachment_cfg, dict):
        return
    design_roots = attachment_cfg.get("design_roots")
    if not isinstance(design_roots, list) or not design_roots:
        return

    feature_resolved = feature_dir.resolve()
    roots = [Path(str(item)).resolve() for item in design_roots if isinstance(item, str) and item]
    if any(feature_resolved == root or root in feature_resolved.parents for root in roots):
        return

    raise ValueError(
        f"feature directory '{feature_dir}' is not within current attachment design_roots: "
        f"{', '.join(str(root) for root in roots)}"
    )


def missing_feature_prerequisites(
    feature_dir: Path,
    *,
    require_feature_brief: bool = False,
    require_design: bool = False,
    require_approval: bool = False,
    require_task_slices_manifest: bool = False,
    require_task_slice_files: bool = False,
) -> list[str]:
    missing: list[str] = []

    feature_brief = feature_dir / "feature-brief.md"
    if require_feature_brief and not feature_brief.exists():
        missing.append(f"missing feature-brief.md: {feature_brief}")

    design_path = detect_latest_design_path(feature_dir)
    if require_design and not design_path.exists():
        missing.append(f"missing design document: {design_path}")

    if require_approval:
        approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"
        if not approval_path.exists():
            missing.append(f"missing approval.json: {approval_path}")

    if require_task_slices_manifest:
        manifest_path = feature_dir / "tasks" / "task-slices.generated.json"
        if not manifest_path.exists():
            missing.append(f"missing task-slices.generated.json: {manifest_path}")

    if require_task_slice_files:
        task_files = sorted((feature_dir / "tasks").glob("slice-*.md"))
        if not task_files:
            missing.append(f"missing task slice files: {feature_dir / 'tasks'}")

    return missing


def assert_feature_prerequisites(feature_dir: Path, **kwargs: bool) -> None:
    missing = missing_feature_prerequisites(feature_dir, **kwargs)
    if missing:
        raise ValueError("feature prerequisites not satisfied:\n- " + "\n- ".join(missing))
