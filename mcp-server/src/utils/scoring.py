from __future__ import annotations

from src.models.schemas import ModernizationScore, ReportDefinition, ReportFormat


def score_modernization(report: ReportDefinition) -> ModernizationScore:
    score = 100
    reasons: list[str] = []

    if report.format != ReportFormat.PBIR:
        score -= 60
        reasons.append("Report is not PBIR format.")

    visuals = sum(len(p.visuals) for p in report.pages)
    custom_visuals = sum(1 for p in report.pages for v in p.visuals if v.visual_type.startswith("custom"))
    unsupported = len(report.unsupported_artifacts)

    if len(report.pages) > 8:
        score -= 10
        reasons.append("High page count increases modernization complexity.")
    if visuals > 40:
        score -= 10
        reasons.append("High visual count may require phased modernization.")
    if custom_visuals > 0:
        score -= min(20, custom_visuals * 2)
        reasons.append("Custom visuals may not support deterministic formatting edits.")
    if unsupported > 0:
        score -= min(40, unsupported * 10)
        reasons.append("Unsupported artifacts detected.")

    score = max(0, min(100, score))
    if score == 0:
        classification = "blocked"
    elif score < 50:
        classification = "hard"
    elif score < 75:
        classification = "medium"
    else:
        classification = "easy"

    next_action = {
        "blocked": "Convert report to PBIR and remove unsupported artifacts.",
        "hard": "Run inspection-only and apply limited style patches per page.",
        "medium": "Use dry-run modernization and review diffs before updates.",
        "easy": "Proceed with dry-run style guide, then confirmed writeback.",
    }[classification]

    return ModernizationScore(score=score, classification=classification, reasons=reasons or ["No major blockers identified."], suggested_next_action=next_action)
