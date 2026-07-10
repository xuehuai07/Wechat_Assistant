from pathlib import Path


def test_launchd_template_uses_rendered_paths_without_environment_secrets():
    root = Path(__file__).resolve().parents[2]
    template = (root / "launchd" / "com.uniubi.wechat-assistant.plist.template").read_text(encoding="utf-8")
    script = (root / "scripts" / "launchd-agent.sh").read_text(encoding="utf-8")

    assert "__PROJECT_ROOT__" in template
    assert "scripts/run-backend.sh" in template
    assert "runtime/logs/launchd.stdout.log" in template
    assert "DEEPSEEK_API_KEY" not in template
    assert "WEB_PASSWORD" not in template
    assert "launchctl bootstrap" in script
    assert "launchctl bootout" in script


def test_launchd_template_is_valid_xml_plist_shape():
    root = Path(__file__).resolve().parents[2]
    template = (root / "launchd" / "com.uniubi.wechat-assistant.plist.template").read_text(encoding="utf-8")

    assert template.startswith("<?xml")
    assert "<plist version=\"1.0\">" in template
    assert template.rstrip().endswith("</plist>")
