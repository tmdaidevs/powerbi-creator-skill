from __future__ import annotations

from src.models.schemas import ReportDefinition, ReportFormat, Severity, ValidationResult, WarningItem


class ReportValidator:
    def validate(self, report: ReportDefinition) -> ValidationResult:
        issues: list[WarningItem] = []

        if report.format != ReportFormat.PBIR:
            issues.append(
                WarningItem(
                    severity=Severity.BLOCKER,
                    code="unsupported_report_format",
                    message=f"Report format {report.format.value} is not safely editable for deterministic modernization.",
                    remediation="Convert to PBIR-compatible format before applying write operations.",
                )
            )

        if not report.parts:
            issues.append(
                WarningItem(
                    severity=Severity.BLOCKER,
                    code="missing_definition_parts",
                    message="No definition parts were returned by API.",
                    remediation="Re-export report definition and verify API permissions.",
                )
            )

        if not report.pages:
            issues.append(
                WarningItem(
                    severity=Severity.BLOCKER,
                    code="missing_pages",
                    message="No editable page definitions were found.",
                    remediation="Ensure report is PBIR and includes page artifacts.",
                )
            )

        page_ids = {p.id for p in report.pages}
        seen_visual_ids: set[str] = set()

        for page in report.pages:
            if page.id in (None, ""):
                issues.append(
                    WarningItem(
                        severity=Severity.BLOCKER,
                        code="missing_page_reference",
                        message="Page has missing ID",
                        remediation="Repair page metadata in source definition.",
                    )
                )

            for visual in page.visuals:
                if visual.page_id not in page_ids:
                    issues.append(
                        WarningItem(
                            severity=Severity.BLOCKER,
                            code="orphaned_visual_reference",
                            message=f"Visual {visual.id} references non-existent page {visual.page_id}",
                            remediation="Update visual->page mapping in definition.",
                        )
                    )
                if visual.id in seen_visual_ids:
                    issues.append(
                        WarningItem(
                            severity=Severity.WARNING,
                            code="duplicate_visual_id",
                            message=f"Duplicate visual id {visual.id}",
                            remediation="Ensure visual IDs are unique for reliable patching.",
                        )
                    )
                seen_visual_ids.add(visual.id)

                if isinstance(visual.properties, dict) and "parseError" in visual.properties:
                    issues.append(
                        WarningItem(
                            severity=Severity.BLOCKER,
                            code="malformed_visual_config",
                            message=f"Visual {visual.id} contains non-JSON config payload",
                            remediation="Normalize visual config JSON before applying patches.",
                        )
                    )

        # Validate visual positions don't overlap within each page
        for page in report.pages:
            positioned = [(v, v.x, v.y, v.width, v.height) for v in page.visuals
                         if v.x is not None and v.y is not None and v.width is not None and v.height is not None]
            for i, (va, ax, ay, aw, ah) in enumerate(positioned):
                for vb, bx, by, bw, bh in positioned[i+1:]:
                    if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by:
                        issues.append(
                            WarningItem(
                                severity=Severity.BLOCKER,
                                code="visual_overlap",
                                message=f"Visuals '{va.name or va.id}' and '{vb.name or vb.id}' overlap on page '{page.name}'",
                                remediation="Use rearrange_page_visuals to fix spacing. All visuals must have consistent gaps with no overlaps.",
                            )
                        )

        # Validate consistent spacing between adjacent visuals
        MIN_GAP = 16  # minimum gap in pixels between visuals
        for page in report.pages:
            positioned = [(v, v.x, v.y, v.width, v.height) for v in page.visuals
                         if v.x is not None and v.y is not None and v.width is not None and v.height is not None]
            for i, (va, ax, ay, aw, ah) in enumerate(positioned):
                for vb, bx, by, bw, bh in positioned[i+1:]:
                    # Check horizontal adjacency (same row, within 40px y)
                    if abs(ay - by) < 40:
                        h_gap = bx - (ax + aw) if bx > ax else ax - (bx + bw)
                        if 0 < h_gap < MIN_GAP:
                            issues.append(
                                WarningItem(
                                    severity=Severity.WARNING,
                                    code="insufficient_visual_spacing",
                                    message=f"Visuals '{va.name or va.id}' and '{vb.name or vb.id}' have only {h_gap:.0f}px horizontal gap (min {MIN_GAP}px) on page '{page.name}'",
                                    remediation="Use rearrange_page_visuals with gap=20 to enforce consistent spacing.",
                                )
                            )

        for artifact in report.unsupported_artifacts:
            sev = Severity.BLOCKER if artifact == "missing_pages" else Severity.WARNING
            issues.append(
                WarningItem(
                    severity=sev,
                    code="unsupported_artifact",
                    message=f"Unsupported artifact detected: {artifact}",
                    remediation="Treat this artifact as read-only or remove before modernization.",
                )
            )

        valid = not any(i.severity == Severity.BLOCKER for i in issues)
        return ValidationResult(valid=valid, issues=issues)
