"""Security tests for document converters."""

import os
import tempfile
from pathlib import Path

import pytest

from src.converters.fetcher import DocumentFetcher


@pytest.mark.unit
class TestFilePathSecurity:
    """Test file path security restrictions."""

    @pytest.mark.asyncio
    async def test_default_allowed_path_is_cwd(self) -> None:
        """Test that default allowed path is current working directory."""
        fetcher = DocumentFetcher()

        # Should have CWD as allowed path
        assert len(fetcher.allowed_paths) == 1
        assert fetcher.allowed_paths[0] == str(Path.cwd().resolve())

    @pytest.mark.asyncio
    async def test_custom_allowed_paths(self) -> None:
        """Test custom allowed paths configuration."""
        allowed = ["/tmp", "/var/tmp"]
        fetcher = DocumentFetcher(allowed_paths=allowed)

        # Should have both paths
        assert len(fetcher.allowed_paths) == 2
        assert str(Path("/tmp").resolve()) in fetcher.allowed_paths
        assert str(Path("/var/tmp").resolve()) in fetcher.allowed_paths

    @pytest.mark.asyncio
    async def test_env_var_allowed_paths(self) -> None:
        """Test allowed paths from environment variable."""
        # Save original env var
        original = os.environ.get("MAESTRO_ALLOWED_FILE_PATHS")

        try:
            # Set env var with multiple paths
            separator = ";" if os.name == "nt" else ":"
            os.environ["MAESTRO_ALLOWED_FILE_PATHS"] = f"/tmp{separator}/var/tmp"

            fetcher = DocumentFetcher()

            # Should have both paths from env var
            assert len(fetcher.allowed_paths) >= 2
            assert str(Path("/tmp").resolve()) in fetcher.allowed_paths
            assert str(Path("/var/tmp").resolve()) in fetcher.allowed_paths
        finally:
            # Restore original env var
            if original is None:
                os.environ.pop("MAESTRO_ALLOWED_FILE_PATHS", None)
            else:
                os.environ["MAESTRO_ALLOWED_FILE_PATHS"] = original

    @pytest.mark.asyncio
    async def test_access_denied_outside_allowed_path(self) -> None:
        """Test that access is denied for files outside allowed paths."""
        # Create fetcher with restricted path
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DocumentFetcher(allowed_paths=[tmpdir])

            # Try to access file outside allowed path
            # Use a path that definitely exists but is outside tmpdir
            forbidden_path = (
                "/etc/hosts"
                if os.path.exists("/etc/hosts")
                else "C:\\Windows\\System32\\drivers\\etc\\hosts"
            )

            if os.path.exists(forbidden_path):
                with pytest.raises(PermissionError) as exc_info:
                    await fetcher.fetch(f"file://{forbidden_path}")

                # Check error message
                assert "Access denied" in str(exc_info.value)
                assert "outside allowed directories" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_access_allowed_within_allowed_path(self) -> None:
        """Test that access is allowed for files within allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Create fetcher with this directory allowed
            fetcher = DocumentFetcher(allowed_paths=[tmpdir])

            # Should succeed
            content, metadata = await fetcher.fetch(str(test_file))

            assert content == b"test content"
            assert "content_length" in metadata
            assert "fetched_at" in metadata

    @pytest.mark.asyncio
    async def test_access_allowed_in_subdirectory(self) -> None:
        """Test that access is allowed for files in subdirectories of allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory and file
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            test_file = subdir / "test.txt"
            test_file.write_text("test content")

            # Create fetcher with parent directory allowed
            fetcher = DocumentFetcher(allowed_paths=[tmpdir])

            # Should succeed - subdirectory is within allowed path
            content, metadata = await fetcher.fetch(str(test_file))

            assert content == b"test content"

    @pytest.mark.asyncio
    async def test_symlink_traversal_blocked(self) -> None:
        """Test that symlinks cannot be used to escape allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a symlink pointing outside allowed directory
            link_path = tmpdir_path / "link_to_etc"

            # Only test on Unix-like systems where /etc exists
            if os.path.exists("/etc") and hasattr(os, "symlink"):
                try:
                    os.symlink("/etc", link_path)

                    # Create fetcher with tmpdir allowed
                    fetcher = DocumentFetcher(allowed_paths=[tmpdir])

                    # Try to access through symlink - should be blocked
                    # because resolved path is outside allowed directory
                    with pytest.raises(PermissionError):
                        await fetcher.fetch(str(link_path / "hosts"))
                except OSError:
                    # Skip if we can't create symlinks (permissions, Windows, etc.)
                    pytest.skip("Cannot create symlinks on this system")

    @pytest.mark.asyncio
    async def test_relative_path_resolution(self) -> None:
        """Test that relative paths are resolved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Create fetcher with this directory allowed
            fetcher = DocumentFetcher(allowed_paths=[tmpdir])

            # Change to tmpdir and use relative path
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Should succeed with relative path
                content, metadata = await fetcher.fetch("test.txt")
                assert content == b"test content"
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_file_url_scheme(self) -> None:
        """Test file:// URL scheme handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Create fetcher with this directory allowed
            fetcher = DocumentFetcher(allowed_paths=[tmpdir])

            # Test with file:// scheme
            content, metadata = await fetcher.fetch(f"file://{test_file}")
            assert content == b"test content"

    @pytest.mark.asyncio
    async def test_error_message_includes_allowed_paths(self) -> None:
        """Test that error message includes list of allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DocumentFetcher(allowed_paths=[tmpdir])

            # Try to access forbidden path
            forbidden = (
                "/etc/passwd"
                if os.path.exists("/etc/passwd")
                else "C:\\Windows\\System32\\config\\SAM"
            )

            if os.path.exists(forbidden):
                with pytest.raises(PermissionError) as exc_info:
                    await fetcher.fetch(forbidden)

                # Error should mention allowed paths
                error_msg = str(exc_info.value)
                assert "Allowed paths:" in error_msg
                assert tmpdir in error_msg
                assert "MAESTRO_ALLOWED_FILE_PATHS" in error_msg


