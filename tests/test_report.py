"""Rendering state back out, and the labels the runtime puts on things.

These are the branches an ordinary example never reaches: a memory with nothing
left to push, an agent who remembers nothing, a negotiation that is still open
or has broken down, and the ends of the confidence scale.
"""

import unittest

from catharsis import run_source
from catharsis.entity import Agent, Bond, Memory
from catharsis.report import render_memories, render_world
from catharsis.world import World


class TestBond(unittest.TestCase):
    def test_a_self_loop_knows_it_is_one(self):
        self.assertTrue(Bond("alice", "alice").reflexive)
        self.assertFalse(Bond("alice", "bob").reflexive)

    def test_asking_for_a_bond_that_is_not_there(self):
        agent = Agent("alice")
        with self.assertRaises(KeyError):
            agent.bond("bob", create=False)
        self.assertNotIn("bob", agent.bonds)
        self.assertIsInstance(agent.bond("bob"), Bond)


class TestMemoryLabels(unittest.TestCase):
    def test_a_claim_with_no_stance_either_way_is_exactly_uncertain(self):
        # Not a boolean, and not a default of False: knowing nothing is 0.5.
        memory = Memory(claim="something happened", subject="alice")
        memory.stances.clear()
        self.assertEqual(memory.confidence, 0.5)
        self.assertEqual(memory.confidence_label, "uncertain")

    def test_the_bottom_of_the_confidence_scale(self):
        memory = Memory(claim="it happened", subject="alice")
        memory.stances.clear()
        memory.stances["deny"] = 1.0
        self.assertEqual(memory.confidence, 0.0)
        self.assertEqual(memory.confidence_label, "denied")

    def test_a_memory_about_nobody_imposes_no_ceiling(self):
        memory = Memory(claim="the harvest failed", subject="alice", about=None)
        memory.signature = {"grief": 0.9, "anger": 0.9}
        self.assertEqual(memory.ceiling(), 1.0)


class TestRendering(unittest.TestCase):
    def test_an_agent_who_remembers_nothing_says_so(self):
        world = World()
        agent = Agent("alice")
        self.assertIn("    nothing", render_memories(world, agent))

    def test_a_memory_that_has_stopped_pushing_still_shows_what_it_was(self):
        # A memory made only of hostile feeling, then reconciled: `rumination`
        # drops every axis, so there is nothing live to print -- but the memory
        # is still there and the report says what it was made of.
        world = World()
        agent = Agent("bob")
        memory = Memory(claim="alice betrayed bob", subject="bob", about="alice")
        memory.signature = {"anger": 0.8, "resentment": 0.6}
        memory.reconciled = True
        agent.memories.append(memory)
        lines = render_memories(world, agent)
        self.assertEqual(memory.rumination(), {})
        self.assertTrue(any("pushing nothing (signature:" in line for line in lines), "\n".join(lines))

    def test_an_open_negotiation_renders_both_positions(self):
        world = run_source(
            "agent alice bob\ngoal alice price 90\ngoal bob price 50\n"
            "pride alice 0.9\npride bob 0.9\nanger alice bob 0.8\nanger bob alice 0.8\n"
            "propose alice bob\ntick 2\n"
        )
        rendered = "\n".join(render_world(world))
        self.assertIn("negotiations:", rendered)
        self.assertIn("open: alice at", rendered)

    def test_an_impasse_renders_as_one(self):
        world = run_source(
            "agent alice bob\ngoal alice price 90\ngoal bob price 50\n"
            "pride alice 0.95\npride bob 0.95\n"
            "anger alice bob 0.9\nanger bob alice 0.9\n"
            "resentment alice bob 0.9\nresentment bob alice 0.9\n"
            "propose alice bob\ntick 60\n"
        )
        rendered = "\n".join(render_world(world))
        self.assertIn("impasse (tick", rendered)

    def test_a_group_is_rendered_with_the_world(self):
        world = run_source(
            "group crew\nagent alice bob\njoin alice crew\njoin bob crew\n"
            'goal crew "the harvest"\nhope alice 0.8\ntrust alice bob 0.7\ntick 5\n'
        )
        rendered = "\n".join(render_world(world))
        self.assertIn("crew", rendered)
        self.assertIn("the harvest", rendered)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
