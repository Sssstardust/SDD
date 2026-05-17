#!/usr/bin/env python3
"""
generate_feature_brief.py

根据 PRD / 需求文本生成第一版 feature-brief.md。
当前版本采用启发式规则，不依赖模型调用。
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from concurrency import atomic_write_text, feature_lock
from versioning import resolve_feature_dir
from domain.requirement_heuristics import (
    has_greenfield_signal,
    infer_capability_tags,
    infer_feature_type,
    infer_risk_tier,
)


ROOT = Path(__file__).resolve().parent.parent


def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def first_heading_or_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if not stripped.startswith(("```", "|")):
            return re.sub(r"^[-*\d\.\)．、\s]+", "", stripped)
    return "auto-feature"


def detect_project_mode(text: str) -> tuple[str, list[str], float]:
    if has_greenfield_signal(text):
        return "greenfield", [f"需求文本命中 greenfield 信号"], 0.85

    evidence: list[str] = []
    if (ROOT / "src" / "main" / "java").exists():
        evidence.append("检测到现有 src/main/java")
    if (ROOT / "specs").exists():
        evidence.append("检测到已有 feature 试点目录")
    if not evidence:
        evidence.append("未命中 greenfield 信号，默认按 brownfield 处理")
    return "brownfield", evidence, 0.80


def split_numbered_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^\d+[\.\)．、]\s+", stripped):
            items.append(re.sub(r"^\d+[\.\)．、]\s+", "", stripped))
    return items


def split_bullets(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^[-*]\s+", stripped):
            items.append(re.sub(r"^[-*]\s+", "", stripped))
    return items


def split_paragraph_sentences(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs:
        for sentence in re.split(r"[。！？；;\n]", paragraph):
            sentence = sentence.strip()
            if len(sentence) >= 10:
                sentences.append(sentence)
    return sentences


def split_candidate_items(text: str) -> list[str]:
    numbered = split_numbered_items(text)
    if numbered:
        return numbered

    bullets = split_bullets(text)
    if bullets:
        return bullets

    return split_paragraph_sentences(text)


def clean_requirement_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -•\t")


def make_requirement_title(text: str) -> str:
    text = clean_requirement_text(text)
    first_clause = re.split(r"[。；;，,：:]", text)[0].strip()
    if len(first_clause) > 24:
        first_clause = first_clause[:24]
    return first_clause or "需求项"


def extract_requirements(text: str) -> list[dict[str, str]]:
    candidates = [clean_requirement_text(item) for item in split_candidate_items(text)]
    candidates = [item for item in candidates if len(item) >= 8]

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = re.sub(r"\s+", "", item[:80])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    if not deduped:
        deduped = ["补充需求说明，当前源文本未能自动抽取出清晰需求项"]

    result: list[dict[str, str]] = []
    for index, item in enumerate(deduped[:5], start=1):
        result.append(
            {
                "req_id": f"REQ-{index:03d}",
                "priority": "P0" if index <= 3 else "P1",
                "title": make_requirement_title(item),
                "description": item,
            }
        )
    return result


def build_one_liner(title: str, requirements: list[dict[str, str]]) -> str:
    if requirements:
        return requirements[0]["description"][:80]
    return title[:80]


def infer_modules(tags: list[str]) -> str:
    modules = []
    if "api" in tags:
        modules.append("接口层")
    if "db-change" in tags:
        modules.append("数据库层")
    if "payment" in tags:
        modules.append("支付域")
    if "external-call" in tags:
        modules.append("外部系统集成")
    if "async" in tags:
        modules.append("异步事件链路")
    if "security-sensitive" in tags:
        modules.append("安全与审计")
    return "、".join(modules) if modules else "待补充"


def render_feature_brief(
    *,
    project_mode: str,
    project_mode_evidence: list[str],
    project_mode_confidence: float,
    feature_name: str,
    feature_type: str,
    one_liner: str,
    tags: list[str],
    risk_tier: str,
    requirements: list[dict[str, str]],
    source_path: Path,
) -> str:
    tags_block = "\n".join(f"  - {tag}" for tag in tags)
    evidence_block = "\n".join(f'  - "{item}"' for item in project_mode_evidence)
    requirements_block = "\n".join(
        [
            f"  - req_id: {item['req_id']}\n"
            f"    priority: {item['priority']}\n"
            f'    title: "{item["title"]}"\n'
            f"    description: |-\n"
            + "\n".join(f"      {line}" for line in item["description"].splitlines())
            for item in requirements
        ]
    )

    modules_text = infer_modules(tags)

    return f"""# Feature Brief

