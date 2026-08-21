"""Catharsis -- programs with feelings.

An esoteric language in which emotion is the computational substrate: entities,
the charge on the edges between them, what they cannot forget, and what they are
still arguing with themselves about.

    >>> from catharsis import run_source
    >>> world = run_source('alice = agent\\nbob = agent\\nlove alice bob\\ntick 3\\n')
    >>> round(world.agents["alice"].feels("trust", "bob"), 2) > 0
    True
"""

from .errors import CatharsisError, CatharsisRuntimeError, LexError, ParseError, SourceError
from .parser import parse
from .report import to_dict
from .world import World, run_source

__version__ = "0.1.0"

__all__ = [
    "CatharsisError",
    "LexError",
    "ParseError",
    "CatharsisRuntimeError",
    "SourceError",
    "World",
    "parse",
    "run_source",
    "to_dict",
    "__version__",
]
