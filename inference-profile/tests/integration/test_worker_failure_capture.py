from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALLABLE_MODULE = "tests.integration.test_worker_failure_capture"


def _integration_runtime_error_worker(_point_spec, raw_writer) -> dict[str, object]:
    print("integration stdout", flush=True)
    print("integration stderr", file=sys.stderr, flush=True)
    raw_writer.write_row({"phase": "prefill", "duration_us": "55.0"})
    raise RuntimeError("integration runtime failure")


def test_worker_failure_capture_smoke_uses_file_backed_logs(tmp_path: Path) -> None:
    run_root = tmp_path / "integration-run"
    script_path = tmp_path / "invoke_worker_runner.py"
    script_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import json",
                "from pathlib import Path",
                "import sys",
                f"PROJECT_ROOT = Path({str(PROJECT_ROOT)!r})",
                "sys.path.insert(0, str(PROJECT_ROOT))",
                "from inference_profile.worker_profile_point import run_profile_point",
                "",
                "def main() -> int:",
                "    result = run_profile_point(",
                "        {",
                "            'point_id': 'integration-runtime-failure',",
                f"            'callable_path': '{CALLABLE_MODULE}._integration_runtime_error_worker',",
                "            'raw_fieldnames': ['phase', 'duration_us'],",
                "        },",
                f"        run_root=Path({str(run_root)!r}),",
                "        timeout_seconds=5,",
                "    )",
                "    print(json.dumps(result, sort_keys=True))",
                "    return 0",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-B", str(script_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Traceback" not in result.stdout

    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["public_status"] == "profile_failed"
    assert payload["failure_kind"] == "exception"
    assert payload["failure_cause"] == "integration runtime failure"
    assert payload["timed_out"] is False
    assert payload["exit_code"] == 1
    assert payload["raw_output_exists"] is True
    assert payload["raw_row_count"] == 1
    assert (
        Path(payload["stdout_log_path"])
        .read_text(encoding="utf-8")
        .startswith("integration stdout\n")
    )
    stderr_text = Path(payload["stderr_log_path"]).read_text(encoding="utf-8")
    assert "integration stderr" in stderr_text
    assert "integration runtime failure" in stderr_text
