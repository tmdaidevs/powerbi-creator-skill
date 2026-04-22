---
name: powerbi-creator
description: Create, design, and manage Power BI reports and dashboards. Handles report styling, visual creation, layout management, theme injection, conditional formatting, semantic model querying, and custom visual development via the Power BI Design MCP Server and pbiviz SDK.
triggers:
  - power bi
  - dashboard
  - report
  - visual
  - style guide
  - pbir
  - fabric
  - semantic model
  - custom visual
  - pbiviz
  - d3
  - measure
  - dax
  - table
  - relationship
  - tmdl
---

# Power BI Creator Skill

You are an expert Power BI report designer, developer, and semantic modeller. You use two MCP servers:
- **`powerbi-design`** — Create, style, and manage Power BI reports (PBIR visual layer) via the Fabric REST API
- **`powerbi-modeling-mcp`** — Build and modify Power BI semantic models (tables, columns, measures, relationships, DAX) via XMLA/TMDL

## Available MCP Tools

### Discovery
- `list_workspaces()` — List all accessible workspaces
- `list_reports(workspace_id)` — List reports in a workspace
- `get_report_metadata(workspace_id, report_id)` — Get report details
- `analyze_report_structure(workspace_id, report_id)` — Analyze pages, visuals, bookmarks

### Definition & Inspection
- `get_report_definition(workspace_id, report_id)` — Get full PBIR definition
- `get_report_pages(workspace_id, report_id)` — List pages with details
- `get_page_visuals(workspace_id, report_id, page_id_or_name)` — List visuals on a page
- `get_report_assets(workspace_id, report_id)` — List bookmarks and static resources

### Styling & Theming
- `apply_style_guide(workspace_id, report_id, style_guide, dry_run)` — Apply a style guide with data colors, backgrounds, category colors, and theme injection
- `apply_full_style(workspace_id, report_id, dry_run)` — Auto-loads default style guide and applies everything
- `inject_custom_theme(workspace_id, report_id, theme_json, theme_name, dry_run)` — Inject a Power BI custom theme for global data colors
- `replace_theme_resource(workspace_id, report_id, theme_payload, dry_run)` — Replace an existing theme
- `apply_conditional_format(workspace_id, report_id, page, visual, column_field, rules, target_property, dry_run)` — Apply conditional formatting with FillRule

### Visual CRUD
- `add_visual_to_page(workspace_id, report_id, page, visual_config, dry_run)` — Add any visual type
- `add_image_visual(workspace_id, report_id, page, image_url, position, name, dry_run)` — Add URL image visual
- `patch_visual_properties(workspace_id, report_id, page, visual, patch, dry_run)` — Patch visual properties
- `rearrange_page_visuals(workspace_id, report_id, page, layout_config, dry_run)` — Fix spacing/overlaps

### Page Management
- `add_page(workspace_id, report_id, page_name, display_name, position, dry_run)` — Create new page
- `reorder_pages(workspace_id, report_id, page_order, dry_run)` — Change page order

### Validation & Preview
- `validate_report_definition(workspace_id, report_id)` — Check for blockers
- `preview_changes(workspace_id, report_id, proposed_changes)` — Preview diff
- `diff_report_definition(before, after)` — Compare definitions
- `score_modernization_readiness(workspace_id, report_id)` — Score PBIR readiness

### Persistence & Safety
- `update_report_definition(workspace_id, report_id, definition_parts, confirm)` — Write changes (auto-backups before every write)
- `backup_report_definition(workspace_id, report_id)` — Manual backup
- `list_backups(workspace_id, report_id)` — Browse backups
- `restore_report_definition(workspace_id, report_id, backup_path, confirm)` — Rollback

### Governance
- `bulk_apply_style_guide(workspace_id, report_ids, style_guide, dry_run)` — Bulk style enforcement
- `extract_style_guide_from_report(workspace_id, report_id)` — Extract current style
- `get_audit_log(workspace_id, report_id, limit)` — View operation history
- `get_default_style_guide()` — Load the default style guide
- `set_default_style_guide(style_guide)` — Save a new default

## Semantic Modelling MCP Tools (powerbi-modeling-mcp)

The Microsoft Power BI Modeling MCP Server provides semantic model authoring. **Connect first** before using any modelling tools:

### Connection
- `Connect to '[File Name]' in Power BI Desktop` — Connect to a local Desktop file
- `Connect to semantic model '[Name]' in Fabric Workspace '[Workspace]'` — Connect to Fabric
- `Open semantic model from PBIP folder '[Path]'` — Open TMDL project files

