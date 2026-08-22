"""Parser for Catharsis.

Grammar, in full::

    program   := line*
    line      := declaration | utterance | <empty>
    declaration := NAME '=' 'agent'
    utterance := NAME argument*
    argument  := NAME | NUMBER | STRING

``agent alice bob carol`` is an ordinary utterance that happens to declare, so
one line can introduce a whole cast; ``alice = agent`` is the same thing for a
single entity, kept because it reads better on its own.

Arguments are bound to the slots declared by the utterance's entry in
:mod:`catharsis.vocabulary`, which is what lets ``pride alice 0.8`` and
``love alice bob 0.8`` share one signature without ambiguity.
"""

from __future__ import annotations

from .ast import Arg, Declare, Program, Utter
from .errors import ParseError, suggest
from .lexer import Token, tokenize
from .vocabulary import AGENT_GLYPH, ALIASES, PARTICLES, RESERVED, VOCABULARY, lookup, resolve

_NAME_KINDS = {"agent", "entity", "group", "word", "event"}


def _matches(token: Token, kind: str) -> bool:
    base = kind.rstrip("?+")
    if base in _NAME_KINDS:
        return token.kind == "NAME"
    if base == "text":
        return token.kind == "STRING"
    if base == "number":
        return token.kind == "NUMBER"
    if base == "value":
        return token.kind in ("STRING", "NUMBER")
    return False  # pragma: no cover - unknown slot kind is a table bug


def _describe(kind: str) -> str:
    base = kind.rstrip("?+")
    plural = kind.endswith("+")
    described = {
        "agent": "an agent name",
        "entity": "an agent or group name",
        "group": "a group name",
        "word": "a bare word",
        "event": "an event word",
        "text": 'a "quoted claim"',
        "number": "a number",
        "value": 'a number or a "quoted string"',
    }.get(base, base)
    if not plural:
        return described
    return {
        "agent": "one or more agent names",
        "word": "one or more bare words",
        "text": 'one or more "quoted claims"',
        "number": "one or more numbers",
    }.get(base, f"one or more {described}")


