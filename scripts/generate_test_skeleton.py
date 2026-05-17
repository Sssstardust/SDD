#!/usr/bin/env python3
"""
generate_test_skeleton.py

从 specs/<feature>/tasks/*.md 中提取 req_ids / acceptance_checks / test_spec，
生成最小可用的测试骨架和 REQ-ID -> 测试方法映射表。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from concurrency import atomic_write_text, feature_lock
from gate_report import write_gate_section
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir
from domain.attached_project import load_attachment_config, is_fixture_attachment
from infrastructure.baseline_paths import get_active_baseline_dir
from domain.baseline import ModuleMapDocument
from domain.feature_brief import FeatureBrief


ROOT = Path(__file__).resolve().parent.parent


def ensure_task_slices(feature_dir: Path) -> int:
    command = [sys.executable, str(ROOT / "scripts" / "generate_task_slices.py"), str(feature_dir)]
    return subprocess.run(command, check=False).returncode


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_list_block(text: str, key: str) -> list[str]:
    items: list[str] = []
    lines = text.splitlines()
    in_block = False
    base_indent = 0
    for line in lines:
        if not in_block:
            if re.match(rf"^\s*{re.escape(key)}\s*:\s*$", line):
                in_block = True
                base_indent = len(line) - len(line.lstrip())
            continue

        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break

        stripped = line.strip()
        if stripped.startswith("- "):
            value = stripped[2:].strip().strip('"').strip("'")
            if value:
                items.append(value)
    return items


def extract_inline_list(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*\[(.*?)\]\s*$", text)
    if not match:
        return []

    body = match.group(1).strip()
    if not body:
        return []

    return [item.strip().strip('"').strip("'") for item in body.split(",") if item.strip()]


def extract_list_field(text: str, key: str) -> list[str]:
    items = extract_list_block(text, key)
    return items if items else extract_inline_list(text, key)


def extract_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_requirement_priorities(yaml_text: str) -> dict[str, str]:
    lines = yaml_text.splitlines()
    in_requirements = False
    base_indent = 0
    current_req: str | None = None
    priorities: dict[str, str] = {}

    for line in lines:
        if not in_requirements:
            if re.match(r"^\s*requirements\s*:\s*$", line):
                in_requirements = True
                base_indent = len(line) - len(line.lstrip())
            continue

        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break

        req_match = re.match(r"^\s*-\s*req_id\s*:\s*(REQ-\d+)\s*$", line)
        if req_match:
            current_req = req_match.group(1)
            continue

        pri_match = re.match(r"^\s*priority\s*:\s*(P\d+)\s*$", line)
        if pri_match and current_req:
            priorities[current_req] = pri_match.group(1)

    return priorities


def extract_requirement_ids(yaml_text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s*-\s*req_id\s*:\s*(REQ-\d+)\s*$", yaml_text))


def extract_design_acceptance_matrix(design_text: str) -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {}
    for raw_line in design_text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|"):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue

        req_id = cells[0]
        acceptance = cells[2]
        if req_id == "REQ-ID" or req_id.startswith("---"):
            continue
        if not re.fullmatch(r"REQ-\d+", req_id):
            continue

        matrix.setdefault(req_id, []).append(acceptance)

    return matrix


def normalize_for_match(value: str) -> str:
    return re.sub(r"[\s`'\"，。；：、,./\\\-()（）]+", "", value).lower()


def extract_test_cases(text: str) -> list[dict[str, str]]:
    yaml_text = "\n".join(extract_yaml_blocks(text))
    lines = yaml_text.splitlines()
    cases: list[dict[str, str]] = []
    in_cases = False
    base_indent = 0
    current: dict[str, str] | None = None

    for line in lines:
        if not in_cases:
            if re.match(r"^\s*cases\s*:\s*$", line):
                in_cases = True
                base_indent = len(line) - len(line.lstrip())
            continue

        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break

        id_match = re.match(r"^\s*-\s*id\s*:\s*(\S+)\s*$", line)
        if id_match:
            if current:
                cases.append(current)
            current = {"id": id_match.group(1).strip()}
            continue

        req_match = re.match(r"^\s*req_id\s*:\s*(REQ-\d+)\s*$", line)
        if req_match and current is not None:
            current["req_id"] = req_match.group(1).strip()
            continue

        desc_match = re.match(r"^\s*description\s*:\s*\"?(.*?)\"?\s*$", line)
        if desc_match and current is not None:
            current["description"] = desc_match.group(1).strip()

    if current:
        cases.append(current)

    return [case for case in cases if {"id", "req_id", "description"} <= case.keys()]


def parse_feature_brief(feature_brief: Path) -> dict[str, object]:
    yaml_text = "\n".join(extract_yaml_blocks(read_text(feature_brief)))
    return {
        "feature_name": extract_scalar(yaml_text, "feature_name") or feature_brief.parent.name,
        "priorities": extract_requirement_priorities(yaml_text),
        "requirement_ids": extract_requirement_ids(yaml_text),
    }


def parse_task_slice(task_file: Path) -> dict[str, object]:
    text = read_text(task_file)
    yaml_text = "\n".join(extract_yaml_blocks(text))
    return {
        "path": task_file,
        "slice_file": task_file.name,
        "slice_id": extract_scalar(yaml_text, "slice_id") or task_file.stem.upper(),
        "depends_on": extract_list_field(yaml_text, "depends_on"),
        "req_ids": extract_list_field(yaml_text, "req_ids"),
        "acceptance_checks": extract_list_field(yaml_text, "acceptance_checks"),
        "cases": extract_test_cases(text),
    }


def validate_task_slices(
    slices: list[dict[str, object]],
    *,
    requirement_ids: set[str],
    design_acceptance_matrix: dict[str, list[str]],
) -> tuple[list[str], list[dict[str, object]]]:
    errors: list[str] = []
    ordered_slices: list[dict[str, object]] = []
    seen_slice_ids: set[str] = set()
    slice_by_id: dict[str, dict[str, object]] = {}

    for slice_meta in slices:
        slice_id = str(slice_meta["slice_id"])
        if not slice_id:
            errors.append(f"{slice_meta['slice_file']} 缺少 slice_id")
            continue
        if slice_id in seen_slice_ids:
            errors.append(f"slice_id 重复: {slice_id}")
            continue
        seen_slice_ids.add(slice_id)
        slice_by_id[slice_id] = slice_meta

    for slice_meta in slices:
        slice_file = str(slice_meta["slice_file"])
        slice_id = str(slice_meta["slice_id"])
        req_ids = [str(item) for item in slice_meta["req_ids"]]
        acceptance_checks = [str(item) for item in slice_meta["acceptance_checks"]]
        depends_on = [str(item) for item in slice_meta["depends_on"]]
        cases = [case for case in slice_meta["cases"] if isinstance(case, dict)]

        if not req_ids:
            errors.append(f"{slice_file} 缺少 req_ids")
        if not acceptance_checks:
            errors.append(f"{slice_file} 缺少 acceptance_checks")

        unknown_req_ids = [req_id for req_id in req_ids if req_id not in requirement_ids]
        if unknown_req_ids:
            errors.append(f"{slice_file} 引用了 feature-brief 中不存在的 req_ids: {', '.join(unknown_req_ids)}")

        allowed_acceptance_checks: set[str] = set()
        for req_id in req_ids:
            design_checks = design_acceptance_matrix.get(req_id, [])
            if not design_checks:
                errors.append(f"{slice_file} 的 req_id {req_id} 未在 design 验收矩阵中找到")
            allowed_acceptance_checks.update(normalize_for_match(item) for item in design_checks)

        # 定义允许的自动生成技术校验点模式
        tech_check_prefixes = ("接口", "实体", "输入校验", "领域实体", "CRUD", "数据库", "异步", "超时", "熔断", "降级")

        for check in acceptance_checks:
            normalized_check = normalize_for_match(check)
            if normalized_check in allowed_acceptance_checks:
                continue
            
            # 如果是标准技术校验点，允许跳过设计矩阵匹配
            if any(check.startswith(prefix) for prefix in tech_check_prefixes):
                continue
                
            errors.append(f"{slice_file} 的 acceptance_checks 未映射回 design 验收矩阵: {check}")

        for case in cases:
            case_req_id = str(case.get("req_id") or "")
            if case_req_id and case_req_id not in req_ids:
                errors.append(f"{slice_file} 的 test_spec.cases 引用了未在 req_ids 中声明的 req_id: {case_req_id}")

        for parent_slice_id in depends_on:
            if parent_slice_id == slice_id:
                errors.append(f"{slice_file} 的 depends_on 不能依赖自身: {slice_id}")
            elif parent_slice_id not in slice_by_id:
                errors.append(f"{slice_file} 的 depends_on 引用了不存在的切片: {parent_slice_id}")

    if errors:
        return errors, ordered_slices

    indegree = {slice_id: 0 for slice_id in slice_by_id}
    graph: dict[str, list[str]] = {slice_id: [] for slice_id in slice_by_id}
    for slice_meta in slices:
        current_slice_id = str(slice_meta["slice_id"])
        for parent_slice_id in [str(item) for item in slice_meta["depends_on"]]:
            graph.setdefault(parent_slice_id, []).append(current_slice_id)
            indegree[current_slice_id] += 1

    ready = sorted([slice_id for slice_id, degree in indegree.items() if degree == 0])
    while ready:
        slice_id = ready.pop(0)
        ordered_slices.append(slice_by_id[slice_id])
        for child_slice_id in sorted(graph.get(slice_id, [])):
            indegree[child_slice_id] -= 1
            if indegree[child_slice_id] == 0:
                ready.append(child_slice_id)
                ready.sort()

    if len(ordered_slices) != len(slices):
        errors.append("切片 depends_on 存在循环依赖，无法得到合法拓扑序")

    return errors, ordered_slices


def to_pascal_case(name: str) -> str:
    parts = re.split(r"[-_\s]+", name)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def sanitize_identifier(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value.lower() or "case"


def deduplicate_mappings(mappings: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen_methods: set[str] = set()
    for mapping in mappings:
        method_name = mapping["test_method"]
        if method_name in seen_methods:
            continue
        seen_methods.add(method_name)
        deduped.append(mapping)
    return deduped


def resolve_primary_business_package(brief: FeatureBrief, feature_dir: Path) -> str | None:
    """尝试通过 logic_atoms 与 module-map 定位核心业务类的包路径。"""
    if not brief.logic_atoms:
        return None
    
    # 获取第一个被提及的组件
    first_atom = brief.logic_atoms[0]
    logic_steps = first_atom.get("logic", [])
    if not logic_steps:
        return None
    
    primary_comp = str(logic_steps[0].get("component", ""))
    if not primary_comp:
        return None
    
    # 查找 module-map
    baseline_dir = get_active_baseline_dir()
    if not baseline_dir:
        return None
    
    module_map_path = baseline_dir / "module-map.json"
    if not module_map_path.exists():
        return None
        
    try:
        mmap = ModuleMapDocument.from_json_file(module_map_path)
        for cls_info in mmap.classes:
            if cls_info.get("simple_name") == primary_comp:
                pkg = cls_info.get("package")
                return str(pkg) if pkg else None
    except Exception:
        pass
    return None


def build_java_test(feature_name: str, mappings: list[dict[str, str]], *, package_name: str | None = None) -> str:
    class_name = f"{to_pascal_case(feature_name)}DesignVerificationTest"
    lines = []
    if package_name:
        lines.append(f"package {package_name};")
        lines.append("")

    lines.extend([
        "/**",
        " * 自动生成测试骨架（最小版本）",
        f" * 对应 feature: {feature_name}",
        " */",
        f"public class {class_name} {{",
        "",
    ])

    for mapping in mappings:
        req_id = mapping["req_id"]
        method_name = mapping["test_method"]
        description = mapping["description"]
        lines.extend(
            [
                f"    // {req_id}: {description}",
                f"    public void {method_name}() {{",
                f"        // TODO[{req_id}]: 补全断言与测试步骤",
                "    }",
                "",
            ]
        )

    lines.extend(
        [
            "    public static void main(String[] args) {",
            f"        {class_name} test = new {class_name}();",
        ]
    )
    for mapping in mappings:
        lines.append(f"        test.{mapping['test_method']}();")
    lines.extend(
        [
            "    }",
            "",
        ]
    )

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def should_preserve_existing_test(test_file: Path, mappings: list[dict[str, str]]) -> bool:
    if not test_file.exists():
        return False

    content = test_file.read_text(encoding="utf-8")
    if "TODO[" in content:
        return False

    return all(mapping["test_method"] in content for mapping in mappings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    if not feature_dir.exists():
        print(f"[ERROR] feature 目录不存在: {feature_dir}")
        return 1

    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    # 解析 Brief 以获取 logic_atoms
    brief_content = feature_brief.read_text(encoding="utf-8")
    brief_domain = FeatureBrief.from_text(brief_content, feature_dir_name=feature_dir.name)

    feature_meta = parse_feature_brief(feature_brief)
    feature_name = str(feature_meta["feature_name"])
    priorities: dict[str, str] = feature_meta["priorities"]  # type: ignore[assignment]
    requirement_ids: set[str] = feature_meta["requirement_ids"]  # type: ignore[assignment]
    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] 缺少设计文档: {design_path}")
        return 1
    design_text = read_text(design_path)
    design_acceptance_matrix = extract_design_acceptance_matrix(design_text)

    task_files = sorted((feature_dir / "tasks").glob("slice-*.md"))
    if not task_files:
        print("[WARN] 未找到 slice-*.md，尝试先生成 task slices")
        if ensure_task_slices(feature_dir) == 0:
            task_files = sorted((feature_dir / "tasks").glob("slice-*.md"))
    if not task_files:
        print("[ERROR] 未找到任何 slice-*.md")
        return 1

    slices = [parse_task_slice(task_file) for task_file in task_files]
    validation_errors, ordered_slices = validate_task_slices(
        slices,
        requirement_ids=requirement_ids,
        design_acceptance_matrix=design_acceptance_matrix,
    )

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    reports_dir.mkdir(parents=True, exist_ok=True)
    skeleton_report = reports_dir / "gate4-skeleton.json"

    if validation_errors:
        gate_report = write_gate_section(
            reports_dir,
            gate_name="gate4",
            feature_name=feature_name,
            design_version=design_path.name,
            payload={
                "result": "FAIL",
                "test_file": "",
                "test_file_preserved": False,
                "mapping_count": 0,
                "report_file": str(skeleton_report),
                "warnings": [],
                "errors": validation_errors,
            },
        )
        print("[FAIL] Gate 4 切片校验失败")
        for error in validation_errors:
            print(f"  - {error}")
        print(f"  - gate:   {gate_report}")
        return 1

    mappings: list[dict[str, str]] = []
    for slice_meta in ordered_slices:
        task_file = slice_meta["path"]
        req_ids = [str(item) for item in slice_meta["req_ids"]]
        acceptance_checks = [str(item) for item in slice_meta["acceptance_checks"]]
        cases = [case for case in slice_meta["cases"] if isinstance(case, dict)]

        if not cases:
            for index, req_id in enumerate(req_ids, start=1):
                description = acceptance_checks[index - 1] if index - 1 < len(acceptance_checks) else req_id
                cases.append({"id": f"TC-{index:03d}", "req_id": req_id, "description": description})

        for case in cases:
            req_id = case["req_id"]
            method_name = f"test_{sanitize_identifier(req_id)}_{sanitize_identifier(case['description'])}"
            mappings.append(
                {
                    "slice_file": task_file.name,
                    "slice_id": str(slice_meta["slice_id"]),
                    "req_id": req_id,
                    "priority": priorities.get(req_id, "P1"),
                    "description": case["description"],
                    "case_id": case["id"],
                    "test_method": method_name,
                }
            )

    mappings = deduplicate_mappings(mappings)

    # 路径决策逻辑：优先使用附着项目目录
    attachment = load_attachment_config()
    target_project_root: Path | None = None
    if attachment:
        project_root_str = attachment.get("project_root")
        if isinstance(project_root_str, str) and project_root_str:
            root_path = Path(project_root_str).resolve()
            if not is_fixture_attachment(root_path):
                target_project_root = root_path

    sanitized_feature_name = sanitize_identifier(feature_name)
    
    # 默认路径
    test_dir = ROOT / "src" / "test" / "java" / "generated" / "design" / feature_name
    package_name = None

    if target_project_root:
        target_test_root = target_project_root / "src" / "test" / "java"
        if target_test_root.exists():
            # 尝试精准对齐包路径
            biz_package = resolve_primary_business_package(brief_domain, feature_dir)
            if biz_package:
                test_dir = target_test_root / biz_package.replace(".", "/")
                package_name = biz_package
            else:
                # 回退到 sdd.generated
                test_dir = target_test_root / "sdd" / "generated" / sanitized_feature_name
                package_name = f"sdd.generated.{sanitized_feature_name}"

    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / f"{to_pascal_case(feature_name)}DesignVerificationTest.java"

    with feature_lock(feature_dir, phase="generate-test-skeleton"):
        preserved = should_preserve_existing_test(test_file, mappings)
        if not preserved:
            atomic_write_text(test_file, build_java_test(feature_name, mappings, package_name=package_name), encoding="utf-8")

        report = {
            "feature_name": feature_name,
            "design_version": design_path.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "test_file": str(test_file),
            "test_file_preserved": preserved,
            "mappings": mappings,
        }
        atomic_write_text(skeleton_report, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    gate_report = write_gate_section(
        reports_dir,
        gate_name="gate4",
        feature_name=feature_name,
        design_version=design_path.name,
        payload={
            "result": "PASS",
            "test_file": str(test_file),
            "test_file_preserved": preserved,
            "mapping_count": len(mappings),
            "report_file": str(skeleton_report),
            "warnings": [],
            "errors": [],
        },
    )

    print("[OK] Gate 4 测试骨架生成完成")
    print(f"  - report: {skeleton_report}")
    print(f"  - gate:   {gate_report}")
    print(f"  - test:   {test_file}")
    print(f"  - preserved: {'yes' if preserved else 'no'}")
    print(f"  - count:  {len(mappings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
