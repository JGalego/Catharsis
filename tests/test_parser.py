import unittest

from catharsis import parse
from catharsis.ast import Declare, Utter
from catharsis.errors import LexError, ParseError, SourceError
from catharsis.vocabulary import resolve


class TestLexing(unittest.TestCase):
    def test_comments_and_blank_lines_are_ignored(self):
        program = parse("# nothing here\n\nalice = agent  # trailing\n")
        self.assertEqual(len(program.statements), 1)

    def test_unterminated_string(self):
        with self.assertRaises(LexError) as caught:
            parse('remember alice "the door\n')
        self.assertIn("unterminated string", str(caught.exception))

    def test_escapes(self):
        program = parse('alice = agent\nremember alice "a \\"quoted\\" thing"\n')
        self.assertEqual(program.statements[1].slot(1), 'a "quoted" thing')


class TestParsing(unittest.TestCase):
    def test_declaration(self):
        statement = parse("alice = agent\n").statements[0]
        self.assertIsInstance(statement, Declare)
        self.assertEqual(statement.name, "alice")

    def test_agent_declares_a_whole_cast(self):
        program = parse("agent alice bob carol\n")
        self.assertEqual(len(program.statements), 1)
        self.assertEqual(program.statements[0].verb, "agent")
        self.assertEqual(program.statements[0].slot(0), ("alice", "bob", "carol"))

    def test_a_repeating_slot_needs_at_least_one(self):
        with self.assertRaises(ParseError) as caught:
            parse("agent\n")
        message = str(caught.exception)
        self.assertIn("one or more bare words", message)
        self.assertIn("usage: agent <word> [word ...]", message)

    def test_a_reserved_word_cannot_be_declared_in_a_list(self):
        with self.assertRaises(ParseError) as caught:
            parse("agent alice love\n")
        self.assertIn("'love' is a reserved word", str(caught.exception))

    def test_emotion_shapes(self):
        program = parse("pride alice 0.8\nlove alice bob 0.9\nfear bob\n")
        self.assertEqual([s.slot(0) for s in program.statements], ["alice", "alice", "bob"])
        self.assertEqual(program.statements[0].slot(1), None)  # no second agent
        self.assertEqual(program.statements[0].slot(3), 0.8)  # bound to the number slot
        self.assertEqual(program.statements[1].slot(1), "bob")
        self.assertEqual(program.statements[1].slot(3), 0.9)

    def test_particles_are_dropped(self):
        with_particle = parse('regret alice over "leaving"\n').statements[0]
        without = parse('regret alice "leaving"\n').statements[0]
        self.assertEqual(
            [None if slot is None else slot.value for slot in with_particle.slots],
            [None if slot is None else slot.value for slot in without.slots],
        )

    def test_aliases_and_gerunds_resolve(self):
        self.assertEqual(parse("lonely charlie\n").statements[0].verb, "loneliness")
        self.assertEqual(parse("apology alice bob\n").statements[0].verb, "apologize")
        self.assertEqual(parse("jealous charlie bob\n").statements[0].verb, "jealousy")

    def test_unknown_verb_suggests(self):
        with self.assertRaises(ParseError) as caught:
            parse("lvoe alice bob\n")
        message = str(caught.exception)
        self.assertIn("unknown utterance 'lvoe'", message)
        self.assertIn("love", message)

    def test_missing_argument_reports_usage(self):
        with self.assertRaises(ParseError) as caught:
            parse("betray alice\n")
        message = str(caught.exception)
        self.assertIn("expects an agent name", message)
        self.assertIn("usage: betray", message)

    def test_too_many_arguments(self):
        with self.assertRaises(ParseError) as caught:
            parse("forgive alice bob charlie\n")
        self.assertIn("does not take another argument", str(caught.exception))

    def test_reserved_words_cannot_be_agents(self):
        with self.assertRaises(ParseError) as caught:
            parse("love = agent\n")
        self.assertIn("reserved word", str(caught.exception))

    def test_error_points_at_the_source(self):
        with self.assertRaises(ParseError) as caught:
            parse("alice = agent\nbetray alice\n")
        rendered = caught.exception.render()
        self.assertIn(":2:", rendered)
        self.assertIn("betray alice", rendered)
        self.assertIn("^", rendered)

    def test_statement_shape(self):
        statement = parse("witness charlie alice betraying bob\n").statements[0]
        self.assertIsInstance(statement, Utter)
        self.assertEqual(statement.verb, "witness")
        self.assertEqual([statement.slot(i) for i in range(4)], ["charlie", "alice", "betraying", "bob"])


class TestRejections(unittest.TestCase):
    """The messages a beginner actually hits, and the token names in them."""

    def bad(self, source: str) -> str:
        with self.assertRaises(SourceError) as caught:
            parse(source)
        return caught.exception.render()

    def test_a_line_must_start_with_a_word(self):
        for source, described in (
            ("0.5 alice bob\n", "the number 0.5"),
            ('"a claim" alice\n', "a quoted claim"),
            ("= agent\n", "'='"),
        ):
            with self.subTest(source=source.strip()):
                rendered = self.bad(source)
                self.assertIn("a line must start with a word", rendered)
                self.assertIn(described, rendered)

    def test_only_an_agent_can_be_declared(self):
        rendered = self.bad("alice = group\n")
        self.assertIn("only 'agent' can be declared", rendered)
        self.assertIn("groups are declared with 'group name'", rendered)

    def test_a_word_where_a_number_belongs(self):
        rendered = self.bad("agent alice\nhave alice bread apples\n")
        self.assertIn("'have' expects a number here", rendered)
        self.assertIn("the word 'apples'", rendered)

    def test_a_stray_equals_after_a_complete_utterance(self):
        # `raw` only swallows words, numbers and quoted claims, so an `=` lands
        # past the end of the arguments.
        self.assertIn("unexpected '=' at end of line", self.bad("love alice = bob\n"))

    def test_a_character_the_language_has_no_use_for(self):
        rendered = self.bad("agent alice\nlove alice & bob\n")
        self.assertIn("unexpected character", rendered)
        self.assertIn("&", rendered)


class TestSlots(unittest.TestCase):
    def test_asking_for_a_slot_that_is_not_there(self):
        statement = parse("pride charlie\n").statements[0]
        self.assertEqual(statement.slot(0), "charlie")
        self.assertIsNone(statement.slot(9))
        self.assertEqual(statement.slot(9, "fallback"), "fallback")

    def test_a_program_can_quote_its_own_source(self):
        program = parse("agent alice\npride alice 0.5\n")
        self.assertEqual(program.line_text(2), "pride alice 0.5")
        self.assertEqual(program.line_text(0), "")
        self.assertEqual(program.line_text(99), "")


class TestNormalisation(unittest.TestCase):
    """A verb is recognised in the shapes people naturally write it in."""

    def test_the_forms_that_resolve(self):
        # `betraying` and `forgiving` would not test the gerund rules -- they
        # are in ALIASES and short-circuit before reaching them.
        cases = {
            "betray": "betray",  # already canonical
            "lonely": "loneliness",  # an alias
            "betraying": "betray",  # an alias that happens to be a gerund
            "witnessing": "witness",  # gerund, plain stem
            "hoping": "hope",  # gerund, stem wants its `e` back
            "betrayed": "betray",  # past tense
            "goals": "goal",  # plural
        }
        for written, canonical in cases.items():
            with self.subTest(written=written):
                self.assertEqual(resolve(written), canonical)

    def test_a_word_it_cannot_place_is_handed_back_unchanged(self):
        self.assertEqual(resolve("flurbling"), "flurbling")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
