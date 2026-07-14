"""Tests des validations avant compilation LaTeX."""

import pytest

from qcmscan.latexgen import LatexError, verifier_texte_question


def test_ampersand_literal_is_reported():
    with pytest.raises(LatexError, match="non échappé"):
        verifier_texte_question("SVT & maths", "La réponse 1")


def test_escaped_ampersand_is_accepted():
    verifier_texte_question(r"SVT \& maths", "La réponse 1")


def test_ampersand_after_two_backslashes_is_reported():
    with pytest.raises(LatexError, match="non échappé"):
        verifier_texte_question(r"texte\\&", "La réponse 1")
