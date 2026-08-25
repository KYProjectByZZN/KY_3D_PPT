from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ppt_generator.app_paths import (
    app_data_root,
    copy_legacy_file_if_missing,
    project_ai_candidates_root,
    project_far_assets_root,
)
from ppt_generator.project import PptProject
from ppt_generator.project_session import ProjectStateTracker


class AppPathAndSessionTests(unittest.TestCase):
    def test_environment_root_and_project_scoped_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"KY_PPT_APP_DATA_ROOT": temp_dir}):
                root = Path(temp_dir).resolve()
                self.assertEqual(app_data_root(), root)
                self.assertEqual(
                    project_ai_candidates_root("project/01"),
                    root / "data" / "projects" / "project_01" / "ai_candidates",
                )
                self.assertEqual(
                    project_far_assets_root("project/01"),
                    root / "data" / "projects" / "project_01" / "far_assets",
                )

    def test_legacy_copy_never_overwrites_or_removes_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "legacy.json"
            destination = root / "new" / "store.json"
            source.write_text('{"legacy": true}', encoding="utf-8")
            self.assertTrue(copy_legacy_file_if_missing(source, destination))
            self.assertTrue(source.is_file())
            self.assertEqual(destination.read_text(encoding="utf-8"), '{"legacy": true}')
            destination.write_text('{"new": true}', encoding="utf-8")
            self.assertFalse(copy_legacy_file_if_missing(source, destination))
            self.assertEqual(destination.read_text(encoding="utf-8"), '{"new": true}')

    def test_project_state_tracker_detects_and_clears_changes(self) -> None:
        project = PptProject(project_name="初始")
        tracker = ProjectStateTracker()
        tracker.mark_clean(project)
        self.assertFalse(tracker.is_dirty(project))
        project.project_name = "已修改"
        self.assertTrue(tracker.is_dirty(project))
        tracker.mark_clean(project)
        self.assertFalse(tracker.is_dirty(project))


if __name__ == "__main__":
    unittest.main()
