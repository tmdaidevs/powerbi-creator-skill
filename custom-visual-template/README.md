# Custom Visual Template

Starter template for building Power BI custom visuals with D3.js.

## Usage

```bash
# 1. Copy this template
cp -r custom-visual-template/ my-visual/
cd my-visual/

# 2. Or scaffold with pbiviz (recommended)
pbiviz new my-visual --force
cd my-visual
npm install d3@7 --save
npm install @types/d3@7 --save-dev

# 3. Edit capabilities.json for your data roles
# 4. Edit src/visual.ts for your rendering logic
# 5. Edit pbiviz.json with your visual name and author info

# 6. Build
npx pbiviz package

# 7. Import the .pbiviz file in Power BI UI
```

## Files to Edit

| File | Purpose |
|------|---------|
| `capabilities.json` | Define what data fields the visual accepts |
| `pbiviz.json` | Visual name, GUID, author, description |
| `src/visual.ts` | D3.js rendering logic |
| `style/visual.less` | CSS styling |

## Tips

- Use `d3.forceSimulation` for network graphs
- Use `d3-sankey` for flow diagrams
- Use `d3.scaleTime` for timelines
- Always use `.text()` not `.html()` to avoid lint errors
- Read data from `options.dataViews[0].categorical`
- Use `options.viewport.width/height` for responsive sizing
