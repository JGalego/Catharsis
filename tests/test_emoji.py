"""The emoji shorthand is a spelling, not a dialect.

The load-bearing test here is :meth:`TestEmojiInput.test_both_spellings_produce_the_same_world`:
if a glyph ever acquires semantics of its own, that test fails.
"""

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from catharsis import parse, run_source, to_dict
from catharsis.cli import main
from catharsis.errors import ParseError
from catharsis.field import EMOTIONS
from catharsis.lexer import tokenize
from catharsis.vocabulary import ALL_GLYPHS, EVENT_GLYPHS, GLYPHS, VOCABULARY

WORDS = """
alice = agent
bob = agent
carol = agent

love alice bob 0.9
trust bob alice 0.8
jealousy carol alice 0.7
loneliness carol 0.6
betray alice bob
grief bob
doubt bob alice
witness carol alice betraying bob
tick 10
apology alice bob
tick 5
forgive bob alice
tick 5
"""

EMOJI = """
alice = 👤
bob = 👤
carol = 👤

❤️ alice bob 0.9
🤝 bob alice 0.8
💚 carol alice 0.7
🧍 carol 0.6
💔 alice bob
🖤 bob
🤔 bob alice
👁️ carol alice betraying bob
⏱️ 10
🙇 alice bob
⏱️ 5
🤲 bob alice
⏱️ 5
"""


class TestGlyphTable(unittest.TestCase):
    def test_every_emotion_has_a_glyph(self):
        self.assertEqual(set(GLYPHS), set(EMOTIONS))

    def test_glyphs_are_unique(self):
        self.assertEqual(len(set(ALL_GLYPHS.values())), len(ALL_GLYPHS))

    def test_event_glyphs_name_real_utterances(self):
        for name in EVENT_GLYPHS:
            self.assertIn(name, VOCABULARY, f"{name} is not an utterance")


class TestEmojiLexing(unittest.TestCase):
    def test_a_multi_codepoint_emoji_is_one_token(self):
        # U+2764 U+FE0F -- a heart plus a variation selector.
        tokens = tokenize("❤️ alice bob\n")
        self.assertEqual(tokens[0].kind, "NAME")
        self.assertEqual(tokens[0].value, "❤️")
        self.assertEqual([t.value for t in tokens[1:3]], ["alice", "bob"])

    def test_a_zwj_sequence_is_one_token(self):
        tokens = tokenize("👨‍👩‍👧 alice\n")
        self.assertEqual(tokens[0].value, "👨‍👩‍👧")
        self.assertEqual(tokens[1].value, "alice")

    def test_adjacent_glyphs_do_not_merge(self):
        tokens = tokenize("❤️🤝\n")
        self.assertEqual([t.value for t in tokens[:2]], ["❤️", "🤝"])

    def test_letters_outside_ascii_are_still_names(self):
        world = run_source("renée = agent\nzoë = agent\n❤️ renée zoë\n")
        self.assertGreater(world.agents["renée"].feels("love", "zoë"), 0.0)


class TestEmojiInput(unittest.TestCase):
    def test_both_spellings_produce_the_same_world(self):
        self.assertEqual(to_dict(run_source(WORDS)), to_dict(run_source(EMOJI)))

    def test_the_two_spellings_are_not_accidentally_the_same_text(self):
        self.assertNotEqual(WORDS, EMOJI)

    def test_a_glyph_resolves_to_its_utterance(self):
        self.assertEqual(parse("💔 alice bob\n").statements[0].verb, "betray")
        self.assertEqual(parse("🧍 carol\n").statements[0].verb, "loneliness")

    def test_the_original_spelling_is_kept_for_diagnostics(self):
        self.assertEqual(parse("💔 alice bob\n").statements[0].spelling, "💔")

    def test_a_glyph_cannot_name_an_agent(self):
        with self.assertRaises(ParseError) as caught:
            parse("❤️ = agent\n")
        self.assertIn("reserved word", str(caught.exception))

    def test_an_unknown_glyph_is_an_error(self):
        with self.assertRaises(ParseError) as caught:
            parse("🦑 alice bob\n")
        self.assertIn("unknown utterance", str(caught.exception))

    def test_glyphs_mix_freely_with_words(self):
        world = run_source("a = agent\nb = 👤\n❤️ a b 0.8\ntrust b a 0.5\n⏱️ 3\n")
        self.assertGreater(world.agents["a"].feels("love", "b"), 0.0)
        self.assertGreater(world.agents["b"].feels("trust", "a"), 0.0)


class TestEmojiOutput(unittest.TestCase):
    def render(self, *argv) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(list(argv)), 0)
        return out.getvalue()

    def test_emoji_flag_renders_glyphs(self):
        rendered = self.render("run", "examples/contradiction.feel", "--emoji", "--quiet")
        self.assertIn("❤️", rendered)
        self.assertNotIn(" love ", rendered)

    def test_without_the_flag_the_report_stays_in_words(self):
        rendered = self.render("run", "examples/contradiction.feel", "--quiet")
        self.assertIn("love", rendered)
        self.assertNotIn("❤️", rendered)

    def test_the_flag_does_not_change_the_state(self):
        source = Path("examples/contradiction.feel").read_text(encoding="utf-8")
        plain = run_source(source)
        glyphed = run_source(source)
        glyphed.emoji = True
        self.assertEqual(to_dict(plain), to_dict(glyphed))

    def test_words_lists_the_glyphs(self):
        listing = self.render("words")
        self.assertIn("❤️", listing)
        self.assertIn("💔", listing)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
