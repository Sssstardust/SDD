from pathlib import Path
import sys
import shutil


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline  # type: ignore  # noqa: E402


def test_should_pass_force_to_generation_skill_when_init_design_precreates_output(monkeypatch) -> None:
    tmp_path = ROOT / ".tmp_test_workspace" / "generate_design_force_case"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)

    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()
    output_path = feature_dir / "design-v1.md"

    fake_root = tmp_path / "repo"
    skill_script = fake_root / "skills" / "sdd-generation" / "run.py"
    skill_script.parent.mkdir(parents=True)
    skill_script.write_text("# fake skill\n", encoding="utf-8")

    captured_commands: list[list[str]] = []

    def fake_init_design(_feature_dir: str) -> int:
        output_path.write_text("# template\n", encoding="utf-8")
        return 0

    def fake_detect_latest_design_path(_feature_dir_path: Path) -> Path:
        return output_path

    class FakeResult:
        returncode = 0

    def fake_run(command: list[str], check: bool = False) -> FakeResult:
        captured_commands.append(command)
        return FakeResult()

    monkeypatch.setattr(run_pipeline, "ROOT", fake_root)
    monkeypatch.setattr(run_pipeline, "init_design", fake_init_design)
    monkeypatch.setattr(run_pipeline, "detect_latest_design_path", fake_detect_latest_design_path)
    monkeypatch.setattr(run_pipeline.subprocess, "run", fake_run)

    result = run_pipeline.generate_design(str(feature_dir))

    assert result == 0
    assert captured_commands
    assert "--force" in captured_commands[0]
