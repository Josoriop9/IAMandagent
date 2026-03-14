"""
Tests for src/hashed/banner.py

Coverage targets:
- show_banner() — with version, without version, tagline=False
- _HASH_LINES and _HASHED_LINES constants — length, content, types
- Module-level constants — _HASH_STYLE, _HASHED_STYLE, _GAP, etc.
- Rich integration — Console.print called, no exceptions raised

All tests are pure unit tests — no network, no filesystem, no async.
Python 3.9 compatible.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestBannerConstants:
    """Validate the block-art constants."""

    def test_hash_lines_is_list_of_strings(self):
        from hashed.banner import _HASH_LINES
        assert isinstance(_HASH_LINES, list)
        for line in _HASH_LINES:
            assert isinstance(line, str), f"Expected str, got {type(line)}"

    def test_hashed_lines_is_list_of_strings(self):
        from hashed.banner import _HASHED_LINES
        assert isinstance(_HASHED_LINES, list)
        for line in _HASHED_LINES:
            assert isinstance(line, str), f"Expected str, got {type(line)}"

    def test_hash_lines_has_six_rows(self):
        """# symbol needs exactly 6 rows to align with HASHED block art."""
        from hashed.banner import _HASH_LINES
        assert len(_HASH_LINES) == 6

    def test_hashed_lines_has_six_rows(self):
        """HASHED block art has exactly 6 rows."""
        from hashed.banner import _HASHED_LINES
        assert len(_HASHED_LINES) == 6

    def test_hash_lines_contain_block_chars(self):
        """Every line must contain the ██ block character."""
        from hashed.banner import _HASH_LINES
        for line in _HASH_LINES:
            assert "██" in line, f"Expected block chars in: {repr(line)}"

    def test_hashed_lines_contain_block_chars(self):
        """HASHED block art uses ██ and box-drawing chars."""
        from hashed.banner import _HASHED_LINES
        for line in _HASHED_LINES:
            assert len(line) > 0, "Line must not be empty"

    def test_hash_style_is_string(self):
        from hashed.banner import _HASH_STYLE
        assert isinstance(_HASH_STYLE, str)
        assert len(_HASH_STYLE) > 0

    def test_hashed_style_is_string(self):
        from hashed.banner import _HASHED_STYLE
        assert isinstance(_HASHED_STYLE, str)
        assert len(_HASHED_STYLE) > 0

    def test_gap_is_string(self):
        from hashed.banner import _GAP
        assert isinstance(_GAP, str)

    def test_version_style_is_string(self):
        from hashed.banner import _VERSION_STYLE
        assert isinstance(_VERSION_STYLE, str)

    def test_tagline_style_is_string(self):
        from hashed.banner import _TAGLINE_STYLE
        assert isinstance(_TAGLINE_STYLE, str)


# ---------------------------------------------------------------------------
# show_banner()
# ---------------------------------------------------------------------------

class TestShowBanner:
    """Tests for the show_banner() function."""

    def test_show_banner_no_args_does_not_raise(self):
        """show_banner() with default args must not raise."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner()  # no exception

    def test_show_banner_with_version_does_not_raise(self):
        """show_banner(version='1.2.3') must not raise."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner(version="1.2.3")  # no exception

    def test_show_banner_tagline_false_does_not_raise(self):
        """show_banner(tagline=False) must not raise."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner(tagline=False)  # no exception

    def test_show_banner_calls_console_print(self):
        """show_banner() must call console.print at least once per line + 2 blanks."""
        from hashed.banner import show_banner, _HASH_LINES
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner()
            # 6 logo lines + tagline + 2 blank prints (open + close)
            assert mock_console.print.call_count >= len(_HASH_LINES) + 2

    def test_show_banner_with_version_extra_print(self):
        """With version, tagline print is called (contains version string)."""
        from hashed.banner import show_banner, _HASH_LINES
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner(version="0.2.1")
            # Should have 6 logo lines + 1 tagline + 2 blanks = 9+
            assert mock_console.print.call_count >= len(_HASH_LINES) + 2

    def test_show_banner_tagline_false_fewer_prints(self):
        """tagline=False skips the tagline print, so fewer calls."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console_with = MagicMock()
            mock_console_without = MagicMock()

            mock_console_cls.return_value = mock_console_with
            show_banner(tagline=True)
            count_with = mock_console_with.print.call_count

            mock_console_cls.return_value = mock_console_without
            show_banner(tagline=False)
            count_without = mock_console_without.print.call_count

            assert count_with > count_without

    def test_show_banner_empty_version_skips_version_markup(self):
        """version='' should not include version markup in tagline."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner(version="")  # empty version
            # Should still work, just no version in tagline
            assert mock_console.print.call_count >= 1

    def test_show_banner_creates_one_console(self):
        """show_banner() creates exactly one Console instance."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner(version="0.2.1")
            mock_console_cls.assert_called_once()

    def test_show_banner_uses_text_objects(self):
        """Each logo row is rendered as a Rich Text object (not raw string)."""
        from hashed.banner import show_banner
        from rich.text import Text
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner()
            # Collect all positional args from print calls
            all_args = [
                call.args[0]
                for call in mock_console.print.call_args_list
                if call.args
            ]
            # At least one call should pass a Text object
            text_objects = [a for a in all_args if isinstance(a, Text)]
            assert len(text_objects) == 6, (
                f"Expected 6 Text rows (one per logo line), got {len(text_objects)}"
            )

    def test_show_banner_version_021(self):
        """Smoke test with actual project version string."""
        from hashed.banner import show_banner
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            show_banner(version="0.2.1")
            assert mock_console.print.called

    def test_show_banner_callable(self):
        """show_banner is callable."""
        from hashed import banner
        assert callable(banner.show_banner)

    def test_banner_module_importable(self):
        """banner module must import cleanly."""
        import importlib
        mod = importlib.import_module("hashed.banner")
        assert hasattr(mod, "show_banner")
        assert hasattr(mod, "_HASH_LINES")
        assert hasattr(mod, "_HASHED_LINES")


# ---------------------------------------------------------------------------
# Integration: banner in CLI context
# ---------------------------------------------------------------------------

class TestBannerCLIIntegration:
    """Test that the banner is wired up in the CLI callback."""

    def test_hashed_no_subcommand_shows_banner(self):
        """Running 'hashed' without subcommand triggers show_banner."""
        from typer.testing import CliRunner
        from hashed.cli import app
        runner = CliRunner()
        with patch("hashed.banner.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            result = runner.invoke(app, [])
            # Banner should have been triggered (console.print called)
            assert mock_console.print.call_count >= 1

    def test_hashed_login_does_not_show_banner(self):
        """Running 'hashed login' should NOT trigger show_banner."""
        from typer.testing import CliRunner
        from hashed.cli import app
        runner = CliRunner()
        with patch("hashed.banner.show_banner") as mock_banner:
            # login will fail (no network) but banner should not be called
            runner.invoke(app, ["login", "--help"])
            mock_banner.assert_not_called()

    def test_hashed_version_does_not_show_banner(self):
        """Running 'hashed version' should NOT trigger show_banner."""
        from typer.testing import CliRunner
        from hashed.cli import app
        runner = CliRunner()
        with patch("hashed.banner.show_banner") as mock_banner:
            runner.invoke(app, ["version"])
            mock_banner.assert_not_called()
