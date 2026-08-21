import unittest

from catharsis import parse
from catharsis.ast import Declare, Utter
from catharsis.errors import LexError, ParseError


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
