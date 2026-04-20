from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.models.schemas import (
    ReportDefinition,
    Severity,
    StyleGuide,
    TransformationChange,
    TransformationPlan,
    VisualDefinition,
    WarningItem,
)


class StyleTransformationEngine:
    EDITABLE_STYLE_FIELDS = {
        "backgroundColor",
        "textColor",
        "cornerRadius",
        "titleAlignment",
        "showBorder",
        "alternatingRows",
        "legendPosition",
        "dataLabelColor",
    }

    # Visual types that use category-based coloring
    CATEGORY_VISUAL_TYPES = {
        "donutChart", "pieChart", "treemap", "funnel",
        "waterfallChart", "sunburst",
        "barChart", "columnChart", "clusteredBarChart", "clusteredColumnChart",
        "stackedBarChart", "stackedColumnChart", "lineChart", "areaChart",
    }

    @staticmethod
    def extract_category_field(visual: VisualDefinition) -> dict[str, str] | None:
        """Extract the category field (entity + property) from a visual's query.

        Returns ``{"entity": ..., "property": ..., "queryRef": ...}`` if the
        visual has a Category projection, otherwise ``None``.
        """
        query_state = visual.raw.get("visual", {}).get("query", {}).get("queryState", {})
        category = query_state.get("Category", {})
        projections = category.get("projections", [])
        if not projections:
            return None

        field = projections[0].get("field", {})
        col = field.get("Column", {})
        entity = col.get("Expression", {}).get("SourceRef", {}).get("Entity")
        prop = col.get("Property")
        query_ref = projections[0].get("queryRef", "")
        if entity and prop:
            return {"entity": entity, "property": prop, "queryRef": query_ref}
        return None

    @staticmethod
    def build_category_data_points(
        entity: str,
        prop: str,
        category_values: list[str],
        palette: list[str],
    ) -> list[dict[str, Any]]:
        """Build per-category ``dataPoint`` entries with PBIR selectors."""
        data_points: list[dict[str, Any]] = []
        for idx, val in enumerate(category_values):
            color = palette[idx % len(palette)] if palette else "#888888"
            data_points.append({
                "properties": {
                    "fill": {
                        "solid": {
                            "color": {
                                "expr": {"Literal": {"Value": f"'{color}'"}}
                            }
                        }
                    }
                },
                "selector": {
                    "data": [
                        {
                            "scopeId": {
                                "Comparison": {
                                    "ComparisonKind": 0,
                                    "Left": {
                                        "Column": {
                                            "Expression": {"SourceRef": {"Entity": entity}},
                                            "Property": prop,
                                        }
                                    },
                                    "Right": {"Literal": {"Value": f"'{val}'"}},
                                }
                            }
                        }
                    ],
                },
            })
        return data_points

    def _apply_if_changed(self, plan: TransformationPlan, target: str, path: str, container: dict, key: str, new_value, risk_note: str | None = None) -> None:
        old_value = container.get(key)
        if old_value == new_value:
            return
        container[key] = new_value
        plan.changes.append(
            TransformationChange(target=target, path=path, old_value=old_value, new_value=new_value, risk_note=risk_note)
        )

    def apply_style_guide(self, report: ReportDefinition, style_guide: StyleGuide, dry_run: bool = True) -> tuple[ReportDefinition, TransformationPlan]:
        mutable = deepcopy(report)
        plan = TransformationPlan(report_id=report.report_id, workspace_id=report.workspace_id, dry_run=dry_run)

        for page in mutable.pages:
            if len(page.visuals) > style_guide.rules.max_visuals_per_page:
                plan.warnings.append(
                    WarningItem(
                        severity=Severity.WARNING,
                        code="max_visuals_exceeded",
                        message=f"Page {page.name} has {len(page.visuals)} visuals; max is {style_guide.rules.max_visuals_per_page}",
                        remediation="Split page visuals or increase style guide threshold.",
                    )
                )

            page.properties.setdefault("canvas", {})
            self._apply_if_changed(
                plan,
                target=f"page:{page.id}",
                path="canvas.padding",
                container=page.properties["canvas"],
                key="padding",
                new_value=style_guide.layout.page_padding,
            )

            for visual in page.visuals:
                visual.properties.setdefault("style", {})
                style = visual.properties["style"]

                self._apply_if_changed(
                    plan,
                    target=f"visual:{visual.id}",
                    path="style.backgroundColor",
                    container=style,
                    key="backgroundColor",
                    new_value=style_guide.theme.background_color,
                )
                self._apply_if_changed(
                    plan,
                    target=f"visual:{visual.id}",
                    path="style.textColor",
                    container=style,
                    key="textColor",
                    new_value=style_guide.theme.text_color,
                )
                self._apply_if_changed(
                    plan,
                    target=f"visual:{visual.id}",
                    path="style.cornerRadius",
                    container=style,
                    key="cornerRadius",
                    new_value=style_guide.layout.corner_radius,
                )

                type_rules = style_guide.visual_rules.get(visual.visual_type, {})
                for rule_key, rule_value in type_rules.items():
                    if rule_key not in self.EDITABLE_STYLE_FIELDS:
                        plan.warnings.append(
                            WarningItem(
                                severity=Severity.INFO,
                                code="non_editable_rule_skipped",
                                message=f"Skipped unsupported style rule '{rule_key}' for visual {visual.id}",
                                remediation="Add deterministic mapping before applying this rule.",
                            )
                        )
                        continue
                    self._apply_if_changed(
                        plan,
                        target=f"visual:{visual.id}",
                        path=f"style.{rule_key}",
                        container=style,
                        key=rule_key,
                        new_value=rule_value,
                    )

                if visual.visual_type.startswith("custom") and not style_guide.rules.allow_custom_visuals:
                    plan.warnings.append(
                        WarningItem(
                            severity=Severity.BLOCKER,
                            code="custom_visual_disallowed",
                            message=f"Custom visual {visual.id} violates style guide policy.",
                            remediation="Replace custom visual or set allowCustomVisuals=true.",
                        )
                    )

        if dry_run:
            return report, plan
        return mutable, plan
