from __future__ import annotations

import base64
import json
from typing import Any

from src.models.schemas import (
    BookmarkDefinition,
    PageDefinition,
    ReportDefinition,
    ReportFormat,
    ReportPart,
    StaticResource,
    VisualDefinition,
)


class ReportDefinitionParser:
    @staticmethod
    def _decode_payload(raw_payload: Any, payload_type: str | None = None) -> Any:
        """Decode a part payload, handling InlineBase64-encoded JSON."""
        if payload_type == "InlineBase64" and isinstance(raw_payload, str):
            try:
                decoded = base64.b64decode(raw_payload).decode("utf-8")
                return json.loads(decoded)
            except (ValueError, json.JSONDecodeError):
                return raw_payload
        if isinstance(raw_payload, dict):
            return raw_payload
        return raw_payload

    def _normalize_visual_properties(self, visual_raw: dict[str, Any]) -> dict[str, Any]:
        config = visual_raw.get("config", {})
        if isinstance(config, str):
            try:
                return json.loads(config)
            except json.JSONDecodeError:
                return {"rawConfig": config, "parseError": "visual_config_not_json"}
        if isinstance(config, dict):
            return config
        return {"rawConfig": config}

    def parse(self, workspace_id: str, report_id: str, payload: dict[str, Any]) -> ReportDefinition:
        definition = payload.get("definition", {})
        parts_raw = definition.get("parts", [])
        parts = [
            ReportPart(
                name=p.get("name", "unknown"),
                path=p.get("path", p.get("name", "unknown")),
                content_type=p.get("contentType", "application/json"),
                payload=self._decode_payload(p.get("payload", {}), p.get("payloadType")),
                payload_type=p.get("payloadType"),
            )
            for p in parts_raw
        ]

        format_value = definition.get("format", "Unknown")
        report_format = ReportFormat(format_value) if format_value in ReportFormat._value2member_map_ else ReportFormat.UNKNOWN

        pages: list[PageDefinition] = []
        bookmarks: list[BookmarkDefinition] = []
        static_resources: list[StaticResource] = []
        unsupported_artifacts: list[str] = []

        # PBIR uses separate parts for pages and visuals:
        #   definition/pages/{page_name}/page.json
        #   definition/pages/{page_name}/visuals/{visual_name}/visual.json
        # Collect visuals keyed by parent page folder, then assemble pages.

        page_parts: dict[str, tuple[int, ReportPart]] = {}
        visual_parts: dict[str, list[ReportPart]] = {}

        for idx, part in enumerate(parts):
            path_lower = part.path.lower()

            # Detect PBIR page parts (path ends with /page.json)
            if path_lower.endswith("/page.json") and "/pages/" in path_lower and isinstance(part.payload, dict):
                # Extract the page folder key, e.g. "definition/pages/page_overview"
                page_folder = part.path.rsplit("/", 1)[0]
                page_parts[page_folder] = (idx, part)
                continue

            # Detect PBIR visual parts (path ends with /visual.json)
            if path_lower.endswith("/visual.json") and "/visuals/" in path_lower and isinstance(part.payload, dict):
                # Extract the parent page folder, e.g. from
                # "definition/pages/page_overview/visuals/bar_chart/visual.json"
                # we need "definition/pages/page_overview"
                segments = part.path.split("/")
                try:
                    visuals_idx = segments.index("visuals")
                    page_folder = "/".join(segments[:visuals_idx])
                except ValueError:
                    page_folder = ""
                visual_parts.setdefault(page_folder, []).append(part)
                continue

            # Legacy flat format: pages embedded with visuals
            if "/pages/" in f"/{path_lower}" and isinstance(part.payload, dict) and "visuals" in part.payload:
                visuals_raw = part.payload.get("visuals", [])
                visuals = []
                for n, v in enumerate(visuals_raw):
                    pos = v.get("position", {})
                    visuals.append(
                        VisualDefinition(
                            id=v.get("id", v.get("name", f"visual_{n}")),
                            name=v.get("name"),
                            visual_type=v.get("type", "unknown"),
                            page_id=part.payload.get("id", part.name),
                            x=pos.get("x"),
                            y=pos.get("y"),
                            width=pos.get("width"),
                            height=pos.get("height"),
                            z_order=pos.get("z"),
                            properties=self._normalize_visual_properties(v),
                            objects=v.get("objects", {}),
                            raw=v,
                        )
                    )
                pages.append(
                    PageDefinition(
                        id=part.payload.get("id", f"page_{idx}"),
                        name=part.payload.get("name", part.name),
                        display_name=part.payload.get("displayName"),
                        order=part.payload.get("ordinal", idx),
                        visuals=visuals,
                        properties={k: v for k, v in part.payload.items() if k != "visuals"},
                        raw=part.payload,
                    )
                )
                continue

            if "bookmark" in path_lower and isinstance(part.payload, dict):
                bookmarks.append(
                    BookmarkDefinition(
                        id=part.payload.get("id", part.name),
                        name=part.payload.get("name", part.name),
                        raw=part.payload,
                    )
                )
                continue

            if any(x in path_lower for x in ("staticresources", "resources", "themes")):
                static_resources.append(
                    StaticResource(name=part.name, resource_type=part.content_type, raw={"path": part.path, "payload": part.payload})
                )

            if any(x in path_lower for x in ("mobilestate", "legacy", "customvisualstate")):
                unsupported_artifacts.append(part.path)

        # Assemble PBIR pages from collected page_parts + visual_parts
        for page_folder, (idx, page_part) in page_parts.items():
            page_payload = page_part.payload
            page_visuals_raw = visual_parts.get(page_folder, [])
            visuals = []
            for n, vp in enumerate(page_visuals_raw):
                position = vp.payload.get("position", {})
                visuals.append(
                    VisualDefinition(
                        id=vp.payload.get("name", vp.path.rsplit("/", 2)[-2] if "/" in vp.path else f"visual_{n}"),
                        name=vp.payload.get("name"),
                        visual_type=vp.payload.get("visual", {}).get("visualType", "unknown"),
                        page_id=page_payload.get("name", page_part.name),
                        x=position.get("x"),
                        y=position.get("y"),
                        width=position.get("width"),
                        height=position.get("height"),
                        z_order=position.get("z"),
                        properties=self._normalize_visual_properties(vp.payload),
                        objects=vp.payload.get("visual", {}).get("objects", {}),
                        raw=vp.payload,
                    )
                )
            pages.append(
                PageDefinition(
                    id=page_payload.get("name", f"page_{idx}"),
                    name=page_payload.get("name", page_part.name),
                    display_name=page_payload.get("displayName"),
                    order=page_payload.get("ordinal", idx),
                    visuals=visuals,
                    properties={k: v for k, v in page_payload.items() if k not in ("visuals", "$schema")},
                    raw=page_payload,
                )
            )

        if not pages:
            unsupported_artifacts.append("missing_pages")

        return ReportDefinition(
            report_id=report_id,
            workspace_id=workspace_id,
            format=report_format,
            metadata=payload.get("metadata", {}),
            parts=parts,
            pages=pages,
            bookmarks=bookmarks,
            static_resources=static_resources,
            unsupported_artifacts=unsupported_artifacts,
        )
