"""Tests for the field itself: decay, coupling, tension, saturation."""

import unittest

from catharsis import run_source
from catharsis.entity import Bond
from catharsis.field import DECAY, EMOTIONS, MEMORY_HOLD, contradictions, jitter, tension


class TestCharge(unittest.TestCase):
    def test_deposits_saturate_instead_of_clipping(self):
        bond = Bond("a", "b")
        for _ in range(20):
            bond.add("love", 0.5)
        self.assertLess(bond.get("love"), 1.0)
        self.assertGreater(bond.get("love"), 0.99)

    def test_withdrawal_is_proportional_and_cannot_go_negative(self):
        bond = Bond("a", "b")
        bond.add("trust", 0.4)
        bond.add("trust", -2.0)
        self.assertEqual(bond.get("trust"), 0.0)

    def test_tension_is_the_overlap_of_antagonists(self):
        self.assertAlmostEqual(tension({"love": 0.8, "anger": 0.6}), 0.6)
        self.assertAlmostEqual(tension({"love": 0.8}), 0.0)
        self.assertAlmostEqual(tension({"trust": 0.5, "doubt": 0.9}), 0.5)

    def test_contradictions_are_reported_strongest_first(self):
        found = contradictions({"love": 0.9, "anger": 0.7, "trust": 0.4, "doubt": 0.3})
        self.assertEqual(found[0][:2], ("love", "anger"))
        self.assertEqual(found[1][:2], ("trust", "doubt"))


class TestTables(unittest.TestCase):
    def test_every_emotion_has_a_decay_rate(self):
        self.assertEqual(set(DECAY), set(EMOTIONS))

    def test_slow_emotions_are_the_ones_memory_sustains(self):
        self.assertGreater(MEMORY_HOLD["grief"], MEMORY_HOLD["anger"])
        self.assertGreater(MEMORY_HOLD["resentment"], MEMORY_HOLD["anger"])


class TestDeterminism(unittest.TestCase):
    SOURCE = """
    alice = agent
    bob = agent
    charlie = agent
    love alice bob 0.8
    jealousy charlie bob 0.7
    betray alice bob
    witness charlie alice betraying bob
    tick 15
    """

    def test_jitter_is_content_addressed(self):
        self.assertEqual(jitter("alice", "bob", 3), jitter("alice", "bob", 3))
        self.assertNotEqual(jitter("alice", "bob", 3), jitter("alice", "bob", 4))
        self.assertTrue(0.0 <= jitter("x") < 1.0)

    def test_the_same_program_gives_the_same_world(self):
        from catharsis import to_dict

        first = to_dict(run_source(self.SOURCE))
        second = to_dict(run_source(self.SOURCE))
        self.assertEqual(first, second)

    def test_coupling_turns_a_deposit_into_consequences(self):
        # Nothing mentions trust; love is what produces it.
        world = run_source("alice = agent\nbob = agent\nlove alice bob 0.9\ntick 10\n")
        self.assertGreater(world.agents["alice"].feels("trust", "bob"), 0.2)

    def test_decay_is_not_uniform(self):
        world = run_source("alice = agent\nanger alice 0.9\ngrief alice 0.9\ntick 20\n")
        me = world.agents["alice"].self_bond
        self.assertLess(me.get("anger"), me.get("grief"))


def load_tests(loader, tests, ignore):
    """Run the doctest in the package docstring as part of the suite."""
    import doctest

    import catharsis

    tests.addTests(doctest.DocTestSuite(catharsis))
    return tests


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
