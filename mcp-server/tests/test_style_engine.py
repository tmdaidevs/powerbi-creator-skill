from src.models.schemas import ReportDefinition, ReportFormat, StyleGuide
from src.parser.definition_parser import ReportDefinitionParser
from src.transformations.style_engine import StyleTransformationEngine


def _report_payload():
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
                        "visuals": [{"id": "v1", "type": "barChart", "config": {"style": {}}}],
                    },
                }
            ],
        }
    }


def _guide():
    return StyleGuide.model_validate(
        {
            "theme": {"primaryColor": "#0078D4", "backgroundColor": "#fff", "textColor": "#111"},
            "typography": {
                "titleFontFamily": "Segoe UI Semibold",
                "bodyFontFamily": "Segoe UI",
                "titleFontSize": 16,
                "bodyFontSize": 11,
            },
            "layout": {"pagePadding": 16, "visualSpacing": 12, "cornerRadius": 8},
            "rules": {"maxVisualsPerPage": 6, "allowCustomVisuals": True, "enforceTopRowKpis": False},
            "visualRules": {"barChart": {"titleAlignment": "left"}},
        }
    )


def test_style_guide_dry_run_returns_original_report_with_plan():
    parser = ReportDefinitionParser()
    report = parser.parse("w1", "r1", _report_payload())
    transformed, plan = StyleTransformationEngine().apply_style_guide(report, _guide(), dry_run=True)

    assert transformed.report_id == report.report_id
    assert len(plan.changes) > 0
    assert plan.dry_run is True
