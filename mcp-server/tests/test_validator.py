from src.models.schemas import PageDefinition, ReportDefinition, ReportFormat, VisualDefinition
from src.validation.validator import ReportValidator


def test_validator_blocks_unknown_format():
    report = ReportDefinition(report_id="r", workspace_id="w", format=ReportFormat.UNKNOWN)
    result = ReportValidator().validate(report)
    assert result.valid is False
    assert any(i.code == "unsupported_report_format" for i in result.issues)


def test_validator_detects_orphaned_visual_reference():
    report = ReportDefinition(
        report_id="r",
        workspace_id="w",
        format=ReportFormat.PBIR,
        pages=[
            PageDefinition(
                id="p1",
                name="p1",
                visuals=[VisualDefinition(id="v1", visual_type="barChart", page_id="missing", properties={})],
            )
        ],
    )
    result = ReportValidator().validate(report)
    assert result.valid is False
    assert any(i.code == "orphaned_visual_reference" for i in result.issues)