**版本:** `v1.0`  
**日期:** `{date.today()}`  
**状态:** `Draft`  

---

## 1. 基本信息

```yaml
project_mode: {project_mode}
project_mode_source: agent
project_mode_confidence: {project_mode_confidence:.2f}
project_mode_evidence:
{evidence_block}
project_mode_confirmed_by: zhangsan

feature_name: {feature_name}
feature_type: {feature_type}
one_liner: "{one_liner}"

capability_tags:
{tags_block}

risk_tier: {risk_tier}
```

---

## 2. 需求清单
```yaml
requirements:
{requirements_block}
```

---

## 3. 歧义与待澄清项
- 无

---

## 4. 业务说明

- 背景：本 Feature Brief 由 `{source_path.name}` 自动生成第一版草稿。
- 业务目标：围绕 `{feature_name}` 形成进入设计阶段的结构化输入。
- 非目标：当前版本不保证完全替代人工评审与业务澄清。
- 成功标准：需求清单、风险级别、标签分类可支撑后续 design-pack 与 Gate 执行。

---

## 5. 依赖与影响范围
- 涉及模块：{modules_text}
- 涉及数据库：{"是" if "db-change" in tags else "待补充"}
- 涉及外部系统：{"是" if "external-call" in tags else "否"}
- 是否影响现有接口：{"是" if "api" in tags else "待补充"}

---

## 6. 风险说明

- 为什么当前 `risk_tier` 是这个级别：根据 `capability_tags={", ".join(tags)}` 自动推导。
- 是否需要架构审批：{"是" if risk_tier == "high" else "否"}
- 是否存在上线风险：需结合详细设计和实现阶段进一步确认。

---

## 7. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_file", help="PRD/需求文本文件路径")
    parser.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 feature-brief.md")
    args = parser.parse_args()

    source_path = Path(args.source_file)
    if not source_path.exists():
        print(f"[ERROR] 源文件不存在: {source_path}")
        return 1

    feature_dir = resolve_feature_dir(args.feature_name)
    feature_dir.mkdir(parents=True, exist_ok=True)
    output_path = feature_dir / "feature-brief.md"
    if output_path.exists() and not args.force:
        print(f"[ERROR] feature-brief 已存在，若需覆盖请使用 --force: {output_path}")
        return 1

    source_text = read_source(source_path)
    detected_title = first_heading_or_line(source_text)
    feature_name = feature_dir.name
    project_mode, evidence, confidence = detect_project_mode(source_text)
    
    tags = infer_capability_tags(source_text)
    risk_tier = infer_risk_tier(set(tags))
    feature_type = infer_feature_type(detected_title, source_text, set(tags))
    
    requirements = extract_requirements(source_text)
    one_liner = build_one_liner(detected_title, requirements)

    rendered = render_feature_brief(
        project_mode=project_mode,
        project_mode_evidence=evidence,
        project_mode_confidence=confidence,
        feature_name=feature_name,
        feature_type=feature_type,
        one_liner=one_liner,
        tags=tags,
        risk_tier=risk_tier,
        requirements=requirements,
        source_path=source_path,
    )
    with feature_lock(feature_dir, phase="generate-feature-brief"):
        atomic_write_text(output_path, rendered, encoding="utf-8")

    print("[OK] Feature Brief 自动生成完成")
    print(f"  - source:  {source_path}")
    print(f"  - feature: {feature_name}")
    print(f"  - output:  {output_path}")
    print(f"  - tags:    {', '.join(tags)}")
    print(f"  - risk:    {risk_tier}")
    print(f"  - reqs:    {len(requirements)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
