"""Tokenizer for Catharsis source.

The syntax is deliberately tiny: one utterance per line, words separated by
spaces.  There are no blocks, no operators and no punctuation beyond ``=`` and
string quotes, because every interesting thing in the language happens in the
runtime rather than in the grammar.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import LexError

NAME_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
NAME_BODY = NAME_START | set("0123456789-.")
DIGITS = set("0123456789")

#: Characters that continue an emoji rather than starting a new one: variation
#: selectors, the combining keycap, and skin tone modifiers.
EMOJI_MODIFIERS = {"️", "︎", "⃣"}
ZWJ = "‍"


def _is_name_start(char: str) -> bool:
    """Letters (in any script) and underscore begin a word."""
    return char in NAME_START or char.isalpha()


def _is_name_body(char: str) -> bool:
    return char in NAME_BODY or char.isalpha() or char.isdigit()


def _is_glyph_start(char: str) -> bool:
    """Anything printable that is neither a letter, a digit nor punctuation.

    Emoji are not a separate token kind -- they lex to a ``NAME`` and resolve
    through the same alias table as ``lonely`` or ``apology``.  Keeping them out
    of the grammar is what lets them be a pure data addition.
    """
    return not char.isspace() and not char.isalpha() and not char.isdigit() and not char.isascii()


def _glyph_at(raw: str, index: int) -> tuple[str, int]:
    """Consume one whole emoji, including ZWJ sequences and modifiers.

    ``❤️`` is two code points and ``👨‍👩‍👧`` is five; both are one word here.
    """
    start = index
    index += 1
    length = len(raw)
    while index < length:
        char = raw[index]
        if char in EMOJI_MODIFIERS or "\U0001f3fb" <= char <= "\U0001f3ff":
            index += 1
        elif char == ZWJ and index + 1 < length:
            index += 2
        else:
            break
    return raw[start:index], index


@dataclass(frozen=True)
class Token:
    kind: str  # NAME | NUMBER | STRING | EQUALS | NEWLINE | EOF
    value: object
    line: int
    column: int
    text: str = ""

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.kind}({self.value!r})@{self.line}:{self.column}"


def tokenize(source: str, filename: str = "<source>") -> list[Token]:
    """Turn source text into a flat token list."""
    tokens: list[Token] = []
    lines = source.splitlines()
    for lineno, raw in enumerate(lines, start=1):
        index = 0
        length = len(raw)
        while index < length:
            char = raw[index]
            if char in " \t":
                index += 1
                continue
            if char == "#":
                break
            column = index + 1
            if char == "=":
                tokens.append(Token("EQUALS", "=", lineno, column, raw))
                index += 1
                continue
            if char == '"':
                index += 1
                buffer = []
                while index < length and raw[index] != '"':
                    if raw[index] == "\\" and index + 1 < length:
                        escape = raw[index + 1]
                        buffer.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(escape, escape))
                        index += 2
                        continue
                    buffer.append(raw[index])
                    index += 1
                if index >= length:
                    raise LexError(
                        "unterminated string",
                        line=lineno,
                        column=column,
                        text=raw,
                        filename=filename,
                        hint='strings must be closed with a matching " on the same line',
                    )
                index += 1
                tokens.append(Token("STRING", "".join(buffer), lineno, column, raw))
                continue
            if char in DIGITS or (char == "-" and index + 1 < length and raw[index + 1] in DIGITS):
                start = index
                index += 1
                seen_dot = False
                while index < length and (raw[index] in DIGITS or (raw[index] == "." and not seen_dot)):
                    seen_dot = seen_dot or raw[index] == "."
                    index += 1
                literal = raw[start:index]
                try:
                    value = float(literal)
                except ValueError:  # pragma: no cover - guarded by the scanner
                    raise LexError(
                        f"malformed number {literal!r}",
                        line=lineno,
                        column=column,
                        text=raw,
                        filename=filename,
                    ) from None
                tokens.append(Token("NUMBER", value, lineno, column, raw))
                continue
            if _is_name_start(char):
                start = index
                while index < length and _is_name_body(raw[index]):
                    index += 1
                tokens.append(Token("NAME", raw[start:index], lineno, column, raw))
                continue
            if _is_glyph_start(char):
                glyph, index = _glyph_at(raw, index)
                tokens.append(Token("NAME", glyph, lineno, column, raw))
                continue
            raise LexError(
                f"unexpected character {char!r}",
                line=lineno,
                column=column,
                text=raw,
                filename=filename,
                hint='Catharsis lines are words, emoji, numbers and "quoted claims"',
            )
        tokens.append(Token("NEWLINE", None, lineno, len(raw) + 1, raw))
    tokens.append(Token("EOF", None, len(lines) + 1, 1, ""))
    return tokens
