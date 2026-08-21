"""The intermediate representation.

A Catharsis program is a flat sequence of declarations and utterances.  There is
no nesting because there is no control flow: the interesting structure is built
at runtime, in the field, not in the syntax tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field


@dataclass(frozen=True)
class Arg:
    """One bound argument, with its source position for error reporting."""

    kind: str  # agent | entity | group | word | event | text | number | value
    value: object
    line: int
    column: int


@dataclass(frozen=True)
class Node:
    line: int
    column: int
    text: str


@dataclass(frozen=True)
class Declare(Node):
    """``alice = agent``"""

    name: str


@dataclass(frozen=True)
class Utter(Node):
    """``love alice bob 0.9`` -- a verb and its slots, aligned to the spec params."""

    verb: str
    slots: tuple[Arg | None, ...]
    spelling: str = ""

    def slot(self, index: int, default=None):
        if index >= len(self.slots):
            return default
        arg = self.slots[index]
        return default if arg is None else arg.value


@dataclass
class Program:
    statements: list[Node] = dc_field(default_factory=list)
    filename: str = "<source>"
    source: str = ""

    def line_text(self, line: int) -> str:
        lines = self.source.splitlines()
        return lines[line - 1] if 0 < line <= len(lines) else ""
