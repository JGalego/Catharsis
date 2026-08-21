"""Command line interface: ``catharsis run program.feel``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .errors import CatharsisError, SourceError
from .parser import parse, signature
from .report import render_world, to_dict
from .vocabulary import ALIASES, ALL_GLYPHS, VOCABULARY
from .world import World

__all__ = ["main"]


def _read(path: str) -> tuple[str, str]:
    file = Path(path)
    if not file.exists():
        raise CatharsisError(f"no such program: {path}")
    return file.read_text(encoding="utf-8"), str(file)


def _cmd_run(args: argparse.Namespace) -> int:
    source, name = _read(args.program)
    program = parse(source, name)
    lines: list[str] = []
    sink = lines.append if args.json else print
    world = World(sink=sink, trace=args.trace, emoji=args.emoji)
    world.run(program)
    if args.ticks:
        for _ in range(args.ticks):
            world.step()
    if args.json:
        json.dump({"output": lines, "state": to_dict(world)}, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return 0
    if not args.quiet:
        print()
        for line in render_world(world):
            print(line)
    return 0


def _cmd_visualize(args: argparse.Namespace) -> int:
    from .viz import build_payload, render_html

    source, name = _read(args.program)
    program = parse(source, name)
    world = World(record=True)
    world.run(program)
    for _ in range(args.ticks):
        world.step()
    out = Path(args.output) if args.output else Path(args.program).with_suffix(".html")
    out.write_text(render_html(build_payload(world, Path(name).stem, source)), encoding="utf-8")
    print(f"{out}  ({len(world.frames)} moments, {len(world.agents)} entities)")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    source, name = _read(args.program)
    program = parse(source, name)
    print(f"{name}: {len(program.statements)} statements, no syntax errors")
    return 0


def _cmd_words(args: argparse.Namespace) -> int:
    reverse: dict[str, list[str]] = {}
    for alias, canonical in ALIASES.items():
        if alias in ALL_GLYPHS.values():
            continue  # shown as the entry's glyph instead
        reverse.setdefault(canonical, []).append(alias)
    for category in ("emotion", "event"):
        print(f"-- {category}s --")
        for name in sorted(VOCABULARY):
            spec = VOCABULARY[name]
            if spec.category != category:
                continue
            aliases = reverse.get(name)
            suffix = f"   (also: {', '.join(sorted(aliases))})" if aliases else ""
            glyph = ALL_GLYPHS.get(name, " ")
            print(f"  {glyph}  {signature(name, spec.params)}")
            print(f"      {spec.doc}{suffix}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catharsis",
        description="Catharsis -- programs with feelings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="execute a .feel program")
    run.add_argument("program")
    run.add_argument("--ticks", type=int, default=0, help="extra ticks to run after the program ends")
    run.add_argument("--trace", action="store_true", help="print every event as it happens")
    run.add_argument("--json", action="store_true", help="emit the final state as JSON")
    run.add_argument("--quiet", action="store_true", help="suppress the closing state report")
    run.add_argument("--emoji", action="store_true", help="render state with one glyph per emotion")
    run.set_defaults(func=_cmd_run)

    visualize = subparsers.add_parser("visualize", help="replay a program as a graph you can scrub through")
    visualize.add_argument("program")
    visualize.add_argument("-o", "--output", help="where to write the HTML (default: alongside the program)")
    visualize.add_argument("--ticks", type=int, default=0, help="extra ticks to run after the program ends")
    visualize.set_defaults(func=_cmd_visualize)

    check = subparsers.add_parser("check", help="parse a program without running it")
    check.add_argument("program")
    check.set_defaults(func=_cmd_check)

    words = subparsers.add_parser("words", help="list everything the language can say")
    words.set_defaults(func=_cmd_words)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SourceError as error:
        print(error.render(), file=sys.stderr)
        return 1
    except CatharsisError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        # `catharsis words | head` closes the pipe under us.  Point the rest of
        # stdout at devnull so the interpreter does not complain again on exit.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
