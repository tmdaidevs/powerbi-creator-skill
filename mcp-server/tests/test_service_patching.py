from pathlib import Path

from src.server.service import ReportModernizationService


class FakeApiClient:
    def get_report_definition(self, workspace_id: str, report_id: str):
        return {
            "definition": {
                "format": "PBIR",
                "parts": [
                    {
                        "name": "Page1",
                        "path": "pages/Page1/page.json",
                        "contentType": "application/json",
                        "payload": {
                            "id": "Page1",
                            "name": "Page1",
                            "visuals": [{"id": "v1", "type": "barChart", "config": {"style": {"textColor": "#111"}}}],
                        },
                    },
                    {
                        "name": "reportTheme",
                        "path": "StaticResources/themes/default.json",
                        "contentType": "application/json",
                        "payload": {"name": "old"},
                    },
                ],
            },
            "metadata": {"theme": {"primaryColor": "#0000FF"}},
        }



def test_patch_visual_properties_dry_run_contains_diff():
    service = ReportModernizationService(api_client=FakeApiClient())
    result = service.patch_visual_properties("w", "r", "Page1", "v1", {"style": {"textColor": "#222"}}, dry_run=True)
    assert result.success is True
    assert result.data["diff"]["field_changes"]



def test_replace_theme_resource_non_dry_run_returns_definition_parts():
    service = ReportModernizationService(api_client=FakeApiClient())
    result = service.replace_theme_resource("w", "r", {"name": "new"}, dry_run=False)
    assert result.success is True
    assert "definitionParts" in result.data



def test_backup_report_definition_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PBIR_MCP_BACKUP_DIRECTORY", str(tmp_path))
    from src.config.settings import Settings
    from src import config as _  # noqa: F401

    service = ReportModernizationService(api_client=FakeApiClient())
    # force setting for this service instance
    import src.server.service as service_mod

    service_mod.settings.backup_directory = str(tmp_path)
    result = service.backup_report_definition("w", "r")
    assert result.success is True
    assert Path(result.data["backupPath"]).exists()
