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


def test_ampersand_accepted_inside_array():
    verifier_texte_question(
        r"$\begin{array}{|c|c|} \hline x & 1 \\ \hline \end{array}$",
        "L'énoncé")


def test_ampersand_accepted_with_tkztab():
    verifier_texte_question(
        r"\tkzTabInit{$x$/1}{$-\infty$,$+\infty$} avec x & y", "L'énoncé")


def test_ampersand_accepted_inside_cases():
    verifier_texte_question(
        r"$f(x)=\begin{cases} 1 & x>0 \\ 0 & sinon \end{cases}$",
        "L'énoncé")
