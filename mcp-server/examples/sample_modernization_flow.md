# Sample Dry-Run Modernization Flow

1. `list_workspaces()`
2. `list_reports(workspace_id)`
3. `analyze_report_structure(workspace_id, report_id)`
4. `validate_report_definition(workspace_id, report_id)`
5. `backup_report_definition(workspace_id, report_id)`
6. `apply_style_guide(workspace_id, report_id, style_guide, dry_run=true)`
7. `preview_changes(workspace_id, report_id, proposed_changes)`
8. `update_report_definition(..., confirm=true)` only after approvals