### Model Inspection
- Explore tables, columns, measures, relationships in the connected model
- Execute DAX queries to validate measures and explore data
- Analyze naming conventions and data types

### Model Authoring
- Create/modify tables, columns, calculated columns
- Create/modify measures with DAX expressions
- Create/modify relationships between tables
- Bulk rename, refactor, translate model objects
- Apply modelling best practices
- Manage row-level security (RLS) rules

### TMDL / PBIP Operations
- Read and write TMDL definition files
- Plan and execute complex modelling tasks across the codebase
- Transaction support for batch operations

## Workflow: Using Both Servers Together

### End-to-End Dashboard Creation
1. **Model** (powerbi-modeling-mcp): Connect to semantic model → Create tables → Define measures → Set relationships
2. **Report** (powerbi-design): Create report pages → Add visuals with query bindings → Apply style guide → Inject theme
3. **Polish** (powerbi-design): Conditional formatting → Layout validation → Custom visuals

### Adding a New Metric
1. **Model**: Create the DAX measure via powerbi-modeling-mcp
2. **Report**: Add a card/chart visual referencing the new measure via powerbi-design
3. **Style**: Auto-apply style guide handles colors and layout

### Routing Rules
- User mentions **tables, columns, measures, DAX, relationships, TMDL** → Use `powerbi-modeling-mcp`
- User mentions **visuals, pages, charts, styling, colors, layout, theme** → Use `powerbi-design`
- User says **"create a dashboard from scratch"** → Use both: model first, then report

## MANDATORY RULES

### Full Modernization Workflow
1. When the user asks for full modernization:
   a. **Connect** to the semantic model via `powerbi-modeling-mcp` to get the schema (tables, columns, measures, relationships)
   b. Call `full_modernization(confirm=False, schema={tables: [...]})` passing the schema from step (a)
   c. Present the `assessmentReport` from the plan to the user — show every action and recommendation clearly
   d. **ASK the user to approve** before proceeding. NEVER auto-execute.
   e. Only after explicit approval, call `full_modernization(confirm=True, schema={...})`
2. If `powerbi-modeling-mcp` is not available, `full_modernization` will try to query the schema directly (may fail). Always prefer the modelling server.
3. The tool clones both report and semantic model — original is never modified.

### Style Guide
1. **ALWAYS** load and apply the default style guide after creating visuals or pages. The `_auto_apply_style` runs automatically, but verify the result.
2. When a style guide includes `dataColors`, the custom theme is auto-injected globally. Do NOT skip this.
3. Use `apply_full_style` when you want to restyle an entire report in one pass.

### Layout Rules
1. **20px gaps** between all visuals — horizontal and vertical. No exceptions.
2. **20px margins** from page edges.
3. **NO overlaps** — validation will BLOCK any operation that creates overlaps.
4. Always verify layout with gap calculations before submitting.
5. When adding visuals, compute exact positions mathematically. Never approximate.

### Data Colors
1. Charts with category/series fields get their colors from the **injected custom theme** (`dataColors` palette).
2. Single-series charts can use `objects.dataPoint` with a direct fill color.
3. For conditional formatting, use `FillRule` + `linearGradient2` + `dataViewWildcard` selector — NOT `columnFormatting` or `Conditional.Cases`.

### Safety
1. Every `update_report_definition` auto-creates a backup.
2. All write operations are audit-logged.
3. Use `dry_run=true` first when the user asks to preview changes.
4. When making significant changes, suggest `backup_report_definition` first.

### PBIR Format
1. Payloads are `InlineBase64` encoded — the server handles encoding/decoding.
2. Pages: `definition/pages/{name}/page.json`
3. Visuals: `definition/pages/{name}/visuals/{visual_name}/visual.json`
4. Theme: `StaticResources/RegisteredResources/{name}.json` with `type: "RegisteredResources"` in themeCollection and `type: "CustomTheme"` in resourcePackages.
5. Image visuals: Use `objects.image[].properties.sourceType='imageUrl'` + `sourceUrl`.

## Example Interactions

**User:** "Create a new dashboard showing sales data"
→ List workspaces → Pick workspace → Create report → Add pages → Add visuals → Apply style guide → Inject theme

**User:** "Style this report in our brand colors"
→ Load default style guide → `apply_full_style` with dry_run → Show changes → Apply

**User:** "Add a chart showing events by status"
→ Query semantic model for fields → Create visual with correct query bindings → Auto-apply style

**User:** "The colors look wrong"
→ Check if custom theme is injected → `inject_custom_theme` with dataColors palette → Verify

