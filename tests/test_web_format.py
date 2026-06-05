from __future__ import annotations

import unittest

from clearink.api.web_format import format_browser_response


class TestWebFormat(unittest.TestCase):
    """Test format_browser_response for safe browser rendering."""

    def test_preserves_display_math(self) -> None:
        """$$...$$ display math delimiters are left untouched."""
        result = format_browser_response("Energy: $$E=mc^2$$")
        self.assertIn("$$E=mc^2$$", result)

    def test_preserves_multiple_display_math_blocks(self) -> None:
        """Multiple disjoint $$...$$ blocks are all preserved."""
        result = format_browser_response(
            "First: $$x^2$$ and second: $$\\int_0^1 f(x)\\,dx$$"
        )
        self.assertIn("$$x^2$$", result)
        self.assertIn("$$\\int_0^1 f(x)\\,dx$$", result)

    def test_preserves_inline_math(self) -> None:
        """$...$ inline math delimiters are left untouched."""
        result = format_browser_response("The variable $x$ is positive.")
        self.assertIn("$x$", result)

    def test_escapes_html_script_tags(self) -> None:
        """<script> tags are HTML-escaped to &lt;script&gt;."""
        result = format_browser_response(
            "Hello <script>alert('xss')</script> world"
        )
        self.assertIn("&lt;script&gt;alert('xss')&lt;/script&gt;", result)
        self.assertNotIn("<script>", result)

    def test_escapes_html_in_mixed_content(self) -> None:
        """HTML tags in non-math, non-code regions are escaped."""
        result = format_browser_response(
            "<b>bold</b> and <i>italic</i>"
        )
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", result)
        self.assertIn("&lt;i&gt;italic&lt;/i&gt;", result)

    def test_code_fence_content_untouched(self) -> None:
        """Content inside ```...``` code fences is NOT HTML-escaped."""
        result = format_browser_response(
            "Outside text\n```html\n<script>alert(1)</script>\n```\nMore text"
        )
        self.assertIn("<script>alert(1)</script>", result)
        self.assertNotIn("&lt;script&gt;", result)

    def test_code_fence_contains_dollar_signs(self) -> None:
        """Dollar signs inside code fences remain literal."""
        result = format_browser_response(
            "```\n$$E=mc^2$$\n```"
        )
        self.assertIn("$$E=mc^2$$", result)

    def test_math_inside_code_fence_untouched(self) -> None:
        """Math delimiters inside code fences pass through unchanged."""
        result = format_browser_response(
            "Text before\n```tex\n$$x^2$$\n```\nText after"
        )
        self.assertIn("$$x^2$$", result)

    def test_empty_string_returns_empty(self) -> None:
        """Empty input returns empty output."""
        self.assertEqual(format_browser_response(""), "")

    def test_no_math_or_html_is_passthrough(self) -> None:
        """Plain text without special tokens is returned as-is (modulo blank-line collapse)."""
        text = "Hello, this is plain text."
        self.assertEqual(format_browser_response(text).strip(), text)

    def test_mixed_content_math_html_and_code(self) -> None:
        """Mixed content: math preserved, HTML escaped, code fences untouched."""
        raw = (
            "## Formula\n\n"
            "The energy is $$E=mc^2$$ where $c$ is light speed.\n\n"
            "```python\n"
            "import math\n"
            "print('<hello>')\n"
            "```\n\n"
            "See <script>danger</script> for details."
        )
        result = format_browser_response(raw)

        # Math preserved
        self.assertIn("$$E=mc^2$$", result)
        self.assertIn("$c$", result)

        # Code fence content untouched (including angle brackets)
        self.assertIn("print('<hello>')", result)
        self.assertNotIn("&lt;hello&gt;", result)

        # HTML in plain text escaped
        self.assertIn("&lt;script&gt;danger&lt;/script&gt;", result)
        self.assertNotIn("<script>danger</script>", result)

    def test_blank_lines_collapsed(self) -> None:
        """Runs of three or more newlines are collapsed to two."""
        result = format_browser_response("Line 1\n\n\n\n\nLine 2")
        self.assertIn("Line 1\n\nLine 2", result)

    def test_html_escape_inline_math_surrounding(self) -> None:
        """Text surrounding inline math is HTML-escaped while math stays raw."""
        result = format_browser_response(
            "Use <x> with parameter $\\alpha$ for <y>."
        )
        self.assertIn("$\\alpha$", result)
        self.assertIn("&lt;x&gt;", result)
        self.assertIn("&lt;y&gt;", result)

    def test_display_math_with_html_inside(self) -> None:
        """HTML-like content inside display math is NOT escaped."""
        result = format_browser_response(
            "Equation: $$ \\langle x \\rangle $$"
        )
        self.assertIn("$$ \\langle x \\rangle $$", result)


if __name__ == "__main__":
    unittest.main()
