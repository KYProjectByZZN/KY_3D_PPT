"""UI-independent dirty-state tracking for one project session."""

from __future__ import annotations

import hashlib
import json

from .project import PptProject


def project_fingerprint(project: PptProject) -> str:
    payload = json.dumps(
        project.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ProjectStateTracker:
    def __init__(self) -> None:
        self._clean_fingerprint: str | None = None

    def mark_clean(self, project: PptProject) -> None:
        self._clean_fingerprint = project_fingerprint(project)

    def is_dirty(self, project: PptProject) -> bool:
        return self._clean_fingerprint != project_fingerprint(project)


__all__ = ["ProjectStateTracker", "project_fingerprint"]
