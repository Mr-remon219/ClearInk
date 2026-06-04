from __future__ import annotations

import unittest

from clearink.user.output_format import format_response_text


class OutputFormatTests(unittest.TestCase):
    def test_beautifies_display_math_blocks(self) -> None:
        raw = (
            r"$$\text{Eq (4): } \mathrm{Var}[y_l] = n_l \mathrm{Var}[w_l] "
            r"\mathrm{E}[x_l^2] \quad \text{(Glorot &amp; Bengio methodology)}$$ "
            r"$$\downarrow \text{ReLU: } \mathrm{E}[x_l^2] "
            r"= \tfrac{1}{2}\mathrm{Var}[y_{l-1}] \quad "
            r"\text{(Nair &amp; Hinton insight)}$$ "
            r"$$\text{Eq (7): } \tfrac{1}{2} n_l \mathrm{Var}[w_l] = 1 "
            r";\Rightarrow; \sigma = \sqrt{2/n_l} \quad "
            r"\text{(Kaiming initialization)}$$"
        )

        formatted = format_response_text(raw)

        self.assertNotIn("$$", formatted)
        self.assertNotIn(r"\text", formatted)
        self.assertNotIn(r"\mathrm", formatted)
        self.assertNotIn(r"\tfrac", formatted)
        self.assertIn("Eq (4): Var[y_l] = n_l Var[w_l] E[x_l^2]", formatted)
        self.assertIn("-> ReLU: E[x_l^2] = 1/2 Var[y_(l-1)]", formatted)
        self.assertIn("Glorot & Bengio methodology", formatted)
        self.assertIn(
            "Eq (7): 1/2 n_l Var[w_l] = 1 => sigma = sqrt(2/n_l)",
            formatted,
        )

    def test_does_not_rewrite_code_fences(self) -> None:
        raw = "Before $x_l^2$\n```tex\n$$\\text{raw}$$\n```\nAfter"

        formatted = format_response_text(raw)

        self.assertIn("Before x_l^2", formatted)
        self.assertIn("```tex\n$$\\text{raw}$$\n```", formatted)


if __name__ == "__main__":
    unittest.main()
