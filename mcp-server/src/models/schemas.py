from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ReportFormat(str, Enum):
    PBIR = "PBIR"
    PBIR_LEGACY = "PBIR-Legacy"
    UNKNOWN = "Unknown"


class MCPErrorCode(str, Enum):
    UNSUPPORTED_REPORT_FORMAT = "unsupported_report_format"
    EXTERNAL_EDITING_NOT_SUPPORTED = "external_editing_not_supported"
    VALIDATION_FAILED = "validation_failed"
    THROTTLED_RETRYABLE = "throttled_retryable"
    ASYNC_OPERATION_PENDING = "async_operation_pending"
    CORRUPTED_PAYLOAD_RISK = "corrupted_payload_risk"
    TRANSIENT_UPSTREAM_FAILURE = "transient_upstream_failure"
    AUTH_FAILED = "auth_failed"
    FORBIDDEN_SCOPE = "forbidden_scope"


class WarningItem(BaseModel):
    severity: Severity
    code: str
    message: str
    remediation: str | None = None


class ToolResponse(BaseModel):
    success: bool
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[WarningItem] = Field(default_factory=list)
    blockers: list[WarningItem] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ReportPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    path: str
    content_type: str
    payload: dict[str, Any] | list[Any] | str
    payload_type: str | None = None  # "InlineBase64" or None — needed for re-encoding on writeback


class VisualDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str | None = None
    visual_type: str
    page_id: str
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    z_order: int | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    objects: dict[str, Any] = Field(default_factory=dict)  # visual-level formatting (data colors, axes)
    raw: dict[str, Any] = Field(default_factory=dict)


class PageDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    display_name: str | None = None
    order: int = 0
    visuals: list[VisualDefinition] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class BookmarkDefinition(BaseModel):
    id: str
    name: str
    raw: dict[str, Any] = Field(default_factory=dict)


class StaticResource(BaseModel):
    name: str
    resource_type: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ReportDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_id: str
    workspace_id: str
    format: ReportFormat = ReportFormat.UNKNOWN
    metadata: dict[str, Any] = Field(default_factory=dict)
    parts: list[ReportPart] = Field(default_factory=list)
    pages: list[PageDefinition] = Field(default_factory=list)
    bookmarks: list[BookmarkDefinition] = Field(default_factory=list)
    static_resources: list[StaticResource] = Field(default_factory=list)
    unsupported_artifacts: list[str] = Field(default_factory=list)


class StyleGuideTheme(BaseModel):
    primary_color: str = Field(alias="primaryColor")
    background_color: str = Field(alias="backgroundColor")
    text_color: str = Field(alias="textColor")
    data_colors: list[str] = Field(default_factory=list, alias="dataColors")


class StyleGuideTypography(BaseModel):
    title_font_family: str = Field(alias="titleFontFamily")
    body_font_family: str = Field(alias="bodyFontFamily")
    title_font_size: int = Field(alias="titleFontSize", ge=8, le=72)
    body_font_size: int = Field(alias="bodyFontSize", ge=6, le=48)


class StyleGuideLayout(BaseModel):
    page_padding: int = Field(alias="pagePadding", ge=0, le=200)
    visual_spacing: int = Field(alias="visualSpacing", ge=0, le=200)
    corner_radius: int = Field(alias="cornerRadius", ge=0, le=100)


class StyleGuideRules(BaseModel):
    max_visuals_per_page: int = Field(alias="maxVisualsPerPage", ge=1, le=100)
    allow_custom_visuals: bool = Field(alias="allowCustomVisuals", default=True)
    enforce_top_row_kpis: bool = Field(alias="enforceTopRowKpis", default=False)


class StyleGuide(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    theme: StyleGuideTheme
    typography: StyleGuideTypography
    layout: StyleGuideLayout
    rules: StyleGuideRules
    visual_rules: dict[str, dict[str, Any]] = Field(default_factory=dict, alias="visualRules")


class TransformationChange(BaseModel):
    target: str
    path: str
    old_value: Any
    new_value: Any
    risk_note: str | None = None


class TransformationPlan(BaseModel):
    report_id: str
    workspace_id: str
    dry_run: bool = True
    changes: list[TransformationChange] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)


class ValidationResult(BaseModel):
    valid: bool
    issues: list[WarningItem] = Field(default_factory=list)


class DiffEntry(BaseModel):
    path: str
    before: Any
    after: Any


class DiffResult(BaseModel):
    changed_parts: list[str] = Field(default_factory=list)
    field_changes: list[DiffEntry] = Field(default_factory=list)
    summary: str


class LayoutConfig(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    margin: int = Field(default=20, alias="margin", ge=0, le=200)
    gap: int = Field(default=20, alias="gap", ge=0, le=200)
    page_width: int = Field(default=1280, alias="pageWidth")
    auto_height: bool = Field(default=True, alias="autoHeight")


class ModernizationScore(BaseModel):
    score: int = Field(ge=0, le=100)
    classification: str
    reasons: list[str]
    suggested_next_action: str
