from __future__ import annotations

from typing import Any

from src.server.service import ReportModernizationService

service = ReportModernizationService()


def list_workspaces() -> dict[str, Any]:
    return service.list_workspaces().model_dump(mode="json")


def list_reports(workspace_id: str) -> dict[str, Any]:
    return service.list_reports(workspace_id).model_dump(mode="json")


def get_report_metadata(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.get_report_metadata(workspace_id, report_id).model_dump(mode="json")


def analyze_report_structure(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.analyze_report_structure(workspace_id, report_id).model_dump(mode="json")


def get_report_definition(workspace_id: str, report_id: str) -> dict[str, Any]:
    report = service._load_report(workspace_id, report_id)
    return {"success": True, "summary": "Report definition retrieved", "data": report.model_dump(mode="json")}


def get_report_pages(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.get_report_pages(workspace_id, report_id).model_dump(mode="json")


def get_page_visuals(workspace_id: str, report_id: str, page_id_or_name: str) -> dict[str, Any]:
    return service.get_page_visuals(workspace_id, report_id, page_id_or_name).model_dump(mode="json")


def get_report_assets(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.get_report_assets(workspace_id, report_id).model_dump(mode="json")


def apply_style_guide(workspace_id: str, report_id: str, style_guide: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return service.apply_style_guide(workspace_id, report_id, style_guide, dry_run=dry_run).model_dump(mode="json")


def patch_report_properties(workspace_id: str, report_id: str, patch: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return service.patch_report_properties(workspace_id, report_id, patch, dry_run=dry_run).model_dump(mode="json")


def patch_page_properties(workspace_id: str, report_id: str, page_id_or_name: str, patch: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return service.patch_page_properties(workspace_id, report_id, page_id_or_name, patch, dry_run=dry_run).model_dump(mode="json")


def patch_visual_properties(workspace_id: str, report_id: str, page_id_or_name: str, visual_id_or_name: str, patch: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return service.patch_visual_properties(
        workspace_id,
        report_id,
        page_id_or_name,
        visual_id_or_name,
        patch,
        dry_run=dry_run,
    ).model_dump(mode="json")


def replace_theme_resource(workspace_id: str, report_id: str, theme_payload: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return service.replace_theme_resource(workspace_id, report_id, theme_payload, dry_run=dry_run).model_dump(mode="json")


def validate_report_definition(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.validate_report(workspace_id, report_id).model_dump(mode="json")


def preview_changes(workspace_id: str, report_id: str, proposed_changes: dict[str, Any]) -> dict[str, Any]:
    before = proposed_changes.get("before", {})
    after = proposed_changes.get("after", {})
    return service.preview_changes(before, after).model_dump(mode="json")


def diff_report_definition(before_definition: dict[str, Any], after_definition: dict[str, Any]) -> dict[str, Any]:
    return service.preview_changes(before_definition, after_definition).model_dump(mode="json")


def update_report_definition(workspace_id: str, report_id: str, definition_parts: dict[str, Any], confirm: bool = False) -> dict[str, Any]:
    return service.update_report_definition(workspace_id, report_id, definition_parts, confirm=confirm).model_dump(mode="json")


def backup_report_definition(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.backup_report_definition(workspace_id, report_id).model_dump(mode="json")


def score_modernization_readiness(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.score_modernization_readiness(workspace_id, report_id).model_dump(mode="json")


def bulk_apply_style_guide(workspace_id: str, report_ids: list[str], style_guide: dict[str, Any], dry_run: bool = True, continue_on_error: bool = True) -> dict[str, Any]:
    return service.bulk_apply_style_guide(
        workspace_id=workspace_id,
        report_ids=report_ids,
        style_guide_payload=style_guide,
        dry_run=dry_run,
        continue_on_error=continue_on_error,
    ).model_dump(mode="json")


def extract_style_guide_from_report(workspace_id: str, report_id: str, include_visual_rules: bool = True) -> dict[str, Any]:
    return service.extract_style_guide_from_report(
        workspace_id=workspace_id,
        report_id=report_id,
        include_visual_rules=include_visual_rules,
    ).model_dump(mode="json")


def add_visual_to_page(workspace_id: str, report_id: str, page_id_or_name: str, visual_config: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return service.add_visual_to_page(workspace_id, report_id, page_id_or_name, visual_config, dry_run=dry_run).model_dump(mode="json")


def rearrange_page_visuals(workspace_id: str, report_id: str, page_id_or_name: str, layout_config: dict[str, Any] | None = None, dry_run: bool = True) -> dict[str, Any]:
    return service.rearrange_page_visuals(workspace_id, report_id, page_id_or_name, layout_config or {}, dry_run=dry_run).model_dump(mode="json")


def add_image_visual(workspace_id: str, report_id: str, page_id_or_name: str, image_url: str, position: dict[str, Any] | None = None, name: str = "image_visual", dry_run: bool = True) -> dict[str, Any]:
    return service.add_image_visual(workspace_id, report_id, page_id_or_name, image_url, position=position, name=name, dry_run=dry_run).model_dump(mode="json")


def build_page(workspace_id: str, report_id: str, page_name: str, display_name: str, visuals: list[dict[str, Any]], dry_run: bool = True) -> dict[str, Any]:
    return service.build_page(workspace_id, report_id, page_name, display_name, visuals, dry_run=dry_run).model_dump(mode="json")


def get_default_style_guide() -> dict[str, Any]:
    return service.get_default_style_guide().model_dump(mode="json")


def set_default_style_guide(style_guide: dict[str, Any]) -> dict[str, Any]:
    return service.set_default_style_guide(style_guide).model_dump(mode="json")


def get_audit_log(workspace_id: str | None = None, report_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    return service.get_audit_log(workspace_id=workspace_id, report_id=report_id, limit=limit).model_dump(mode="json")


def list_backups(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.list_backups(workspace_id, report_id).model_dump(mode="json")


def restore_report_definition(workspace_id: str, report_id: str, backup_path: str, confirm: bool = False) -> dict[str, Any]:
    return service.restore_report_definition(workspace_id, report_id, backup_path, confirm=confirm).model_dump(mode="json")


def apply_full_style(workspace_id: str, report_id: str, style_guide: dict[str, Any] | None = None, dry_run: bool = True) -> dict[str, Any]:
    return service.apply_full_style(workspace_id, report_id, style_guide_payload=style_guide, dry_run=dry_run).model_dump(mode="json")


def add_page(workspace_id: str, report_id: str, page_name: str, display_name: str, position: int | None = None, dry_run: bool = True) -> dict[str, Any]:
    return service.add_page(workspace_id, report_id, page_name, display_name, position=position, dry_run=dry_run).model_dump(mode="json")


def reorder_pages(workspace_id: str, report_id: str, page_order: list[str], dry_run: bool = True) -> dict[str, Any]:
    return service.reorder_pages(workspace_id, report_id, page_order, dry_run=dry_run).model_dump(mode="json")


def full_modernization(workspace_id: str, report_id: str, confirm: bool = False) -> dict[str, Any]:
    return service.full_modernization(workspace_id, report_id, confirm=confirm).model_dump(mode="json")


def inject_custom_theme(workspace_id: str, report_id: str, theme_json: dict[str, Any], theme_name: str = "CustomTheme.json", dry_run: bool = True) -> dict[str, Any]:
    return service.inject_custom_theme(workspace_id, report_id, theme_json, theme_name=theme_name, dry_run=dry_run).model_dump(mode="json")


def apply_conditional_format(workspace_id: str, report_id: str, page_id_or_name: str, visual_id_or_name: str, column_field: str, rules: list[dict[str, Any]], target_property: str = "fontColor", dry_run: bool = True) -> dict[str, Any]:
    return service.apply_conditional_format(workspace_id, report_id, page_id_or_name, visual_id_or_name, column_field, rules, target_property=target_property, dry_run=dry_run).model_dump(mode="json")


def remove_visual(workspace_id: str, report_id: str, page_id_or_name: str, visual_id_or_name: str, dry_run: bool = True) -> dict[str, Any]:
    return service.remove_visual(workspace_id, report_id, page_id_or_name, visual_id_or_name, dry_run=dry_run).model_dump(mode="json")


def remove_page(workspace_id: str, report_id: str, page_id_or_name: str, dry_run: bool = True) -> dict[str, Any]:
    return service.remove_page(workspace_id, report_id, page_id_or_name, dry_run=dry_run).model_dump(mode="json")


def rename_visual(workspace_id: str, report_id: str, page_id_or_name: str, visual_id_or_name: str, new_name: str, dry_run: bool = True) -> dict[str, Any]:
    return service.rename_visual(workspace_id, report_id, page_id_or_name, visual_id_or_name, new_name, dry_run=dry_run).model_dump(mode="json")


def get_semantic_model_schema(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.get_semantic_model_schema(workspace_id, report_id).model_dump(mode="json")


def suggest_visuals(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.suggest_visuals(workspace_id, report_id).model_dump(mode="json")


def auto_layout(visuals: list[dict[str, Any]], page_width: int = 1280, margin: int = 20, gap: int = 20) -> dict[str, Any]:
    return service.auto_layout(visuals, page_width=page_width, margin=margin, gap=gap).model_dump(mode="json")


def compare_reports(workspace_id: str, report_id_a: str, report_id_b: str) -> dict[str, Any]:
    return service.compare_reports(workspace_id, report_id_a, report_id_b).model_dump(mode="json")


def export_report_summary(workspace_id: str, report_id: str) -> dict[str, Any]:
    return service.export_report_summary(workspace_id, report_id).model_dump(mode="json")
