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
                            "visuals": [
                                {
                                    "id": "v1",
                                    "type": "barChart",
                                    "config": {
                                        "style": {
                                            "backgroundColor": "#FFFFFF",
                                            "textColor": "#111111",
                                            "cornerRadius": 4,
                                            "titleFontFamily": "Segoe UI Semibold",
                                            "bodyFontFamily": "Segoe UI",
                                            "titleFontSize": 15,
                                            "bodyFontSize": 10,
                                            "titleAlignment": "left",
                                        }
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
            "metadata": {"theme": {"primaryColor": "#FF0000"}},
        }



def test_extract_style_guide_from_report_returns_style_payload():
    service = ReportModernizationService(api_client=FakeApiClient())
    response = service.extract_style_guide_from_report("w1", "r1")

    assert response.success is True
    assert response.data["styleGuide"]["theme"]["primaryColor"] == "#FF0000"
    assert response.data["styleGuide"]["typography"]["titleFontFamily"] == "Segoe UI Semibold"
    assert response.data["styleGuide"]["visualRules"]["barChart"]["titleAlignment"] == "left"
