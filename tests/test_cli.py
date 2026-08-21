import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
