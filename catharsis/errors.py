"""Errors with enough context to be useful."""

from __future__ import annotations

import difflib


class CatharsisError(Exception):
    """Base class for every error the language raises."""


class SourceError(CatharsisError):
    """An error that can point at a place in the source text."""

    def __init__(
        self,
        message: str,
        *,
        line: int = 0,
        column: int = 0,
        text: str = "",
        filename: str = "<source>",
        hint: str | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.column = column
        self.text = text
        self.filename = filename
        self.hint = hint
        super().__init__(self.render())

    def render(self) -> str:
        head = f"{self.filename}:{self.line}:{self.column}: {self.label}: {self.message}"
        parts = [head]
        if self.text:
            gutter = f"{self.line:>4} | "
            parts.append(gutter + self.text.rstrip("\n"))
            parts.append(" " * len(gutter) + " " * max(0, self.column - 1) + "^")
        if self.hint:
            parts.append(f"       hint: {self.hint}")
        return "\n".join(parts)

    label = "error"


class LexError(SourceError):
    label = "syntax error"


class ParseError(SourceError):
    label = "parse error"


class CatharsisRuntimeError(SourceError):
    label = "runtime error"


def suggest(word: str, options, prefix: str = "did you mean") -> str | None:
    """Return a ``did you mean ...`` hint, or ``None``."""
    matches = difflib.get_close_matches(word, sorted(options), n=2, cutoff=0.6)
    if not matches:
        return None
    quoted = " or ".join(f"'{match}'" for match in matches)
    return f"{prefix} {quoted}?"
