import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from catharsis import run_source, to_dict
from catharsis.cli import main
from catharsis.errors import CatharsisRuntimeError

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*.feel"))


class TestCLI(unittest.TestCase):
    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_check_reports_statement_count(self):
        code, out, _ = self.run_cli("check", str(ROOT / "examples" / "forgiveness.feel"))
        self.assertEqual(code, 0)
        self.assertIn("statements, no syntax errors", out)

    def test_run_prints_a_report(self):
        code, out, _ = self.run_cli("run", str(ROOT / "examples" / "contradiction.feel"))
        self.assertEqual(code, 0)
        self.assertIn("=== world at tick", out)

    def test_json_output_is_valid(self):
        code, out, _ = self.run_cli("run", str(ROOT / "examples" / "reputation.feel"), "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("state", payload)
        self.assertIn("alice", payload["state"]["agents"])
        self.assertIsInstance(payload["output"], list)

    def test_trace_shows_events(self):
        code, out, _ = self.run_cli("run", str(ROOT / "examples" / "society.feel"), "--trace", "--quiet")
        self.assertEqual(code, 0)
        self.assertIn("[tick 1]", out)

    def test_words_lists_the_vocabulary(self):
        code, out, _ = self.run_cli("words")
        self.assertEqual(code, 0)
        self.assertIn("loneliness", out)
        self.assertIn("betray", out)

    def test_a_syntax_error_exits_nonzero_with_a_caret(self):
        bad = ROOT / "tests" / "_bad.feel"
        bad.write_text("alice = agent\nlvoe alice bob\n", encoding="utf-8")
        try:
            code, _, err = self.run_cli("run", str(bad))
        finally:
            bad.unlink()
        self.assertEqual(code, 1)
        self.assertIn("unknown utterance", err)
        self.assertIn("^", err)

    def test_a_missing_file_is_reported(self):
        code, _, err = self.run_cli("run", str(ROOT / "nope.feel"))
        self.assertEqual(code, 1)
        self.assertIn("no such program", err)


class TestRuntimeErrors(unittest.TestCase):
    def test_unknown_agent_suggests_a_declared_one(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("alice = agent\nlove alice bobb\n")
        rendered = caught.exception.render()
        self.assertIn("no agent named 'bobb'", rendered)
        self.assertIn("bob", rendered)  # the suggestion

    def test_redeclaring_an_agent_is_an_error(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("alice = agent\nalice = agent\n")
        self.assertIn("already an agent", str(caught.exception))

    def test_joining_a_group_that_does_not_exist(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("alice = agent\njoin alice crew\n")
        self.assertIn("no group named 'crew'", str(caught.exception))

    def test_a_trait_must_be_an_emotion(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("alice = agent\ntrait alice tallness 0.5\n")
        self.assertIn("not an emotion", str(caught.exception))


class TestExamples(unittest.TestCase):
    def test_there_are_examples(self):
        self.assertGreaterEqual(len(EXAMPLES), 5)

    def test_every_example_runs_and_is_reproducible(self):
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                source = path.read_text(encoding="utf-8")
                first = to_dict(run_source(source, str(path)))
                second = to_dict(run_source(source, str(path)))
                self.assertEqual(first, second, f"{path.name} is not deterministic")
                self.assertTrue(first["agents"], f"{path.name} produced no agents")

    def test_the_readme_links_to_examples_that_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for path in EXAMPLES:
            self.assertIn(f"examples/{path.name}", readme, f"{path.name} is not in the README")


class TestSpectrumCommand(unittest.TestCase):
    """`catharsis spectrum` -- the field on its own, and with a run laid over it."""

    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_the_field_on_its_own(self):
        code, out, _ = self.run_cli("spectrum")
        self.assertEqual(code, 0)
        self.assertIn("the whole field:", out)
        self.assertIn("spectral radius", out)
        self.assertIn("reachable growth", out)
        self.assertIn("couplings driving it:", out)
        # The distinction the tool exists to make.
        self.assertIn("RUNS AWAY", out)
        self.assertIn("HELD BY THE CONE", out)

    def test_a_program_picks_its_own_edge(self):
        code, out, _ = self.run_cli("spectrum", str(ROOT / "examples" / "forgiveness.feel"))
        self.assertEqual(code, 0)
        self.assertIn("the whole field:", out)

    def test_an_explicit_edge_and_a_written_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "phase.html"
            code, out, _ = self.run_cli(
                "spectrum",
                str(ROOT / "examples" / "romeo.feel"),
                "--edge",
                "romeo",
                "juliet",
                "-o",
                str(out_path),
            )
            self.assertEqual(code, 0)
            self.assertIn(str(out_path), out)
            page = out_path.read_text(encoding="utf-8")
            self.assertIn('id="payload"', page)

    def test_a_program_with_no_bonds_at_all(self):
        # `pair` comes out empty, so no edge is chosen and nothing is traced.
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / "alone.feel"
            program.write_text("agent alice\ntick 1\n", encoding="utf-8")
            code, out, _ = self.run_cli("spectrum", str(program))
            self.assertEqual(code, 0)
            self.assertIn("the whole field:", out)


class TestExtraTicks(unittest.TestCase):
    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_run_keeps_ticking_after_the_program_ends(self):
        program = str(ROOT / "examples" / "coordination.feel")
        _, plain, _ = self.run_cli("run", program, "--json", "--quiet")
        _, extra, _ = self.run_cli("run", program, "--json", "--quiet", "--ticks", "5")
        self.assertNotEqual(json.loads(plain)["state"], json.loads(extra)["state"])

    def test_visualize_keeps_ticking_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain, extra = Path(tmp) / "a.html", Path(tmp) / "b.html"
            program = str(ROOT / "examples" / "coordination.feel")
            _, first, _ = self.run_cli("visualize", program, "-o", str(plain))
            _, second, _ = self.run_cli("visualize", program, "-o", str(extra), "--ticks", "5")
            self.assertIn("moments", first)
            self.assertIn("moments", second)
            self.assertGreater(extra.stat().st_size, plain.stat().st_size)

    def test_visualize_defaults_its_output_beside_the_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / "tiny.feel"
            program.write_text("agent a b\nlove a b 0.5\ntick 2\n", encoding="utf-8")
            code, out, _ = self.run_cli("visualize", str(program))
            self.assertEqual(code, 0)
            self.assertTrue(program.with_suffix(".html").exists())
            self.assertIn("entities", out)


class TestFailureModes(unittest.TestCase):
    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_a_syntax_error_is_rendered_with_its_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / "bad.feel"
            program.write_text("agent a\n!!!\n", encoding="utf-8")
            code, _, err = self.run_cli("check", str(program))
            self.assertEqual(code, 1)
            self.assertIn("syntax error: unexpected character", err)
            self.assertIn("2 | !!!", err)

    def test_a_runtime_error_is_reported_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / "bad.feel"
            program.write_text("love alice bob\n", encoding="utf-8")
            code, _, err = self.run_cli("run", str(program))
            self.assertEqual(code, 1)
            self.assertIn("no agent named", err)

    def test_a_closed_pipe_is_not_an_error(self):
        # `catharsis words | head` closes stdout under us.  The handler points
        # the rest of stdout at devnull so the interpreter stays quiet on exit.
        # Not run under redirect_stdout: the handler needs a real fileno().
        with mock.patch("catharsis.cli._cmd_words", side_effect=BrokenPipeError):
            with mock.patch("catharsis.cli.os.dup2") as dup2:
                code = main(["words"])
        self.assertEqual(code, 0)
        dup2.assert_called_once()

    def test_the_module_entry_point_runs_the_cli(self):
        # In-process, so `python -m catharsis` is actually measured rather than
        # being run somewhere the coverage of this process cannot see.
        argv = ["catharsis", "check", str(ROOT / "examples" / "sort.feel")]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_module("catharsis", run_name="__main__")
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("no syntax errors", out.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
