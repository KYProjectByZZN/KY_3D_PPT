"""Stable filesystem boundaries for source code, user data, cache and logs."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAMESPACE = Path("KY_Project") / "PPT_Generator"


def app_data_root() -> Path:
    """Return the writable application root without creating it."""
    configured = os.environ.get("KY_PPT_APP_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return (base / APP_NAMESPACE).resolve()


def data_root() -> Path:
    return app_data_root() / "data"


def cache_root() -> Path:
    return app_data_root() / "cache"


def logs_root() -> Path:
    return app_data_root() / "logs"


def preview_cache_root() -> Path:
    return cache_root() / "previews"


def auto_solution_store_path() -> Path:
    return data_root() / "auto_solution" / "auto_solution_v2_store.json"


def _safe_project_id(project_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", project_id.strip())
    normalized = normalized.strip("._")
    return normalized or "_unbound"


def project_data_root(project_id: str) -> Path:
    return data_root() / "projects" / _safe_project_id(project_id)


def project_ai_candidates_root(project_id: str) -> Path:
    return project_data_root(project_id) / "ai_candidates"


def project_far_assets_root(project_id: str) -> Path:
    return project_data_root(project_id) / "far_assets"


def copy_legacy_file_if_missing(source: Path, destination: Path) -> bool:
    """Copy legacy state atomically, preserving the source and any existing target."""
    if destination.exists() or not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".migrate", dir=destination.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        if destination.exists():
            return False
        os.replace(temporary, destination)
        return True
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "PROJECT_ROOT",
    "app_data_root",
    "auto_solution_store_path",
    "cache_root",
    "copy_legacy_file_if_missing",
    "data_root",
    "logs_root",
    "preview_cache_root",
    "project_ai_candidates_root",
    "project_data_root",
    "project_far_assets_root",
]
