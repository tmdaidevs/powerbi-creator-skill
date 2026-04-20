from __future__ import annotations

import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.settings import settings
from src.diffing.diff_engine import DiffEngine
from src.fabric_client.client import FabricApiClient, FabricApiError
from src.models.schemas import (
    MCPErrorCode,
    ReportDefinition,
    ReportPart,
    Severity,
    StyleGuide,
    ToolResponse,
    VisualDefinition,
    WarningItem,
)
from src.parser.definition_parser import ReportDefinitionParser
from src.transformations.style_engine import StyleTransformationEngine
from src.utils.scoring import score_modernization
from src.validation.validator import ReportValidator


class ReportModernizationService:
    def __init__(
        self,
        api_client: FabricApiClient | None = None,
        parser: ReportDefinitionParser | None = None,
        transformer: StyleTransformationEngine | None = None,
        validator: ReportValidator | None = None,
        diff_engine: DiffEngine | None = None,
    ) -> None:
        self.api_client = api_client or FabricApiClient()
        self.parser = parser or ReportDefinitionParser()
        self.transformer = transformer or StyleTransformationEngine()
        self.validator = validator or ReportValidator()
        self.diff_engine = diff_engine or DiffEngine()
        self._cache: dict[str, tuple[float, ReportDefinition]] = {}

    def _load_report(self, workspace_id: str, report_id: str) -> ReportDefinition:
        cache_key = f"{workspace_id}:{report_id}"
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_report = self._cache[cache_key]
            if now - cached_time < settings.cache_ttl_seconds:
                return cached_report

        raw = self.api_client.get_report_definition(workspace_id, report_id)
        if raw.get("status") == "pending":
            location = raw.get("location")
            if not location:
                raise RuntimeError(f"{MCPErrorCode.ASYNC_OPERATION_PENDING.value}: operation location missing")
            operation = self.api_client.wait_for_operation(location)
            if operation.status.lower() != "succeeded":
                raise RuntimeError(f"{MCPErrorCode.ASYNC_OPERATION_PENDING.value}: operation status {operation.status}")
            raw = operation.payload or {}
        report = self.parser.parse(workspace_id, report_id, raw)
        self._cache[cache_key] = (now, report)
        return report

    def _invalidate_cache(self, workspace_id: str, report_id: str) -> None:
        cache_key = f"{workspace_id}:{report_id}"
        self._cache.pop(cache_key, None)

    def _audit_log(self, operation: str, workspace_id: str, report_id: str, details: dict[str, Any], backup_id: str | None = None) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "operation": operation,
            "workspace_id": workspace_id,
            "report_id": report_id,
            "details": details,
            "backup_id": backup_id,
        }
        log_path = Path(settings.audit_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _validate_report_or_block(self, report: ReportDefinition) -> tuple[list[WarningItem], list[WarningItem]]:
        validation = self.validator.validate(report)
        warnings = [issue for issue in validation.issues if issue.severity != Severity.BLOCKER]
        blockers = [issue for issue in validation.issues if issue.severity == Severity.BLOCKER]
        return warnings, blockers

    def _resolve_page(self, report: ReportDefinition, page_id_or_name: str):
        return next((p for p in report.pages if p.id == page_id_or_name or p.name == page_id_or_name), None)

    def _resolve_visual(self, page, visual_id_or_name: str):
        return next((v for v in page.visuals if v.id == visual_id_or_name or v.name == visual_id_or_name), None)

    def _report_to_definition_parts(self, report: ReportDefinition) -> dict[str, Any]:
        """Reconstruct API-compatible definition parts from the internal report model."""
        out_parts: list[dict[str, Any]] = []

        for part in report.parts:
            payload = deepcopy(part.payload)
            out_entry: dict[str, Any] = {
                "path": part.path,
                "payload": payload,
            }
            # Re-encode as base64 if the original was InlineBase64
            if part.payload_type == "InlineBase64" and isinstance(payload, (dict, list)):
                out_entry["payload"] = base64.b64encode(
                    json.dumps(payload).encode("utf-8")
                ).decode("utf-8")
                out_entry["payloadType"] = "InlineBase64"

            out_parts.append(out_entry)

        return {
            "definition": {
                "parts": out_parts,
            }
        }

    def analyze_report_structure(self, workspace_id: str, report_id: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        warnings, blockers = self._validate_report_or_block(report)
        score = score_modernization(report)
        return ToolResponse(
            success=True,
            summary="Report structure analyzed",
            data={
                "report": {
                    "reportId": report.report_id,
                    "workspaceId": report.workspace_id,
                    "format": report.format.value,
                    "pageCount": len(report.pages),
                    "visualCount": sum(len(p.visuals) for p in report.pages),
                    "bookmarkCount": len(report.bookmarks),
                    "staticResourceCount": len(report.static_resources),
                },
                "modernizationScore": score.model_dump(),
            },
            warnings=warnings,
            blockers=blockers,
            next_actions=["Run get_report_pages for detailed page inventory", "Run apply_style_guide with dry_run=true"],
        )

    def _resolve_dataset_id(self, workspace_id: str, report_id: str) -> str | None:
        """Resolve the dataset/semantic-model ID linked to a report."""
        try:
            metadata = self.api_client.get_report_metadata(workspace_id, report_id)
            return metadata.get("datasetId")
        except FabricApiError:
            return None

    def _query_category_values(self, workspace_id: str, dataset_id: str, entity: str, prop: str, limit: int = 50) -> list[str]:
        """Query distinct values of a category column via DAX."""
        dax = f'EVALUATE TOPN({limit}, DISTINCT(SELECTCOLUMNS(\'{entity}\', "v", \'{entity}\'[{prop}])))'
        try:
            rows = self.api_client.execute_dax_query(workspace_id, dataset_id, dax)
            return [r.get("[v]", r.get("v", "")) for r in rows if r]
        except (FabricApiError, Exception):
            return []

    def _apply_category_colors(
        self,
        report: ReportDefinition,
        workspace_id: str,
        dataset_id: str | None,
        data_colors: list[str],
        plan_changes: list,
    ) -> None:
        """Detect visuals with category fields and apply per-category data colors.

        Mutates ``report.parts`` in-place, updating visual payloads with
        per-category ``dataPoint`` selectors using the provided palette.
        """
        if not data_colors or not dataset_id:
            return

        for page in report.pages:
            for visual in page.visuals:
                cat = self.transformer.extract_category_field(visual)
                if not cat:
                    continue

                # Only auto-color category-dominant visual types
                if visual.visual_type not in self.transformer.CATEGORY_VISUAL_TYPES:
                    continue

                values = self._query_category_values(workspace_id, dataset_id, cat["entity"], cat["property"])
                if not values:
                    continue

                data_points = self.transformer.build_category_data_points(
                    cat["entity"], cat["property"], values, data_colors,
                )

                # Apply to the raw part payload
                for part in report.parts:
                    if not part.path.endswith("/visual.json"):
                        continue
                    if not isinstance(part.payload, dict):
                        continue
                    if part.payload.get("name") != (visual.name or visual.id):
                        continue

                    part.payload.setdefault("visual", {}).setdefault("objects", {})["dataPoint"] = data_points
                    plan_changes.append({
                        "target": f"visual:{visual.name or visual.id}",
                        "path": "objects.dataPoint",
                        "categoryField": f"{cat['entity']}.{cat['property']}",
                        "categoryCount": len(values),
                        "colorsApplied": [data_colors[i % len(data_colors)] for i in range(len(values))],
                    })
                    break

    def _apply_page_backgrounds(
        self,
        report: ReportDefinition,
        background_color: str,
        plan_changes: list,
    ) -> None:
        """Set canvas background and wallpaper color on all pages.

        Mutates ``report.parts`` in-place, updating page.json payloads
        with ``objects.background`` and ``objects.outspace``.
        """
        def _color_expr(hex_val: str) -> dict:
            return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_val}'"}}}}}

        def _lit(val: str) -> dict:
            return {"expr": {"Literal": {"Value": val}}}

        for part in report.parts:
            if not part.path.endswith("/page.json"):
                continue
            if not isinstance(part.payload, dict):
                continue

            page_name = part.payload.get("displayName", part.payload.get("name", "?"))
            objects = part.payload.setdefault("objects", {})

            old_bg = objects.get("background")
            old_ws = objects.get("outspace")

            objects["background"] = [
                {"properties": {"color": _color_expr(background_color), "transparency": _lit("0D")}}
            ]
            objects["outspace"] = [
                {"properties": {"color": _color_expr(background_color), "transparency": _lit("0D")}}
            ]

            if old_bg != objects["background"] or old_ws != objects["outspace"]:
                plan_changes.append({
                    "target": f"page:{page_name}",
                    "path": "objects.background+outspace",
                    "new_value": background_color,
                })

    def apply_style_guide(self, workspace_id: str, report_id: str, style_guide_payload: dict[str, Any], dry_run: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        style_guide = StyleGuide.model_validate(style_guide_payload)

        warnings, blockers = self._validate_report_or_block(report)
        if blockers:
            return ToolResponse(
                success=False,
                summary="Style guide application blocked due to validation blockers",
                blockers=blockers,
                warnings=warnings,
                next_actions=["Resolve blockers", "Retry in dry-run mode after conversion/remediation"],
            )

        transformed, plan = self.transformer.apply_style_guide(report, style_guide, dry_run=dry_run)

        # Apply per-category data colors if the style guide provides a palette
        category_color_changes: list[dict[str, Any]] = []
        data_colors = style_guide.theme.data_colors
        if data_colors:
            dataset_id = self._resolve_dataset_id(workspace_id, report_id)
            self._apply_category_colors(transformed, workspace_id, dataset_id, data_colors, category_color_changes)

        # Apply page background and wallpaper color
        background_changes: list[dict[str, Any]] = []
        self._apply_page_backgrounds(transformed, style_guide.theme.background_color, background_changes)

        # Inject custom theme for global dataColors (controls series colors in all charts)
        theme_injected = False
        if data_colors and not dry_run:
            theme_json = self._build_theme_from_style_guide(style_guide)
            try:
                self.inject_custom_theme(workspace_id, report_id, theme_json, dry_run=False)
                theme_injected = True
            except Exception:
                pass

        all_extra_changes = category_color_changes + background_changes
        diff = self.diff_engine.diff_reports(report, transformed)
        data: dict[str, Any] = {
            "dryRun": dry_run,
            "changeCount": len(plan.changes) + len(all_extra_changes),
            "plan": plan.model_dump(by_alias=True),
            "diff": diff.model_dump(),
        }
        if category_color_changes:
            data["categoryColorChanges"] = category_color_changes
        if background_changes:
            data["backgroundChanges"] = background_changes
        if theme_injected:
            data["themeInjected"] = True
            data["themeDataColors"] = data_colors

        if not dry_run:
            data["definitionParts"] = self._report_to_definition_parts(transformed)
            try:
                self._audit_log("apply_style_guide", workspace_id, report_id, {"changeCount": data["changeCount"]})
            except Exception:
                pass

        return ToolResponse(
            success=True,
            summary="Style guide evaluation completed",
            data=data,
            warnings=warnings + plan.warnings,
            next_actions=["Review diff", "Run update_report_definition with confirm=true to persist"],
        )

    def backup_report_definition(self, workspace_id: str, report_id: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        definition = report.model_dump(mode="json")
        backup_dir = Path(settings.backup_directory)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backup_dir / f"{workspace_id}_{report_id}_{timestamp}.json"
        backup_path.write_text(json.dumps(definition, indent=2), encoding="utf-8")
        return ToolResponse(
            success=True,
            summary="Backup snapshot prepared",
            data={
                "workspaceId": workspace_id,
                "reportId": report_id,
                "backupPath": str(backup_path),
            },
            next_actions=["Store backup file in immutable object storage before writeback"],
        )

    def update_report_definition(self, workspace_id: str, report_id: str, definition_parts: dict[str, Any], confirm: bool = False) -> ToolResponse:
        if not confirm:
            return ToolResponse(
                success=False,
                summary="Writeback blocked because confirm=false",
                blockers=[
                    WarningItem(
                        severity=Severity.BLOCKER,
                        code=MCPErrorCode.CORRUPTED_PAYLOAD_RISK.value,
                        message="Explicit confirmation required before update.",
                        remediation="Set confirm=true after reviewing dry-run diff and validation results.",
                    )
                ],
                next_actions=["Run backup_report_definition", "Run validate_report_definition", "Retry with confirm=true"],
            )

        # Auto-backup before write
        backup_id = None
        try:
            backup_resp = self.backup_report_definition(workspace_id, report_id)
            if backup_resp.success:
                backup_id = backup_resp.data.get("backupPath")
        except Exception:
            pass  # Don't block the write if backup fails

        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status, "payload": state.payload}
        except FabricApiError as exc:
            return ToolResponse(
                success=False,
                summary="Update request failed",
                blockers=[
                    WarningItem(
                        severity=Severity.BLOCKER,
                        code=exc.code.value,
                        message=str(exc),
                        remediation="Review API permissions, payload validity, and retry policy.",
                    )
                ],
                data={"statusCode": exc.status_code, "payload": exc.payload},
            )

        self._invalidate_cache(workspace_id, report_id)

        result["backup_id"] = backup_id

        try:
            self._audit_log("update_report_definition", workspace_id, report_id, {"status": result.get("status")}, backup_id=backup_id)
        except Exception:
            pass

        return ToolResponse(
            success=True,
            summary="Update request completed",
            data=result,
            next_actions=["Re-run analyze_report_structure to verify post-update integrity"],
        )

    def preview_changes(self, before_definition: dict[str, Any], after_definition: dict[str, Any]) -> ToolResponse:
        diff = self.diff_engine.diff_parts(before_definition, after_definition)
        return ToolResponse(success=True, summary="Definition diff generated", data=diff.model_dump(), next_actions=["Review changed parts and risk notes"])

    def validate_report(self, workspace_id: str, report_id: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        warnings, blockers = self._validate_report_or_block(report)
        return ToolResponse(
            success=not blockers,
            summary="Validation completed",
            data={"valid": not blockers},
            warnings=warnings,
            blockers=blockers,
            next_actions=["Fix blockers before writeback"] if blockers else ["Proceed with dry-run transformations"],
        )

    def list_workspaces(self) -> ToolResponse:
        return ToolResponse(success=True, summary="Workspaces listed", data={"workspaces": self.api_client.list_workspaces()})

    def get_default_style_guide(self) -> ToolResponse:
        """Return the default style guide if configured."""
        path = settings.default_style_guide_path
        if not path:
            return ToolResponse(success=False, summary="No default style guide configured",
                                blockers=[WarningItem(severity=Severity.WARNING, code="no_default_style_guide",
                                                      message="Set PBIR_MCP_DEFAULT_STYLE_GUIDE_PATH to a JSON file path.",
                                                      remediation="Set the env var or .env entry.")])
        style_path = Path(path)
        if not style_path.exists():
            return ToolResponse(success=False, summary="Style guide file not found",
                                blockers=[WarningItem(severity=Severity.BLOCKER, code="style_guide_not_found",
                                                      message=f"File not found: {path}")])
        guide = json.loads(style_path.read_text(encoding="utf-8"))
        return ToolResponse(success=True, summary="Default style guide loaded",
                            data={"styleGuide": guide, "path": str(style_path.resolve())})

    def set_default_style_guide(self, style_guide: dict[str, Any]) -> ToolResponse:
        """Save a style guide as the default for all future dashboards."""
        path = settings.default_style_guide_path
        if not path:
            path = str(Path(__file__).resolve().parent.parent.parent / "examples" / "style_guide.default.json")
            settings.default_style_guide_path = path

        style_path = Path(path)
        style_path.parent.mkdir(parents=True, exist_ok=True)
        style_path.write_text(json.dumps(style_guide, indent=2), encoding="utf-8")
        return ToolResponse(success=True, summary="Default style guide saved",
                            data={"path": str(style_path.resolve()), "name": style_guide.get("name", "unnamed")})

    def list_reports(self, workspace_id: str) -> ToolResponse:
        return ToolResponse(success=True, summary="Reports listed", data={"workspaceId": workspace_id, "reports": self.api_client.list_reports(workspace_id)})

    def get_report_metadata(self, workspace_id: str, report_id: str) -> ToolResponse:
        metadata = self.api_client.get_report_metadata(workspace_id, report_id)
        return ToolResponse(success=True, summary="Report metadata retrieved", data=metadata)

    def get_report_pages(self, workspace_id: str, report_id: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        return ToolResponse(success=True, summary="Report pages retrieved", data={"pages": [p.model_dump() for p in report.pages]})

    def get_page_visuals(self, workspace_id: str, report_id: str, page_id_or_name: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        page = self._resolve_page(report, page_id_or_name)
        if not page:
            return ToolResponse(success=False, summary="Page not found", blockers=[WarningItem(severity=Severity.BLOCKER, code="page_not_found", message=page_id_or_name, remediation="Use get_report_pages to list valid identifiers")])
        return ToolResponse(success=True, summary="Page visuals retrieved", data={"page": page.name, "visuals": [v.model_dump() for v in page.visuals]})

    def get_report_assets(self, workspace_id: str, report_id: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        return ToolResponse(success=True, summary="Report assets retrieved", data={"bookmarks": [b.model_dump() for b in report.bookmarks], "staticResources": [s.model_dump() for s in report.static_resources]})

    def score_modernization_readiness(self, workspace_id: str, report_id: str) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        return ToolResponse(success=True, summary="Modernization readiness scored", data=score_modernization(report).model_dump())

    def patch_report_properties(self, workspace_id: str, report_id: str, patch: dict[str, Any], dry_run: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        before = deepcopy(report.metadata)
        after = deepcopy(report.metadata)
        after.update(patch)
        if dry_run:
            return self.preview_changes(before, after)
        report.metadata = after
        return ToolResponse(success=True, summary="Report patch planned", data={"definitionParts": self._report_to_definition_parts(report)})

    def patch_page_properties(self, workspace_id: str, report_id: str, page_id_or_name: str, patch: dict[str, Any], dry_run: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        page = self._resolve_page(report, page_id_or_name)
        if not page:
            return ToolResponse(success=False, summary="Page not found", blockers=[WarningItem(severity=Severity.BLOCKER, code="page_not_found", message=page_id_or_name, remediation="Use get_report_pages to list valid page IDs")])

        before = deepcopy(page.properties)
        after = deepcopy(page.properties)
        after.update(patch)

        if dry_run:
            diff = self.diff_engine.diff_parts(before, after)
            return ToolResponse(success=True, summary="Page patch dry-run generated", data={"dryRun": True, "diff": diff.model_dump()})

        page.properties = after
        return ToolResponse(success=True, summary="Page patch applied", data={"definitionParts": self._report_to_definition_parts(report), "dryRun": False})

    def patch_visual_properties(
        self,
        workspace_id: str,
        report_id: str,
        page_id_or_name: str,
        visual_id_or_name: str,
        patch: dict[str, Any],
        dry_run: bool = True,
    ) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        page = self._resolve_page(report, page_id_or_name)
        if not page:
            return ToolResponse(success=False, summary="Page not found", blockers=[WarningItem(severity=Severity.BLOCKER, code="page_not_found", message=page_id_or_name, remediation="Use get_report_pages to list valid page IDs")])

        visual = self._resolve_visual(page, visual_id_or_name)
        if not visual:
            return ToolResponse(success=False, summary="Visual not found", blockers=[WarningItem(severity=Severity.BLOCKER, code="visual_not_found", message=visual_id_or_name, remediation="Use get_page_visuals to list visual IDs")])

        before = deepcopy(visual.properties)
        after = deepcopy(visual.properties)
        after.update(patch)

        if dry_run:
            diff = self.diff_engine.diff_parts(before, after)
            return ToolResponse(success=True, summary="Visual patch dry-run generated", data={"dryRun": True, "diff": diff.model_dump()})

        visual.properties = after
        return ToolResponse(success=True, summary="Visual patch applied", data={"definitionParts": self._report_to_definition_parts(report), "dryRun": False})

    def replace_theme_resource(self, workspace_id: str, report_id: str, theme_payload: dict[str, Any], dry_run: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        target_part: ReportPart | None = None
        for part in report.parts:
            if "theme" in part.path.lower() or "theme" in part.name.lower():
                target_part = part
                break

        if not target_part:
            return ToolResponse(success=False, summary="Theme resource not found", blockers=[WarningItem(severity=Severity.BLOCKER, code="theme_resource_missing", message="No theme part discovered", remediation="Use get_report_assets to inspect available resources")])

        before = deepcopy(target_part.payload)
        after = deepcopy(theme_payload)

        if dry_run:
            return ToolResponse(success=True, summary="Theme replacement dry-run generated", data={"dryRun": True, "diff": self.diff_engine.diff_parts(before, after).model_dump()})

        target_part.payload = after
        return ToolResponse(success=True, summary="Theme replaced", data={"dryRun": False, "definitionParts": self._report_to_definition_parts(report)})

    def extract_style_guide_from_report(self, workspace_id: str, report_id: str, include_visual_rules: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)

        style_background: dict[str, int] = {}
        style_text: dict[str, int] = {}
        style_corner_radius: dict[int, int] = {}
        title_fonts: dict[str, int] = {}
        body_fonts: dict[str, int] = {}
        title_sizes: dict[int, int] = {}
        body_sizes: dict[int, int] = {}
        visual_rules: dict[str, dict[str, Any]] = {}

        def bump(counter: dict[Any, int], value: Any) -> None:
            if value is None:
                return
            counter[value] = counter.get(value, 0) + 1

        for page in report.pages:
            for visual in page.visuals:
                style = visual.properties.get("style", {}) if isinstance(visual.properties, dict) else {}
                bump(style_background, style.get("backgroundColor"))
                bump(style_text, style.get("textColor"))
                bump(style_corner_radius, style.get("cornerRadius"))
                bump(title_fonts, style.get("titleFontFamily"))
                bump(body_fonts, style.get("bodyFontFamily"))
                bump(title_sizes, style.get("titleFontSize"))
                bump(body_sizes, style.get("bodyFontSize"))

                if include_visual_rules:
                    candidate = {
                        key: value
                        for key, value in style.items()
                        if key in {"titleAlignment", "showBorder", "alternatingRows", "legendPosition", "dataLabelColor"}
                    }
                    if candidate:
                        visual_rules.setdefault(visual.visual_type, {}).update(candidate)

        def most_common(counter: dict[Any, int], fallback: Any) -> Any:
            if not counter:
                return fallback
            return sorted(counter.items(), key=lambda item: item[1], reverse=True)[0][0]

        extracted = {
            "theme": {
                "primaryColor": report.metadata.get("theme", {}).get("primaryColor", "#0078D4"),
                "backgroundColor": most_common(style_background, "#FFFFFF"),
                "textColor": most_common(style_text, "#1F1F1F"),
            },
            "typography": {
                "titleFontFamily": most_common(title_fonts, "Segoe UI Semibold"),
                "bodyFontFamily": most_common(body_fonts, "Segoe UI"),
                "titleFontSize": most_common(title_sizes, 16),
                "bodyFontSize": most_common(body_sizes, 11),
            },
            "layout": {
                "pagePadding": 16,
                "visualSpacing": 12,
                "cornerRadius": most_common(style_corner_radius, 8),
            },
            "rules": {
                "maxVisualsPerPage": max(1, max((len(p.visuals) for p in report.pages), default=6)),
                "allowCustomVisuals": True,
                "enforceTopRowKpis": False,
            },
            "visualRules": visual_rules if include_visual_rules else {},
        }

        return ToolResponse(
            success=True,
            summary="Style guide extracted from report",
            data={
                "workspaceId": workspace_id,
                "reportId": report_id,
                "styleGuide": extracted,
                "sampling": {
                    "pageCount": len(report.pages),
                    "visualCount": sum(len(p.visuals) for p in report.pages),
                },
            },
            next_actions=[
                "Review and harden extracted style guide before bulk rollout",
                "Use apply_style_guide with dry_run=true on target reports",
            ],
        )

    def bulk_apply_style_guide(
        self,
        workspace_id: str,
        report_ids: list[str],
        style_guide_payload: dict[str, Any],
        dry_run: bool = True,
        continue_on_error: bool = True,
    ) -> ToolResponse:
        results: list[dict[str, Any]] = []

        def run_one(rid: str) -> dict[str, Any]:
            try:
                return {"reportId": rid, "result": self.apply_style_guide(workspace_id, rid, style_guide_payload, dry_run=dry_run).model_dump(mode="json")}
            except Exception as exc:  # noqa: BLE001
                if not continue_on_error:
                    raise
                return {
                    "reportId": rid,
                    "result": ToolResponse(
                        success=False,
                        summary="Bulk apply failed",
                        blockers=[WarningItem(severity=Severity.BLOCKER, code="bulk_item_failed", message=str(exc), remediation="Inspect report-specific payload and retry")],
                    ).model_dump(mode="json"),
                }

        with ThreadPoolExecutor(max_workers=max(1, settings.bulk_max_workers)) as pool:
            futures = {pool.submit(run_one, rid): rid for rid in report_ids}
            for future in as_completed(futures):
                results.append(future.result())

        return ToolResponse(
            success=all(r["result"].get("success", False) for r in results),
            summary="Bulk style guide run completed",
            data={"workspaceId": workspace_id, "results": sorted(results, key=lambda r: r["reportId"]), "dryRun": dry_run},
            next_actions=["Review per-report blockers/warnings before persistence"],
        )

    def add_visual_to_page(
        self,
        workspace_id: str,
        report_id: str,
        page_id_or_name: str,
        visual_config: dict[str, Any],
        dry_run: bool = True,
    ) -> ToolResponse:
        """Add a new visual to a page. visual_config should include name, visualType, position, and optionally query/objects."""
        report = self._load_report(workspace_id, report_id)
        page = self._resolve_page(report, page_id_or_name)
        if not page:
            return ToolResponse(
                success=False, summary="Page not found",
                blockers=[WarningItem(severity=Severity.BLOCKER, code="page_not_found", message=page_id_or_name, remediation="Use get_report_pages to list valid page IDs")]
            )

        warnings, blockers = self._validate_report_or_block(report)
        if blockers:
            return ToolResponse(success=False, summary="Blocked by validation errors", blockers=blockers, warnings=warnings)

        name = visual_config.get("name", f"visual_{len(page.visuals)}")
        visual_type = visual_config.get("visualType", "card")
        position = visual_config.get("position", {"x": 20, "y": 20, "z": 0, "width": 400, "height": 300, "tabOrder": 0})
        query = visual_config.get("query")
        objects = visual_config.get("objects", {})
        visual_container_objects = visual_config.get("visualContainerObjects", {})

        schema_url = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json"
        new_visual_payload = {
            "$schema": schema_url,
            "name": name,
            "position": position,
            "visual": {"visualType": visual_type},
        }
        if query:
            new_visual_payload["visual"]["query"] = query
        if objects:
            new_visual_payload["visual"]["objects"] = objects
        if visual_container_objects:
            new_visual_payload["visual"]["visualContainerObjects"] = visual_container_objects

        # Find the page folder path from existing parts
        page_folder = None
        for part in report.parts:
            if part.path.endswith("/page.json"):
                decoded = part.payload if isinstance(part.payload, dict) else {}
                if decoded.get("name") == page.name:
                    page_folder = part.path.rsplit("/", 1)[0]
                    break

        if not page_folder:
            return ToolResponse(
                success=False, summary="Could not resolve page folder path",
                blockers=[WarningItem(severity=Severity.BLOCKER, code="page_path_not_found", message=f"No page.json found for {page_id_or_name}", remediation="Ensure report is PBIR format")]
            )

        new_part_path = f"{page_folder}/visuals/{name}/visual.json"

        if dry_run:
            return ToolResponse(
                success=True, summary="Visual addition dry-run",
                data={"dryRun": True, "newPartPath": new_part_path, "visualPayload": new_visual_payload, "pageName": page.name},
                next_actions=["Set dry_run=false to apply"]
            )

        new_part = ReportPart(
            name=name,
            path=new_part_path,
            content_type="application/json",
            payload=new_visual_payload,
            payload_type="InlineBase64",
        )
        report.parts.append(new_part)

        position_data = new_visual_payload.get("position", {})
        new_visual_def = VisualDefinition(
            id=name, name=name, visual_type=visual_type, page_id=page.name,
            x=position_data.get("x"), y=position_data.get("y"),
            width=position_data.get("width"), height=position_data.get("height"),
            z_order=position_data.get("z"),
            properties={}, objects=objects, raw=new_visual_payload,
        )
        page.visuals.append(new_visual_def)

        definition_parts = self._report_to_definition_parts(report)
        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status}
        except FabricApiError as exc:
            return ToolResponse(success=False, summary="Failed to add visual", blockers=[WarningItem(severity=Severity.BLOCKER, code=exc.code.value, message=str(exc))])

        self._invalidate_cache(workspace_id, report_id)

        try:
            self._audit_log("add_visual_to_page", workspace_id, report_id, {"visualName": name, "pageName": page.name})
        except Exception:
            pass

        self._auto_apply_style(workspace_id, report_id)
        return ToolResponse(success=True, summary=f"Visual '{name}' added to page '{page.name}'", data={"status": result.get("status", "ok"), "visualName": name, "partPath": new_part_path})

    def add_image_visual(
        self,
        workspace_id: str,
        report_id: str,
        page_id_or_name: str,
        image_url: str,
        position: dict[str, Any] | None = None,
        name: str = "image_visual",
        dry_run: bool = True,
    ) -> ToolResponse:
        """Add an image visual to a page using a URL source.

        Uses the correct PBIR format: objects.image[].properties.sourceType='imageUrl'
        and objects.image[].properties.sourceUrl for the URL.
        """
        def _lit(v: str) -> dict:
            return {"expr": {"Literal": {"Value": v}}}

        pos = position or {"x": 20, "y": 20, "z": 0, "width": 200, "height": 100, "tabOrder": 0}

        visual_config = {
            "name": name,
            "visualType": "image",
            "position": pos,
            "objects": {
                "general": [
                    {
                        "properties": {
                            "imageUrl": _lit(f"'{image_url}'"),
                        }
                    }
                ],
                "image": [
                    {
                        "properties": {
                            "sourceType": _lit("'imageUrl'"),
                            "sourceUrl": _lit(f"'{image_url}'"),
                            "transparency": _lit("0L"),
                        }
                    }
                ],
            },
            "visualContainerObjects": {
                "background": [{"properties": {"show": _lit("false")}}],
                "border": [{"properties": {"show": _lit("false")}}],
                "visualHeader": [{"properties": {"show": _lit("false")}}],
                "title": [{"properties": {"show": _lit("false")}}],
            },
        }

        result = self.add_visual_to_page(workspace_id, report_id, page_id_or_name, visual_config, dry_run=dry_run)

        if not dry_run and result.success:
            try:
                self._audit_log("add_image_visual", workspace_id, report_id, {"imageName": name, "imageUrl": image_url})
            except Exception:
                pass

        return result

    def rearrange_page_visuals(
        self,
        workspace_id: str,
        report_id: str,
        page_id_or_name: str,
        layout_config: dict[str, Any],
        dry_run: bool = True,
    ) -> ToolResponse:
        """Validate and fix visual spacing on a page. Detects overlaps and applies consistent gaps."""
        report = self._load_report(workspace_id, report_id)
        page = self._resolve_page(report, page_id_or_name)
        if not page:
            return ToolResponse(success=False, summary="Page not found", blockers=[WarningItem(severity=Severity.BLOCKER, code="page_not_found", message=page_id_or_name)])

        from src.models.schemas import LayoutConfig
        config = LayoutConfig.model_validate(layout_config) if layout_config else LayoutConfig()

        changes: list[dict[str, Any]] = []
        overlaps: list[str] = []
        visuals = page.visuals

        # Detect overlaps
        for i, a in enumerate(visuals):
            if a.x is None or a.y is None or a.width is None or a.height is None:
                continue
            for b in visuals[i+1:]:
                if b.x is None or b.y is None or b.width is None or b.height is None:
                    continue
                if (a.x < b.x + b.width and a.x + a.width > b.x and
                    a.y < b.y + b.height and a.y + a.height > b.y):
                    overlaps.append(f"{a.name or a.id} <-> {b.name or b.id}")

        # Group visuals into rows by proximity of y coordinate
        sorted_visuals = sorted([v for v in visuals if v.y is not None], key=lambda v: (v.y, v.x or 0))
        rows: list[list[VisualDefinition]] = []
        for v in sorted_visuals:
            placed = False
            for row in rows:
                if abs(v.y - row[0].y) < 30:
                    row.append(v)
                    placed = True
                    break
            if not placed:
                rows.append([v])

        # Sort each row by x
        for row in rows:
            row.sort(key=lambda v: v.x or 0)

        # Check and fix gaps
        gap = config.gap
        margin = config.margin
        current_y = margin
        for row in rows:
            # Set y for all visuals in row
            row_height = max(v.height or 0 for v in row)
            for v in row:
                old_y = v.y
                if v.y != current_y:
                    changes.append({"visual": v.name or v.id, "field": "y", "old": old_y, "new": current_y})
                    v.y = current_y

            # Fix horizontal spacing
            current_x = margin
            for v in row:
                old_x = v.x
                if v.x != current_x:
                    changes.append({"visual": v.name or v.id, "field": "x", "old": old_x, "new": current_x})
                    v.x = current_x
                current_x = current_x + (v.width or 0) + gap

            current_y += row_height + gap

        # Update page height if needed
        page_height = current_y + margin - gap
        page_height_change = None
        raw_height = page.raw.get("height")
        if config.auto_height and raw_height and page_height != raw_height:
            page_height_change = {"old": raw_height, "new": page_height}

        if dry_run:
            return ToolResponse(
                success=True, summary=f"Layout audit: {len(changes)} position changes, {len(overlaps)} overlaps",
                data={"dryRun": True, "changes": changes, "overlaps": overlaps, "pageHeight": page_height_change, "rowCount": len(rows)},
                warnings=[WarningItem(severity=Severity.WARNING, code="visual_overlap", message=o) for o in overlaps],
                next_actions=["Set dry_run=false to apply the corrected layout"]
            )

        # Apply changes to the raw parts
        for part in report.parts:
            if not part.path.endswith("/visual.json"):
                continue
            if not isinstance(part.payload, dict):
                continue
            vname = part.payload.get("name", "")
            matching = next((v for v in visuals if (v.name or v.id) == vname), None)
            if matching and matching.x is not None:
                part.payload["position"]["x"] = matching.x
                part.payload["position"]["y"] = matching.y

        # Update page height
        if page_height_change:
            for part in report.parts:
                if part.path.endswith("/page.json") and isinstance(part.payload, dict) and part.payload.get("name") == page.name:
                    part.payload["height"] = page_height_change["new"]

        definition_parts = self._report_to_definition_parts(report)
        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status}
        except FabricApiError as exc:
            return ToolResponse(success=False, summary="Failed to rearrange visuals", blockers=[WarningItem(severity=Severity.BLOCKER, code=exc.code.value, message=str(exc))])

        self._invalidate_cache(workspace_id, report_id)

        try:
            self._audit_log("rearrange_page_visuals", workspace_id, report_id, {"changeCount": len(changes), "page": page_id_or_name})
        except Exception:
            pass

        return ToolResponse(success=True, summary=f"Layout applied: {len(changes)} changes", data={"changes": changes, "overlaps": overlaps, "pageHeight": page_height_change})

    # ── Audit log retrieval ──────────────────────────────────────────────

    def get_audit_log(self, workspace_id: str | None = None, report_id: str | None = None, limit: int = 50) -> ToolResponse:
        log_path = Path(settings.audit_log_path)
        if not log_path.exists():
            return ToolResponse(success=True, summary="No audit entries", data={"entries": []})
        entries = []
        for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            entry = json.loads(line)
            if workspace_id and entry.get("workspace_id") != workspace_id:
                continue
            if report_id and entry.get("report_id") != report_id:
                continue
            entries.append(entry)
        result = entries[-limit:]
        return ToolResponse(success=True, summary=f"{len(result)} audit entries", data={"entries": result})

    # ── Backup listing & restore ─────────────────────────────────────────

    def list_backups(self, workspace_id: str, report_id: str) -> ToolResponse:
        backup_dir = Path(settings.backup_directory)
        if not backup_dir.exists():
            return ToolResponse(success=True, summary="No backups", data={"backups": []})
        prefix = f"{workspace_id}_{report_id}_"
        backups = sorted(
            [
                {
                    "path": str(f),
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=UTC).isoformat(),
                }
                for f in backup_dir.glob(f"{prefix}*.json")
            ],
            key=lambda b: b["modified"],
            reverse=True,
        )
        return ToolResponse(success=True, summary=f"{len(backups)} backups found", data={"backups": backups})

    def restore_report_definition(self, workspace_id: str, report_id: str, backup_path: str, confirm: bool = False) -> ToolResponse:
        path = Path(backup_path)
        if not path.exists():
            return ToolResponse(
                success=False,
                summary="Backup not found",
                blockers=[WarningItem(severity=Severity.BLOCKER, code="backup_not_found", message=backup_path)],
            )

        if not confirm:
            backup_data = json.loads(path.read_text(encoding="utf-8"))
            return ToolResponse(
                success=True,
                summary="Restore preview",
                data={
                    "dryRun": True,
                    "backupFile": backup_path,
                    "pageCount": len(backup_data.get("pages", [])),
                    "partCount": len(backup_data.get("parts", [])),
                },
                next_actions=["Set confirm=true to restore"],
            )

        backup_data = json.loads(path.read_text(encoding="utf-8"))
        definition_parts = self._report_to_definition_parts(ReportDefinition.model_validate(backup_data))
        return self.update_report_definition(workspace_id, report_id, definition_parts, confirm=True)

    # ── Batch apply (single-pass full styling) ───────────────────────────

    def apply_full_style(self, workspace_id: str, report_id: str, style_guide_payload: dict[str, Any] | None = None, dry_run: bool = True) -> ToolResponse:
        """Single-pass: load default or provided style guide, apply everything, write once."""
        if not style_guide_payload:
            default_resp = self.get_default_style_guide()
            if not default_resp.success:
                return default_resp
            style_guide_payload = default_resp.data.get("styleGuide", {})

        return self.apply_style_guide(workspace_id, report_id, style_guide_payload, dry_run=dry_run)

    def _auto_apply_style(self, workspace_id: str, report_id: str) -> None:
        """Automatically apply the default style guide after visual/page creation.

        Silently skipped if no default style guide is configured.
        """
        try:
            default_resp = self.get_default_style_guide()
            if not default_resp.success:
                return
            style_guide = default_resp.data.get("styleGuide", {})
            if not style_guide:
                return
            self.apply_style_guide(workspace_id, report_id, style_guide, dry_run=False)
        except Exception:
            pass  # Never block the primary operation

    @staticmethod
    def _build_theme_from_style_guide(style_guide: StyleGuide) -> dict[str, Any]:
        """Build a Power BI theme JSON from a StyleGuide model."""
        return {
            "name": "Anthropic",
            "dataColors": style_guide.theme.data_colors,
            "background": style_guide.theme.background_color,
            "foreground": style_guide.theme.text_color,
            "tableAccent": style_guide.theme.primary_color,
            "good": "#788C5D",
            "bad": "#C75B3A",
            "neutral": "#B0AEA5",
            "maximum": style_guide.theme.primary_color,
            "center": "#E8E6DC",
            "minimum": style_guide.theme.background_color,
            "textClasses": {
                "title": {
                    "fontFace": style_guide.typography.title_font_family,
                    "fontSize": style_guide.typography.title_font_size,
                    "color": style_guide.theme.text_color,
                },
                "header": {
                    "fontFace": style_guide.typography.title_font_family,
                    "fontSize": 12,
                    "color": style_guide.theme.text_color,
                },
                "label": {
                    "fontFace": style_guide.typography.body_font_family,
                    "fontSize": style_guide.typography.body_font_size,
                    "color": style_guide.theme.text_color,
                },
                "callout": {
                    "fontFace": "Segoe UI Light",
                    "fontSize": 28,
                    "color": style_guide.theme.text_color,
                },
            },
        }

    # ── Page management ──────────────────────────────────────────────────

    def add_page(self, workspace_id: str, report_id: str, page_name: str, display_name: str, position: int | None = None, dry_run: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)
        warnings, blockers = self._validate_report_or_block(report)
        if blockers:
            return ToolResponse(success=False, summary="Blocked", blockers=blockers)

        if any(p.name == page_name for p in report.pages):
            return ToolResponse(
                success=False,
                summary="Page name already exists",
                blockers=[WarningItem(severity=Severity.BLOCKER, code="duplicate_page_name", message=page_name)],
            )

        SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
        page_payload = {
            "$schema": SCHEMA,
            "name": page_name,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        }
        new_part_path = f"definition/pages/{page_name}/page.json"

        if dry_run:
            return ToolResponse(
                success=True,
                summary="Page addition dry-run",
                data={"dryRun": True, "pageName": page_name, "displayName": display_name, "partPath": new_part_path},
            )

        report.parts.append(
            ReportPart(name=page_name, path=new_part_path, content_type="application/json", payload=page_payload, payload_type="InlineBase64")
        )

        for part in report.parts:
            if part.path.endswith("pages/pages.json") and isinstance(part.payload, dict):
                order = part.payload.get("pageOrder", [])
                if position is not None and 0 <= position <= len(order):
                    order.insert(position, page_name)
                else:
                    order.append(page_name)
                part.payload["pageOrder"] = order
                break

        definition_parts = self._report_to_definition_parts(report)
        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status}
        except FabricApiError as exc:
            return ToolResponse(
                success=False,
                summary="Failed to add page",
                blockers=[WarningItem(severity=Severity.BLOCKER, code=exc.code.value, message=str(exc))],
            )

        self._invalidate_cache(workspace_id, report_id)
        self._auto_apply_style(workspace_id, report_id)
        return ToolResponse(success=True, summary=f"Page '{display_name}' added", data={"status": result.get("status"), "pageName": page_name})

    def reorder_pages(self, workspace_id: str, report_id: str, page_order: list[str], dry_run: bool = True) -> ToolResponse:
        report = self._load_report(workspace_id, report_id)

        existing_names = {p.name for p in report.pages}
        for name in page_order:
            if name not in existing_names:
                return ToolResponse(
                    success=False,
                    summary=f"Unknown page: {name}",
                    blockers=[WarningItem(severity=Severity.BLOCKER, code="unknown_page", message=name)],
                )

        if dry_run:
            return ToolResponse(success=True, summary="Reorder dry-run", data={"dryRun": True, "newOrder": page_order})

        for part in report.parts:
            if part.path.endswith("pages/pages.json") and isinstance(part.payload, dict):
                part.payload["pageOrder"] = page_order
                break

        definition_parts = self._report_to_definition_parts(report)
        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status}
        except FabricApiError as exc:
            return ToolResponse(
                success=False,
                summary="Failed to reorder",
                blockers=[WarningItem(severity=Severity.BLOCKER, code=exc.code.value, message=str(exc))],
            )

        self._invalidate_cache(workspace_id, report_id)
        return ToolResponse(success=True, summary="Pages reordered", data={"pageOrder": page_order})

    def inject_custom_theme(
        self,
        workspace_id: str,
        report_id: str,
        theme_json: dict[str, Any],
        theme_name: str = "CustomTheme.json",
        dry_run: bool = True,
    ) -> ToolResponse:
        """Inject a complete custom theme JSON into the report.

        This:
        1. Adds the theme file as StaticResources/RegisteredResources/{theme_name}
        2. Registers it in report.json resourcePackages as type CustomTheme
        3. Sets themeCollection.customTheme to reference it
        """
        report = self._load_report(workspace_id, report_id)
        warnings, blockers = self._validate_report_or_block(report)
        if blockers:
            return ToolResponse(success=False, summary="Blocked", blockers=blockers, warnings=warnings)

        if dry_run:
            return ToolResponse(
                success=True,
                summary="Theme injection dry-run",
                data={
                    "dryRun": True,
                    "themeName": theme_name,
                    "themeKeys": list(theme_json.keys()),
                    "dataColors": theme_json.get("dataColors", []),
                },
            )

        # 1. Update report.json: themeCollection + resourcePackages
        for part in report.parts:
            if part.path != "definition/report.json" or not isinstance(part.payload, dict):
                continue

            # Get current reportVersionAtImport from baseTheme
            base_theme = part.payload.get("themeCollection", {}).get("baseTheme", {})
            rvi = base_theme.get(
                "reportVersionAtImport",
                {"visual": "1.8.91", "report": "2.0.91", "page": "1.3.91"},
            )

            # Set customTheme reference
            part.payload.setdefault("themeCollection", {})["customTheme"] = {
                "name": theme_name,
                "reportVersionAtImport": rvi,
                "type": "RegisteredResources",
            }

            # Register in resourcePackages
            rp = part.payload.setdefault("resourcePackages", [])
            reg_pkg = next((pkg for pkg in rp if pkg.get("name") == "RegisteredResources"), None)
            if not reg_pkg:
                reg_pkg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
                rp.append(reg_pkg)

            # Remove old theme registrations, add new
            reg_pkg["items"] = [item for item in reg_pkg.get("items", []) if item.get("type") != "CustomTheme"]
            reg_pkg["items"].append({"name": theme_name, "path": theme_name, "type": "CustomTheme"})
            break

        # 2. Remove old theme static resource parts, add new
        report.parts = [
            p
            for p in report.parts
            if not (p.path.startswith("StaticResources/") and p.path.endswith(".json") and "Theme" in p.path)
        ]

        # Add new theme as a static resource part
        report.parts.append(
            ReportPart(
                name=theme_name,
                path=f"StaticResources/RegisteredResources/{theme_name}",
                content_type="application/json",
                payload=theme_json,
                payload_type="InlineBase64",
            )
        )

        # 3. Write back
        definition_parts = self._report_to_definition_parts(report)
        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status}
        except FabricApiError as exc:
            return ToolResponse(
                success=False,
                summary="Theme injection failed",
                blockers=[WarningItem(severity=Severity.BLOCKER, code=exc.code.value, message=str(exc))],
            )

        self._invalidate_cache(workspace_id, report_id)
        self._audit_log(
            "inject_custom_theme",
            workspace_id,
            report_id,
            {"theme_name": theme_name, "dataColors": theme_json.get("dataColors", [])},
        )
        return ToolResponse(
            success=True,
            summary=f"Custom theme '{theme_name}' injected",
            data={"status": result.get("status"), "themeName": theme_name},
        )

    def apply_conditional_format(
        self,
        workspace_id: str,
        report_id: str,
        page_id_or_name: str,
        visual_id_or_name: str,
        column_field: str,
        rules: list[dict[str, Any]],
        target_property: str = "fontColor",
        dry_run: bool = True,
    ) -> ToolResponse:
        """Apply conditional formatting rules to a visual column.

        Each rule: {"operator": ">", "value": 0, "color": "#C75B3A"}
        Operators: "=", ">", ">=", "<", "<=", "!="

        column_field format: "entity.property" e.g. "gd_service_principal_summary.failed_events"
        """
        report = self._load_report(workspace_id, report_id)
        page = self._resolve_page(report, page_id_or_name)
        if not page:
            return ToolResponse(
                success=False,
                summary="Page not found",
                blockers=[WarningItem(severity=Severity.BLOCKER, code="page_not_found", message=page_id_or_name)],
            )
        visual = self._resolve_visual(page, visual_id_or_name)
        if not visual:
            return ToolResponse(
                success=False,
                summary="Visual not found",
                blockers=[WarningItem(severity=Severity.BLOCKER, code="visual_not_found", message=visual_id_or_name)],
            )

        # Parse column_field
        parts_split = column_field.split(".", 1)
        if len(parts_split) != 2:
            return ToolResponse(
                success=False,
                summary="Invalid column_field format",
                blockers=[
                    WarningItem(
                        severity=Severity.BLOCKER,
                        code="invalid_field",
                        message=f"Expected 'entity.property', got '{column_field}'",
                    )
                ],
            )
        entity, prop = parts_split

        # Build FillRule format (the correct PBIR format for conditional formatting)
        # Uses linearGradient2 with same min/max color for solid fill,
        # and dataViewWildcard selector for per-row evaluation
        if len(rules) == 1:
            # Single color rule: use linearGradient2 with solid color
            color = rules[0].get("color", "#C75B3A")
            cond_format = {
                "solid": {
                    "color": {
                        "expr": {
                            "FillRule": {
                                "Input": {
                                    "Aggregation": {
                                        "Expression": {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Entity": entity}},
                                                "Property": prop,
                                            }
                                        },
                                        "Function": 0,
                                    }
                                },
                                "FillRule": {
                                    "linearGradient2": {
                                        "min": {"color": {"Literal": {"Value": f"'{color}'"}}},
                                        "max": {"color": {"Literal": {"Value": f"'{color}'"}}},
                                        "nullColoringStrategy": {
                                            "strategy": {"Literal": {"Value": "'asZero'"}}
                                        },
                                    }
                                },
                            }
                        }
                    }
                }
            }
        else:
            # Two-color gradient: min color from first rule, max from last
            min_color = rules[0].get("color", "#FFFFFF")
            max_color = rules[-1].get("color", "#C75B3A")
            cond_format = {
                "solid": {
                    "color": {
                        "expr": {
                            "FillRule": {
                                "Input": {
                                    "Aggregation": {
                                        "Expression": {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Entity": entity}},
                                                "Property": prop,
                                            }
                                        },
                                        "Function": 0,
                                    }
                                },
                                "FillRule": {
                                    "linearGradient2": {
                                        "min": {"color": {"Literal": {"Value": f"'{min_color}'"}}},
                                        "max": {"color": {"Literal": {"Value": f"'{max_color}'"}}},
                                        "nullColoringStrategy": {
                                            "strategy": {"Literal": {"Value": "'asZero'"}}
                                        },
                                    }
                                },
                            }
                        }
                    }
                }
            }

        selector = {
            "data": [{"dataViewWildcard": {"matchingOption": 1}}],
            "metadata": column_field,
        }

        if dry_run:
            return ToolResponse(
                success=True,
                summary=f"Conditional format dry-run: {len(rules)} rules on {column_field}",
                data={
                    "dryRun": True,
                    "rules": rules,
                    "targetProperty": target_property,
                    "generatedFormat": cond_format,
                    "visual": visual_id_or_name,
                },
            )

        # Apply to the visual's raw part using values[] with dataViewWildcard selector
        for part in report.parts:
            if not part.path.endswith("/visual.json") or not isinstance(part.payload, dict):
                continue
            if part.payload.get("name") != (visual.name or visual.id):
                continue

            objects = part.payload.setdefault("visual", {}).setdefault("objects", {})
            values_list = objects.setdefault("values", [])

            # Remove existing conditional format for this column
            values_list = [
                e for e in values_list
                if not (e.get("selector", {}).get("metadata") == column_field and "data" in e.get("selector", {}))
            ]
            values_list.append({"properties": {target_property: cond_format}, "selector": selector})
            objects["values"] = values_list
            break

        definition_parts = self._report_to_definition_parts(report)
        try:
            result = self.api_client.update_report_definition(workspace_id, report_id, definition_parts)
            if result.get("status") == "pending" and result.get("location"):
                state = self.api_client.wait_for_operation(result["location"])
                result = {"status": state.status}
        except FabricApiError as exc:
            return ToolResponse(
                success=False,
                summary="Conditional format failed",
                blockers=[WarningItem(severity=Severity.BLOCKER, code=exc.code.value, message=str(exc))],
            )

        self._invalidate_cache(workspace_id, report_id)
        self._audit_log(
            "apply_conditional_format",
            workspace_id,
            report_id,
            {"visual": visual_id_or_name, "column": column_field, "rules": rules},
        )
        return ToolResponse(
            success=True,
            summary=f"Conditional format applied: {len(rules)} rules on {column_field}",
            data={"status": result.get("status")},
        )
