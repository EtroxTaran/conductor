"""Tests for documentation discovery exclusion patterns.

Regression test: Verifies that archive/legacy directories are excluded
from documentation scanning to prevent context pollution.
"""

import tempfile
from pathlib import Path

from orchestrator.validators.documentation_discovery import DocumentationScanner


class TestDocumentationScannerExclusions:
    """Test exclusion patterns in DocumentationScanner."""

    def test_default_exclude_patterns_exist(self):
        """DEFAULT_EXCLUDE_PATTERNS contains expected patterns."""
        patterns = DocumentationScanner.DEFAULT_EXCLUDE_PATTERNS
        assert "legacy_archive*" in patterns
        assert "archive" in patterns
        assert "deprecated" in patterns
        assert "node_modules" in patterns
        assert ".git" in patterns

    def test_exclude_legacy_archive_directory(self):
        """legacy_archive* directories are excluded by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create docs with a legacy archive
            docs_dir = project_dir / "docs"
            docs_dir.mkdir()

            # Active doc
            active = docs_dir / "overview.md"
            active.write_text("# Overview\nActive documentation.")

            # Legacy archive (should be excluded)
            legacy = docs_dir / "legacy_archive_20260127"
            legacy.mkdir()
            for i in range(5):
                (legacy / f"old_doc_{i}.md").write_text(f"# Old Doc {i}\nSuperseded content.")

            scanner = DocumentationScanner()
            result = scanner.discover(project_dir)

            # Should only find the active doc, not the 5 legacy ones
            assert len(result.documents) == 1
            assert result.documents[0].title == "Overview"

    def test_exclude_archive_directory(self):
        """'archive' directories are excluded by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            docs_dir = project_dir / "docs"
            docs_dir.mkdir()

            (docs_dir / "readme.md").write_text("# Readme\nCurrent docs.")

            archive = docs_dir / "archive"
            archive.mkdir()
            (archive / "old.md").write_text("# Old\nArchived.")

            scanner = DocumentationScanner()
            result = scanner.discover(project_dir)

            assert len(result.documents) == 1
            assert result.documents[0].title == "Readme"

    def test_exclude_deprecated_directory(self):
        """'deprecated' directories are excluded by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            docs_dir = project_dir / "docs"
            docs_dir.mkdir()

            (docs_dir / "current.md").write_text("# Current\nActive.")

            deprecated = docs_dir / "deprecated"
            deprecated.mkdir()
            (deprecated / "removed.md").write_text("# Removed\nDeprecated.")

            scanner = DocumentationScanner()
            result = scanner.discover(project_dir)

            assert len(result.documents) == 1

    def test_custom_exclude_patterns_override_defaults(self):
        """Custom exclude patterns replace defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            docs_dir = project_dir / "docs"
            docs_dir.mkdir()

            (docs_dir / "readme.md").write_text("# Readme\nMain.")

            # Create dir matching custom pattern
            custom_excluded = docs_dir / "drafts"
            custom_excluded.mkdir()
            (custom_excluded / "draft.md").write_text("# Draft\nWIP.")

            # Create dir matching default pattern (should NOT be excluded with custom)
            archive = docs_dir / "archive"
            archive.mkdir()
            (archive / "old.md").write_text("# Old\nArchived.")

            scanner = DocumentationScanner(exclude_patterns=["drafts"])
            result = scanner.discover(project_dir)

            # "drafts" excluded, "archive" NOT excluded (custom replaces defaults)
            paths = [str(d.path) for d in result.documents]
            assert len(result.documents) == 2
            assert any("old.md" in p for p in paths)
            assert not any("draft.md" in p for p in paths)

    def test_empty_exclude_patterns_excludes_nothing(self):
        """Empty list means no exclusions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            docs_dir = project_dir / "docs"
            docs_dir.mkdir()

            (docs_dir / "readme.md").write_text("# Readme")

            archive = docs_dir / "archive"
            archive.mkdir()
            (archive / "old.md").write_text("# Old")

            scanner = DocumentationScanner(exclude_patterns=[])
            result = scanner.discover(project_dir)

            # Both files found
            assert len(result.documents) == 2

    def test_fnmatch_glob_pattern(self):
        """Glob patterns work (e.g., legacy_archive*)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            docs_dir = project_dir / "docs"
            docs_dir.mkdir()

            (docs_dir / "readme.md").write_text("# Readme")

            # Multiple legacy archive dirs
            for suffix in ["_20260101", "_20260127", "_backup"]:
                d = docs_dir / f"legacy_archive{suffix}"
                d.mkdir()
                (d / "doc.md").write_text(f"# Legacy {suffix}")

            scanner = DocumentationScanner()
            result = scanner.discover(project_dir)

            # Only readme, all legacy_archive* excluded
            assert len(result.documents) == 1
            assert result.documents[0].title == "Readme"