@pytest.mark.unit
class TestPathValidation:
    """Test internal path validation logic."""

    def test_is_path_allowed_exact_match(self) -> None:
        """Test path validation for exact directory match."""
        fetcher = DocumentFetcher(allowed_paths=["/tmp"])

        # Exact match should be allowed
        assert fetcher._is_path_allowed(str(Path("/tmp").resolve()))

    def test_is_path_allowed_subdirectory(self) -> None:
        """Test path validation for subdirectories."""
        fetcher = DocumentFetcher(allowed_paths=["/tmp"])

        # Subdirectory should be allowed
        assert fetcher._is_path_allowed(str(Path("/tmp/subdir/file.txt").resolve()))

    def test_is_path_allowed_parent_directory(self) -> None:
        """Test path validation rejects parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()

            # Only allow subdirectory
            fetcher = DocumentFetcher(allowed_paths=[str(subdir)])

            # Parent directory should not be allowed
            assert not fetcher._is_path_allowed(tmpdir)

    def test_is_path_allowed_sibling_directory(self) -> None:
        """Test path validation rejects sibling directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "dir1"
            dir2 = Path(tmpdir) / "dir2"
            dir1.mkdir()
            dir2.mkdir()

            # Only allow dir1
            fetcher = DocumentFetcher(allowed_paths=[str(dir1)])

            # dir2 should not be allowed
            assert not fetcher._is_path_allowed(str(dir2 / "file.txt"))

    def test_is_path_allowed_multiple_allowed_paths(self) -> None:
        """Test path validation with multiple allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "dir1"
            dir2 = Path(tmpdir) / "dir2"
            dir1.mkdir()
            dir2.mkdir()

            # Allow both directories
            fetcher = DocumentFetcher(allowed_paths=[str(dir1), str(dir2)])

            # Both should be allowed (need to resolve paths like the fetcher does)
            assert fetcher._is_path_allowed(str(Path(dir1 / "file.txt").resolve()))
            assert fetcher._is_path_allowed(str(Path(dir2 / "file.txt").resolve()))

            # Parent should not be allowed
            assert not fetcher._is_path_allowed(str(Path(tmpdir).resolve()))


# Made with Bob
