from __future__ import annotations

from src.mcp_tools import tools

try:
    from fastmcp import FastMCP
except ImportError as exc:
    raise RuntimeError("fastmcp must be installed to run the MCP server") from exc

mcp = FastMCP("powerbi-design-modernization-server")

mcp.tool()(tools.list_workspaces)
mcp.tool()(tools.list_reports)
mcp.tool()(tools.get_report_metadata)
mcp.tool()(tools.analyze_report_structure)
mcp.tool()(tools.get_report_definition)
mcp.tool()(tools.get_report_pages)
mcp.tool()(tools.get_page_visuals)
mcp.tool()(tools.get_report_assets)
mcp.tool()(tools.apply_style_guide)
mcp.tool()(tools.patch_report_properties)
mcp.tool()(tools.patch_page_properties)
mcp.tool()(tools.patch_visual_properties)
mcp.tool()(tools.replace_theme_resource)
mcp.tool()(tools.validate_report_definition)
mcp.tool()(tools.preview_changes)
mcp.tool()(tools.diff_report_definition)
mcp.tool()(tools.update_report_definition)
mcp.tool()(tools.backup_report_definition)
mcp.tool()(tools.score_modernization_readiness)
mcp.tool()(tools.bulk_apply_style_guide)
mcp.tool()(tools.extract_style_guide_from_report)
mcp.tool()(tools.add_visual_to_page)
mcp.tool()(tools.rearrange_page_visuals)
mcp.tool()(tools.add_image_visual)
mcp.tool()(tools.get_default_style_guide)
mcp.tool()(tools.set_default_style_guide)
mcp.tool()(tools.get_audit_log)
mcp.tool()(tools.list_backups)
mcp.tool()(tools.restore_report_definition)
mcp.tool()(tools.apply_full_style)
mcp.tool()(tools.add_page)
mcp.tool()(tools.reorder_pages)
mcp.tool()(tools.inject_custom_theme)
mcp.tool()(tools.apply_conditional_format)


if __name__ == "__main__":
    mcp.run()
