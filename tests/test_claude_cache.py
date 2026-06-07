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


def test_cached_claude_tokens_survive_when_live_source_is_missing():
    module = load_module()
    with TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "state"
        os.environ["AI_USAGE_DASHBOARD_STATE_DIR"] = str(cache_dir)

        cached = {
            "tool": "Claude",
            "session_id": "claude-abc",
            "project_path": "~/proj",
            "project_label": "proj",
            "start_time": "2026-05-20T10:00:00Z",
            "end_time": "2026-05-20T11:00:00Z",
            "day": "2026-05-20",
            "model": "claude-sonnet-4",
            "input_tokens": 120,
            "output_tokens": 80,
            "cache_creation_tokens": 20,
            "cache_read_tokens": 10,
            "total_tokens": 230,
            "exact_tokens": True,
            "activity_proxy": 230,
            "cost_proxy": 0.0,
            "files_modified": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "read_ops": 0,
            "write_ops": 0,
            "duration_minutes": 0,
            "message_count": 0,
            "confidence": "high",
            "data_notes": "cached",
        }

        module.save_session_cache([cached])
        merged = module.merge_cached_sessions([])

        assert len(merged) == 1
        rec = merged[0]
        assert rec["session_id"] == "claude-abc"
        assert rec["total_tokens"] == 230
        assert rec["input_tokens"] == 120
        assert rec["output_tokens"] == 80
        assert rec["cache_creation_tokens"] == 20
        assert rec["cache_read_tokens"] == 10
        assert rec["exact_tokens"] is True


if __name__ == "__main__":
    test_cached_claude_tokens_survive_when_live_source_is_missing()
    print("ok")
