"""Coverage must keep branch configuration in source subprocesses outside cwd."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_source_subprocess_keeps_branch_coverage_outside_repository(
    tmp_path: Path,
) -> None:
    """Real pytest catches cwd-dependent configuration and combine errors."""
    probe = tmp_path / "test_probe.py"
    probe.write_text(
        """import json, subprocess, sys

def test_child(tmp_path):
    code = '''import coverage, json, kvscope
print(json.dumps({"branch": coverage.Coverage.current().config.branch}))'''
    child = subprocess.run([sys.executable, '-c', code], cwd=tmp_path,
                           capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout)['branch'] is True
""",
        encoding="utf-8",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COV_", "COVERAGE_"))
        and key not in {"PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST"}
    }
    # Nested coverage never feeds independent data into outer pytest.
    environment["COVERAGE_FILE"] = str(tmp_path / ".coverage")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(ROOT / "pyproject.toml"),
            str(probe),
            "--cov=kvscope",
            "--cov-report=",
            "--basetemp",
            str(tmp_path / "child-temp"),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
