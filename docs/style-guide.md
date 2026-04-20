# Style Guide Reference

The Power BI Creator Skill uses a JSON-based style guide to enforce consistent report styling. This document describes every field, how data colors work, how category detection operates, and the layout rules the engine enforces.

## File Format

A style guide is a JSON object with the following top-level sections:

```json
{
  "dataColors": [...],
  "backgrounds": {...},
  "categoryColors": {...},
  "layoutRules": {...}
}
```

All sections are optional — the engine applies only the sections present.

---

## `dataColors`

An ordered array of hex color strings that define the report's primary palette.

```json
"dataColors": [
  "#E8734A",
  "#D4A27F",
  "#C9CBA3",
  "#7A9E7E",
  "#3C6E71",
  "#284B63",
  "#1A1A2E",
  "#F2E8CF",
  "#BC6C25",
  "#606C38"
]
```

### How data colors work

1. When a style guide with `dataColors` is applied, the engine **injects a Power BI custom theme** into the report's `StaticResources/RegisteredResources/` folder.
2. The custom theme sets the `dataColors` array in the theme JSON, which Power BI uses as the default palette for all chart series.
3. Charts with **category or series fields** automatically pick up colors from this palette in order.
4. **Single-series charts** (e.g., a KPI card) can be individually colored via `objects.dataPoint` with a direct fill color instead of relying on the theme.

### Theme injection details

The injected theme file has this structure:

```json
{
  "name": "CustomStyleGuideTheme",
  "dataColors": ["#E8734A", "#D4A27F", ...],
  "background": "#FFFFFF",
  "foreground": "#1A1A2E",
  "tableAccent": "#E8734A"
}
```

It is registered in the report definition under:
- `themeCollection` with `type: "RegisteredResources"`
- `resourcePackages` with `type: "CustomTheme"`

---

## `backgrounds`

Controls page and visual background fills.

```json
"backgrounds": {
  "page": {
    "color": "#FFFFFF",
    "transparency": 0
  },
  "visual": {
    "color": "#FFFFFF",
    "transparency": 100
  }
}
```

| Field | Type | Description |
|---|---|---|
| `page.color` | hex string | Page background fill color |
| `page.transparency` | integer (0–100) | 0 = fully opaque, 100 = fully transparent |
| `visual.color` | hex string | Default visual container background |
| `visual.transparency` | integer (0–100) | Visual background transparency |

---

## `categoryColors`

A mapping from **dimension values** to specific colors. Used for deterministic coloring of known categories (e.g., status fields, regions).

```json
"categoryColors": {
  "Active": "#7A9E7E",
  "Inactive": "#BC6C25",
  "Pending": "#D4A27F",
  "Completed": "#3C6E71",
  "Cancelled": "#E8734A"
}
```

### How category detection works

1. When the style engine encounters a visual with a **category axis** or **legend field**, it inspects the field's known values.
2. If any value matches a key in `categoryColors`, the engine applies the corresponding color via `objects.dataPoint` conditions.
3. Matching is **case-insensitive** — `"active"`, `"Active"`, and `"ACTIVE"` all match.
4. Values not found in the map fall back to the `dataColors` palette in order.
5. Category colors take precedence over theme data colors for matched values.

---

## `layoutRules`

Defines spacing and positioning constraints that the validation engine enforces.

```json
"layoutRules": {
  "gap": 20,
  "margin": 20,
  "preventOverlaps": true
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `gap` | integer (px) | 20 | Minimum space between adjacent visuals, both horizontal and vertical |
| `margin` | integer (px) | 20 | Minimum space between any visual edge and the page boundary |
| `preventOverlaps` | boolean | `true` | When `true`, the validation engine blocks any write that would create overlapping visuals |

### Layout enforcement

- The engine checks **every visual pair** on a page for overlap after any add/move/resize operation.
- If `preventOverlaps` is `true` and an overlap is detected, the operation is **rejected** with an error listing the conflicting visuals.
- Gap enforcement is advisory during `dry_run` and strict during actual writes.
- The `rearrange_page_visuals` tool can automatically fix spacing issues by redistributing visuals within the page bounds.

---

## Complete Example

```json
{
  "dataColors": [
    "#E8734A",
    "#D4A27F",
    "#C9CBA3",
    "#7A9E7E",
    "#3C6E71",
    "#284B63",
    "#1A1A2E",
    "#F2E8CF",
    "#BC6C25",
    "#606C38"
  ],
  "backgrounds": {
    "page": {
      "color": "#FFFFFF",
      "transparency": 0
    },
    "visual": {
      "color": "#FFFFFF",
      "transparency": 100
    }
  },
  "categoryColors": {
    "Active": "#7A9E7E",
    "Inactive": "#BC6C25",
    "Pending": "#D4A27F",
    "Completed": "#3C6E71",
    "Cancelled": "#E8734A"
  },
  "layoutRules": {
    "gap": 20,
    "margin": 20,
    "preventOverlaps": true
  }
}
```

## Bundled Style Guides

| File | Description |
|---|---|
| `examples/style_guide.example.json` | Blank template with default Power BI colors; copy and customise with your brand |
| `examples/style_guide.enterprise.json` | Corporate blue palette with stricter layout rules |

Use `get_default_style_guide()` to see which guide is currently active, and `set_default_style_guide(style_guide)` to change it at runtime.
