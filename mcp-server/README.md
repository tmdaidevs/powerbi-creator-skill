# Power BI / Fabric Design MCP Server

Production-oriented MCP server for safely modernizing Power BI / Microsoft Fabric report definitions via official REST APIs, without downloading PBIX/PBIP artifacts locally.

## 1) Architecture overview

The implementation uses six explicit layers:

1. **MCP Server Layer**: tool surface for LLM/MCP clients (`src/server/mcp_server.py`).
2. **Fabric API Client Layer**: auth, retry, throttling, async/polling, typed errors (`src/fabric_client/client.py`).
3. **Parser Layer**: definition-part normalization into typed report models (`src/parser/definition_parser.py`).
4. **Transformation Layer**: deterministic style rule application and patch planning (`src/transformations/style_engine.py`).
5. **Validation Layer**: compatibility and integrity checks before writeback (`src/validation/validator.py`).
6. **Diff/Preview Layer**: structured before/after diffs for dry-run approvals (`src/diffing/diff_engine.py`).

See `docs/architecture.md` for concise layer mapping.

## 2) Repository structure

```text
/src
  /server
  /mcp_tools
  /fabric_client
  /models
  /parser
  /transformations
  /validation
  /diffing
  /auth
  /config
  /utils
/tests
/docs
/examples
```

## 3) Data model design

Pydantic models define strong contracts for:
- `ReportDefinition`
- `ReportPart`
- `PageDefinition`
- `VisualDefinition`
- `BookmarkDefinition`
- `StaticResource`
- `StyleGuide`
- `TransformationPlan`
- `ValidationResult`
- `DiffResult`
- `ModernizationScore`

See `src/models/schemas.py`.

## 4) MCP tool contracts

Implemented tools:

### Discovery / inventory
- `list_workspaces()`
- `list_reports(workspace_id)`
- `get_report_metadata(workspace_id, report_id)`
- `analyze_report_structure(workspace_id, report_id)`

### Definition retrieval
- `get_report_definition(workspace_id, report_id)`
- `get_report_pages(workspace_id, report_id)`
- `get_page_visuals(workspace_id, report_id, page_id_or_name)`
- `get_report_assets(workspace_id, report_id)`

### Styling / transformation
- `apply_style_guide(workspace_id, report_id, style_guide, dry_run=true)`
- `patch_report_properties(workspace_id, report_id, patch, dry_run=true)`
- `patch_page_properties(workspace_id, report_id, page_id_or_name, patch, dry_run=true)`
- `patch_visual_properties(workspace_id, report_id, page_id_or_name, visual_id_or_name, patch, dry_run=true)`
- `replace_theme_resource(workspace_id, report_id, theme_payload, dry_run=true)`

### Validation / preview
- `validate_report_definition(workspace_id, report_id)`
- `preview_changes(workspace_id, report_id, proposed_changes)`
- `diff_report_definition(before_definition, after_definition)`

### Persistence
- `update_report_definition(workspace_id, report_id, definition_parts, confirm=false)`
- `backup_report_definition(workspace_id, report_id)`

### Governance / bulk operations
- `score_modernization_readiness(workspace_id, report_id)`
- `bulk_apply_style_guide(workspace_id, report_ids, style_guide, dry_run=true)`
- `extract_style_guide_from_report(workspace_id, report_id, include_visual_rules=true)`

All outputs are stable JSON envelopes with success status, warnings, blockers, and recommended next actions.

## 5) Implementation plan (executed)

1. Define typed domain models and common response/error schema.
2. Implement auth and Fabric REST client with resilience patterns.
3. Build report definition parser for pages/visuals/bookmarks/resources.
4. Implement deterministic style transformations with patch plan output.
5. Add validation engine with blocker/warning severity model.
6. Add diff and modernization scoring logic.
7. Expose MCP tools and wire service orchestration.
8. Add tests, examples, and documentation.

## 6) Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run MCP server:

```bash
python -m src.server.mcp_server
```

## 7) Authentication modes

Supported token modes:
- Service principal (`PBIR_MCP_TENANT_ID`, `PBIR_MCP_CLIENT_ID`, `PBIR_MCP_CLIENT_SECRET`)
- Managed identity (`PBIR_MCP_USE_MANAGED_IDENTITY=true`)
- Delegated/default Azure credential chain

Auth logic lives in `src/auth/token_provider.py`.

## 8) Required API permissions

Grant appropriate Fabric / Power BI API permissions to read and update report definitions in target workspaces. Use least privilege and scoped workspace access.

## 9) Dry-run, backup, and validation behavior

- **Dry-run default** for transformations.
- `update_report_definition` requires `confirm=true`.
- Use `backup_report_definition` before writeback (persisted to `PBIR_MCP_BACKUP_DIRECTORY`, default `./backups`).
- Validation blockers prevent unsafe operations.
- Async Fabric operations are polled automatically with configurable timeout/interval (`PBIR_MCP_ASYNC_POLL_TIMEOUT_SECONDS`, `PBIR_MCP_ASYNC_POLL_INTERVAL_SECONDS`).

## 10) Supported scenarios

- PBIR-compatible report definition analysis
- style guide enforcement for deterministic formatting fields
- diff preview before writeback
- bulk style dry-runs with per-report outputs

## 11) Known limitations / explicit non-goals

- PBIR-Legacy and unknown formats are blocked for writeback.
- No semantic model authoring or DAX generation.
- No Power BI Desktop automation.
- No hidden/private/unofficial APIs.
- No promise of mobile layout editing where unsupported externally.

## 12) Style guide extensibility

Use `visualRules` and additional JSON properties in the style guide model (`extra=allow`) to evolve policy safely. Example file: `examples/style_guide.enterprise.json`.

## 13) Sample prompts for LLM agents

See:
- `examples/sample_modernization_flow.md`

## 14) Testing

```bash
pytest
```

Includes unit coverage for parser/transform/validation/diff/service patching, plus integration stubs in `tests/integration`.

Live integration tests are gated behind `RUN_LIVE_FABRIC_TESTS=true` to avoid accidental calls in standard CI.

## 15) Recommended auth mode by deployment pattern

- **Best cloud default:** Managed Identity (if running in Azure-hosted infrastructure with tenant controls).
- **Best cross-environment automation default:** Service Principal with certificate/secret vaulting.
- **Delegated auth:** useful for interactive diagnostics and analyst-led ad hoc use, not preferred for unattended production jobs.
