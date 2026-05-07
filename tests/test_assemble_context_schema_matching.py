from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "sdd-generation"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from assemble_context import assemble, filter_schema_context  # type: ignore  # noqa: E402


def test_should_not_match_schema_tables_only_by_generic_tob_token() -> None:
    tables = [
        {
            "table_name": "t_tob_pricing_item",
            "columns": ["pricing_id", "pricing_name", "status"],
            "sources": ["examples/fixtures/attached-sample-project/src/main/resources/db/migration/V1__pricing_list_control.sql"],
        }
    ]

    matched = filter_schema_context(tables, ["tob", "demo", "office", "employees"])

    assert matched == []


def test_should_match_schema_tables_by_specific_business_token() -> None:
    tables = [
        {
            "table_name": "t_task_board",
            "columns": ["task_id", "task_title", "status"],
            "sources": ["src/main/resources/db/task_board.sql"],
        }
    ]

    matched = filter_schema_context(tables, ["task", "board", "demo"])

    assert matched == tables


def test_should_not_match_pricing_tables_for_oa_workspace_when_only_generic_tob_overlaps() -> None:
    context = assemble(ROOT / "specs" / "tob-oa-office-demo")

    matched_table_names = [item["table_name"] for item in context["schema_context"]["matched_tables"]]

    assert matched_table_names == []
