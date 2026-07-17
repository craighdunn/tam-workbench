from pathlib import Path

from tam_workbench.templates import ensure_default_templates


def test_default_templates_are_created(tmp_path):
    paths = ensure_default_templates(tmp_path)

    expected = {
        "customer_email.md",
        "internal_escalation.md",
        "troubleshooting_summary.md",
        "meeting_agenda.md",
        "meeting_recap.md",
        "research_summary.md",
        "support_handoff.md",
        "executive_summary.md",
        "course_usage_report.md",
        "asset_metadata_report.md",
        "user_activity_report.md",
        "showpad_update_export.md",
    }
    assert expected == {p.name for p in paths}
    assert (tmp_path / "internal_escalation.md").read_text().startswith("# Internal Escalation")


def test_mcp_server_can_be_constructed():
    from tam_workbench.server import build_server

    server = build_server(Path("/tmp/tam-workbench-test"))
    assert server.name == "tam-workbench"