class Parser:
    def __init__(self, source: str, filename: str = "<source>") -> None:
        self.source = source
        self.filename = filename
        self.tokens = tokenize(source, filename)
        self.pos = 0

    # -- token helpers ----------------------------------------------------
    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        token = self.tokens[self.pos]
        if token.kind != "EOF":
            self.pos += 1
        return token

    def error(self, message: str, token: Token, hint: str | None = None) -> ParseError:
        return ParseError(
            message,
            line=token.line,
            column=token.column,
            text=token.text,
            filename=self.filename,
            hint=hint,
        )

    # -- entry point ------------------------------------------------------
    def parse(self) -> Program:
        program = Program(filename=self.filename, source=self.source)
        while self.current.kind != "EOF":
            if self.current.kind == "NEWLINE":
                self.advance()
                continue
            program.statements.append(self.parse_line())
        return program

    def parse_line(self):
        head = self.current
        if head.kind != "NAME":
            raise self.error(
                f"a line must start with a word, found {self._token_desc(head)}",
                head,
                hint="every Catharsis line is either 'name = agent' or 'verb args...'",
            )
        if self.tokens[self.pos + 1].kind == "EQUALS":
            return self.parse_declaration()
        return self.parse_utterance()

    def parse_declaration(self) -> Declare:
        name_token = self.advance()
        self.advance()  # '='
        kind_token = self.current
        if kind_token.kind != "NAME" or kind_token.value not in ("agent", AGENT_GLYPH):
            raise self.error(
                "only 'agent' can be declared",
                kind_token,
                hint=f"write 'alice = agent' (or 'alice = {AGENT_GLYPH}'); "
                "groups are declared with 'group name'",
            )
        self.advance()
        name = str(name_token.value)
        self._check_agent_name(name, name_token)
        self.expect_end()
        return Declare(name_token.line, name_token.column, name_token.text, name)

    def parse_utterance(self) -> Utter:
        verb_token = self.advance()
        spelling = str(verb_token.value)
        canonical = resolve(spelling)
        spec = lookup(spelling)
        if spec is None:
            raise self.error(
                f"unknown utterance '{spelling}'",
                verb_token,
                hint=suggest(spelling, VOCABULARY)
                or "run 'catharsis words' to list everything the language can say",
            )

        raw: list[Token] = []
        while self.current.kind in ("NAME", "NUMBER", "STRING"):
            token = self.advance()
            if token.kind == "NAME" and token.value in PARTICLES:
                continue  # particles are punctuation made of letters
            raw.append(token)

        slots: list[Arg | None] = []
        index = 0
        for param in spec.params:
            optional = param.endswith("?")
            if param.endswith("+"):
                # A repeating slot swallows every remaining argument that fits,
                # and binds them as one tuple.  This is what lets `agent` declare
                # a whole cast on one line without the grammar growing a list
                # syntax it would need nowhere else.
                taken = []
                while index < len(raw) and _matches(raw[index], param):
                    taken.append(raw[index])
                    index += 1
                if not taken:
                    token = raw[index] if index < len(raw) else verb_token
                    got = self._token_desc(token) if index < len(raw) else "nothing"
                    raise self.error(
                        f"'{canonical}' expects {_describe(param)} here, found {got}",
                        token,
                        hint=self._usage(canonical, spec.params),
                    )
                first = taken[0]
                slots.append(
                    Arg(param.rstrip("+"), tuple(str(t.value) for t in taken), first.line, first.column)
                )
                continue
            if index < len(raw) and _matches(raw[index], param):
                token = raw[index]
                slots.append(Arg(param.rstrip("?"), token.value, token.line, token.column))
                index += 1
            elif optional:
                slots.append(None)
            else:
                token = raw[index] if index < len(raw) else verb_token
                got = self._token_desc(token) if index < len(raw) else "nothing"
                raise self.error(
                    f"'{canonical}' expects {_describe(param)} here, found {got}",
                    token,
                    hint=self._usage(canonical, spec.params),
                )
        if index < len(raw):
            extra = raw[index]
            raise self.error(
                f"'{canonical}' does not take another argument",
                extra,
                hint=self._usage(canonical, spec.params),
            )
        if canonical == "agent":
            for name in slots[0].value:
                self._check_agent_name(name, verb_token)
        self.expect_end()
        return Utter(verb_token.line, verb_token.column, verb_token.text, canonical, tuple(slots), spelling)

    def _check_agent_name(self, name: str, token: Token) -> None:
        if name in RESERVED or name in VOCABULARY or name in ALIASES:
            raise self.error(
                f"'{name}' is a reserved word and cannot name an agent",
                token,
                hint="pick a name that is not an emotion, an event or a particle",
            )

    def expect_end(self) -> None:
        token = self.current
        if token.kind in ("NEWLINE", "EOF"):
            if token.kind == "NEWLINE":
                self.advance()
            return
        # Reachable: `love alice = bob` puts an EQUALS here, because `raw` only
        # ever swallows NAME, NUMBER and STRING.
        raise self.error(
            f"unexpected {self._token_desc(token)} at end of line",
            token,
        )

    @staticmethod
    def _usage(name: str, params: tuple[str, ...]) -> str:
        return "usage: " + signature(name, params)

    @staticmethod
    def _token_desc(token: Token) -> str:
        if token.kind == "NAME":
            return f"the word '{token.value}'"
        if token.kind == "NUMBER":
            return f"the number {token.value:g}"
        if token.kind == "STRING":
            return "a quoted claim"
        if token.kind == "EQUALS":
            return "'='"
        # No caller can reach these: `raw` holds only NAME/NUMBER/STRING, and
        # `expect_end` returns before describing a NEWLINE or an EOF.  They stay
        # as a fallback so a future caller gets a sentence rather than a crash.
        if token.kind == "NEWLINE":  # pragma: no cover - see above
            return "end of line"
        return "end of file"  # pragma: no cover - see above


def signature(name: str, params: tuple[str, ...]) -> str:
    """Render an utterance's shape, e.g. ``agent <word> [word ...]``."""
    parts = []
    for param in params:
        base = param.rstrip("?+")
        rendered = {"text": '"claim"', "value": "value"}.get(base, base)
        if param.endswith("+"):
            parts.append(f"<{rendered}> [{rendered} ...]")
        else:
            parts.append(f"[{rendered}]" if param.endswith("?") else f"<{rendered}>")
    return " ".join([name, *parts])


def parse(source: str, filename: str = "<source>") -> Program:
    """Parse Catharsis source into a :class:`~catharsis.ast.Program`."""
    return Parser(source, filename).parse()
