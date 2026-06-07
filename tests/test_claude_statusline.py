import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "generate_usage_dashboard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_usage_dashboard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_statusline_backfills_missing_claude_output_tokens():
    module = load_module()
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        status_file = tmp / "statusline-msgcount.json"
        status_file.write_text(json.dumps({
            "sessions": {
                "claude-123": {"msg_num": 7, "out_tokens": 13}
            }
        }))

        sessions = {
            "claude-123": module.empty_session("Claude", "claude-123"),
        }

        merged = module.merge_claude_statusline(sessions, status_file)
        rec = merged["claude-123"]

        assert rec["output_tokens"] == 13
        assert rec["activity_proxy"] == 13
        assert rec["message_count"] == 7


if __name__ == "__main__":
    test_statusline_backfills_missing_claude_output_tokens()
    print("ok")
