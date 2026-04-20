from __future__ import annotations

from typing import Any

from src.models.schemas import DiffEntry, DiffResult, ReportDefinition


class DiffEngine:
    def _recursive_diff(self, before: Any, after: Any, path: str, changes: list[DiffEntry]) -> None:
        if type(before) != type(after):
            changes.append(DiffEntry(path=path, before=before, after=after))
            return

        if isinstance(before, dict):
            keys = sorted(set(before) | set(after))
            for key in keys:
                self._recursive_diff(before.get(key), after.get(key), f"{path}/{key}" if path else f"/{key}", changes)
            return

        if isinstance(before, list):
            max_len = max(len(before), len(after))
            for idx in range(max_len):
                b = before[idx] if idx < len(before) else None
                a = after[idx] if idx < len(after) else None
                self._recursive_diff(b, a, f"{path}/{idx}" if path else f"/{idx}", changes)
            return

        if before != after:
            changes.append(DiffEntry(path=path or "/", before=before, after=after))

    def diff_reports(self, before: ReportDefinition, after: ReportDefinition) -> DiffResult:
        changes: list[DiffEntry] = []
        self._recursive_diff(before.model_dump(mode="json"), after.model_dump(mode="json"), "", changes)
        changed_parts = sorted({c.path.split("/")[1] for c in changes if c.path.count("/") >= 1})
        return DiffResult(changed_parts=changed_parts, field_changes=changes, summary=f"{len(changes)} JSON-pointer changes detected")

    def diff_parts(self, before_definition: dict[str, Any], after_definition: dict[str, Any]) -> DiffResult:
        changed: list[DiffEntry] = []
        self._recursive_diff(before_definition, after_definition, "", changed)
        return DiffResult(changed_parts=sorted({c.path.split("/")[1] for c in changed if c.path.count("/") >= 1}), field_changes=changed, summary=f"{len(changed)} definition-part differences")
