from src.diffing.diff_engine import DiffEngine
from src.models.schemas import PageDefinition, ReportDefinition, ReportFormat, VisualDefinition


def test_diff_reports_detects_visual_property_change():
    before = ReportDefinition(
        report_id="r",
        workspace_id="w",
        format=ReportFormat.PBIR,
        pages=[PageDefinition(id="p1", name="p1", visuals=[VisualDefinition(id="v1", visual_type="barChart", page_id="p1", properties={"x": 1})])],
    )
    after = ReportDefinition(
        report_id="r",
        workspace_id="w",
        format=ReportFormat.PBIR,
        pages=[PageDefinition(id="p1", name="p1", visuals=[VisualDefinition(id="v1", visual_type="barChart", page_id="p1", properties={"x": 2})])],
    )

    result = DiffEngine().diff_reports(before, after)
    assert result.field_changes
    assert "pages" in result.changed_parts