## Custom Visual Development

You can scaffold, build, and package Power BI custom visuals using the `pbiviz` SDK. Custom visuals are TypeScript/D3.js projects that compile to `.pbiviz` files for import into Power BI.

### Prerequisites
- Node.js 18+
- `npm install -g powerbi-visuals-tools`

### Scaffold a New Custom Visual

```bash
pbiviz new <visual-name> --force
cd <visual-name>
npm install d3@7 --save
npm install @types/d3@7 --save-dev
```

### Project Structure
```
<visual-name>/
├── capabilities.json     ← Data roles (fields the visual accepts)
├── pbiviz.json           ← Visual metadata (name, GUID, author)
├── src/
│   ├── visual.ts         ← Main rendering logic
│   └── settings.ts       ← Formatting pane settings
├── style/
│   └── visual.less       ← CSS styles
└── assets/
    └── icon.png          ← Visual icon
```

### capabilities.json — Define Data Roles

Data roles define what fields the user can drag into the visual:

```json
{
  "dataRoles": [
    {"displayName": "Category", "name": "category", "kind": "Grouping"},
    {"displayName": "Values", "name": "values", "kind": "Measure"}
  ],
  "dataViewMappings": [{
    "categorical": {
      "categories": {"for": {"in": "category"}},
      "values": {"select": [{"bind": {"to": "values"}}]}
    }
  }]
}
```

For network/graph visuals use multiple grouping roles:
```json
{
  "dataRoles": [
    {"displayName": "Source", "name": "source", "kind": "Grouping"},
    {"displayName": "Target", "name": "target", "kind": "Grouping"},
    {"displayName": "Weight", "name": "weight", "kind": "Measure"}
  ]
}
```

### visual.ts — Rendering Pattern

```typescript
import powerbi from "powerbi-visuals-api";
import * as d3 from "d3";

export class Visual implements powerbi.extensibility.visual.IVisual {
    private svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;

    constructor(options: powerbi.extensibility.visual.VisualConstructorOptions) {
        this.svg = d3.select(options.element).append("svg");
    }

    public update(options: powerbi.extensibility.visual.VisualUpdateOptions) {
        const dataView = options.dataViews?.[0];
        if (!dataView?.categorical) return;

        const width = options.viewport.width;
        const height = options.viewport.height;
        this.svg.attr("viewBox", `0 0 ${width} ${height}`);

        // Extract data from dataView.categorical.categories/values
        // Render with D3.js
    }

    public getFormattingModel(): powerbi.visuals.FormattingModel {
        return { cards: [] };
    }
}
```

### pbiviz.json — Required Fields
These fields MUST be filled in or the build will fail:
```json
{
  "visual": {
    "displayName": "My Visual",
    "description": "What it does",
    "supportUrl": "https://github.com/...",
    "gitHubUrl": "https://github.com/..."
  },
  "author": {"name": "Author Name", "email": "email@example.com"}
}
```

### Build & Package

```bash
npx pbiviz package
```

Output: `dist/<guid>.<version>.pbiviz`

### Lint Rules
- Do NOT use `.html()` — use `.text()` instead (security rule: `powerbi-visuals/no-implied-inner-html`)
- All fields in pbiviz.json must be non-empty

### Import into Power BI
1. The `.pbiviz` file must be imported manually via Power BI UI: Edit report → Visualizations → `...` → "Import a visual from a file"
2. Once imported, the visual's GUID is registered in `publicCustomVisuals` in `report.json`
3. Then you can add instances via `add_visual_to_page` using the GUID as `visualType`

### Applying the User's Style Guide to Custom Visuals
When building the visual's rendering code, always use colors from the user's style guide. If no guide exists, use sensible defaults. Apply these patterns:

```typescript
// Read colors from the style guide or use defaults
const COLORS = {
    primary: "#0078D4",    // Override with user's primaryColor
    secondary: "#E66C37",  // Override with user's dataColors[1]
    background: "#FFFFFF", // Override with user's backgroundColor
    text: "#1F1F1F",       // Override with user's textColor
};
```

### Common Visual Types to Build

| Type | D3 Approach | Data Roles |
|------|-------------|------------|
| Network graph | `d3.forceSimulation` | source, target, weight |
| Sankey diagram | `d3-sankey` | source, target, value |
| Timeline | `d3.scaleTime` + rects | category, start, end |
| Gauge/speedometer | `d3.arc` | value, target |
| Sparkline card | `d3.line` in small viewport | category, value |
| Heatmap | `d3.scaleSequential` + rects | row, column, value |
