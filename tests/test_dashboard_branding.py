import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "generate_usage_dashboard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_usage_dashboard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_dashboard_creates_installable_webapp():
    module = load_module()
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        module.ROOT = root
        summary = {
            "generated_at": "2026-05-22T22:20:53.529732Z",
            "tools": [],
            "projects": [],
            "days": [],
            "models": [],
        }
        module.render_dashboard(summary, [])

        html = (root / "usage-dashboard.html").read_text()
        icon = root / "agentusage-icon.svg"
        manifest = root / "agentusage.webmanifest"

        assert "<title>AgentUsage Dashboard</title>" in html
        assert 'rel="icon"' in html
        assert 'rel="manifest"' in html
        assert 'apple-mobile-web-app-title' in html
        assert 'application-name' in html
        assert icon.exists()
        assert manifest.exists()
        assert '"name": "AgentUsage"' in manifest.read_text()


if __name__ == "__main__":
    test_render_dashboard_creates_installable_webapp()
    print("ok")
