import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "generate_usage_dashboard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_usage_dashboard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_archive_restores_missing_tools_and_sessions():
    module = load_module()
    with TemporaryDirectory() as tmp:
        state_dir = Path(tmp) / "state"
        os.environ["AI_USAGE_DASHBOARD_STATE_DIR"] = str(state_dir)

        archive = {
            "version": 1,
            "sessions": [
                {
                    "tool": "Claude",
                    "session_id": "claude-old",
                    "project_path": "~/old/claude",
                    "project_label": "old/claude",
                    "start_time": "2026-04-01T10:00:00Z",
                    "end_time": "2026-04-01T11:00:00Z",
                    "day": "2026-04-01",
                    "model": "claude-opus-4",
                    "input_tokens": 100,
                    "output_tokens": 200,
                    "cache_creation_tokens": 10,
                    "cache_read_tokens": 20,
                    "total_tokens": 330,
                    "exact_tokens": True,
                    "activity_proxy": 330,
                    "cost_proxy": 0.0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "read_ops": 0,
                    "write_ops": 0,
                    "duration_minutes": 0,
                    "message_count": 0,
                    "confidence": "high",
                    "data_notes": "archived claude",
                },
                {
                    "tool": "Codex",
                    "session_id": "codex-old",
                    "project_path": "~/old/codex",
                    "project_label": "old/codex",
                    "start_time": "2026-04-02T10:00:00Z",
                    "end_time": "2026-04-02T11:00:00Z",
                    "day": "2026-04-02",
                    "model": "gpt-4.1-codex",
                    "input_tokens": 300,
                    "output_tokens": 400,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                    "total_tokens": 700,
                    "exact_tokens": True,
                    "activity_proxy": 700,
                    "cost_proxy": 0.0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "read_ops": 0,
                    "write_ops": 0,
                    "duration_minutes": 0,
                    "message_count": 0,
                    "confidence": "high",
                    "data_notes": "archived codex",
                },
            ],
        }
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "session-archive.json").write_text(__import__("json").dumps(archive))

        live = [module.empty_session("Claude", "claude-live")]
        live[0]["total_tokens"] = 1
        live[0]["input_tokens"] = 1
        live[0]["exact_tokens"] = True

        merged = module.merge_session_archive(live)
        by_id = {s["session_id"]: s for s in merged}

        assert set(by_id) == {"claude-old", "codex-old", "claude-live"}
        assert by_id["claude-old"]["tool"] == "Claude"
        assert by_id["codex-old"]["tool"] == "Codex"
        assert by_id["claude-old"]["total_tokens"] == 330
        assert by_id["codex-old"]["total_tokens"] == 700
        assert by_id["claude-live"]["total_tokens"] == 1


if __name__ == "__main__":
    test_session_archive_restores_missing_tools_and_sessions()
    print("ok")
