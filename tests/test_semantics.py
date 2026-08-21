"""Tests for the claims Catharsis actually makes.

Each of these is a property the language is supposed to have, rather than a
check that a particular number came out.  Where a number is asserted it is an
inequality between two runs, so retuning the field does not silently invalidate
the test.
"""

import unittest

from catharsis import run_source, to_dict
from catharsis.errors import CatharsisRuntimeError


class TestHistoryOverStatelessness(unittest.TestCase):
    def test_order_of_interactions_changes_the_outcome(self):
        # The same three utterances, in two orders.  Forgiving and then being
        # hurt again is not the same state as being hurt twice and forgiving.
        forgive_then_hurt = run_source(
            "a = agent\nb = agent\nlove a b 0.8\nbetray a b\nforgive b a\ntick 5\nbetray a b\ntick 5\n"
        )
        hurt_then_forgive = run_source(
            "a = agent\nb = agent\nlove a b 0.8\nbetray a b\ntick 5\nbetray a b\nforgive b a\ntick 5\n"
        )
        self.assertGreater(
            forgive_then_hurt.agents["b"].feels("resentment", "a"),
            hurt_then_forgive.agents["b"].feels("resentment", "a"),
        )
        self.assertFalse(forgive_then_hurt.agents["b"].memories[0].reconciled)
        self.assertTrue(hurt_then_forgive.agents["b"].memories[0].reconciled)

    def test_a_memory_keeps_acting_after_the_feeling_would_have_faded(self):
        remembered = run_source("a = agent\nb = agent\nbetray a b\ntick 40\n")
        # 40 ticks is long enough for a bare deposit of resentment to be gone.
        bare = run_source("a = agent\nb = agent\nresentment b a 0.5\ntick 40\n")
        self.assertGreater(
            remembered.agents["b"].feels("resentment", "a"),
            bare.agents["b"].feels("resentment", "a"),
        )


class TestDeclaration(unittest.TestCase):
    """`alice = agent`, `agent alice`, and `👤 alice` are one thing said three ways."""

    LONG = "alice = agent\nbob = agent\ncarol = agent\n"
    SHORT = "agent alice bob carol\n"
    GLYPH = "👤 alice bob carol\n"
    BODY = "love alice bob 0.9\njealousy carol alice 0.7\nbetray alice bob\ntick 8\n"

    def test_every_form_builds_the_same_world(self):
        worlds = [to_dict(run_source(head + self.BODY)) for head in (self.LONG, self.SHORT, self.GLYPH)]
        self.assertEqual(worlds[0], worlds[1])
        self.assertEqual(worlds[1], worlds[2])

    def test_declaration_order_is_preserved(self):
        world = run_source(self.SHORT)
        self.assertEqual(list(world.agents), ["alice", "bob", "carol"])

    def test_declaring_the_same_name_twice_is_an_error(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("agent alice bob\nagent bob\n")
        self.assertIn("already an agent", str(caught.exception))

    def test_an_agent_cannot_collide_with_a_group(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("group crew\nagent crew\n")
        self.assertIn("already a group", str(caught.exception))

    def test_the_forms_can_be_mixed(self):
        world = run_source("agent alice bob\ncarol = agent\n👤 dave\n")
        self.assertEqual(list(world.agents), ["alice", "bob", "carol", "dave"])


class TestForgiveness(unittest.TestCase):
    PROGRAM = (
        "alice = agent\nbob = agent\n"
        "love alice bob 0.8\nlove bob alice 0.8\ntrust bob alice 0.9\n"
        "betray alice bob\ntick 6\napology alice bob\ntick 4\n"
    )

    def test_forgiveness_is_not_forgetting(self):
        world = run_source(self.PROGRAM + "forgive bob alice\ntick 12\n")
        bob = world.agents["bob"]
        memories = bob.find_memories(claim="alice betrayed bob")
        self.assertEqual(len(memories), 1)
        self.assertTrue(memories[0].reconciled)
        self.assertGreater(memories[0].salience, 0.5)
        self.assertGreater(memories[0].confidence, 0.9)

    def test_forgiveness_disarms_hostility_but_leaves_grief(self):
        world = run_source(self.PROGRAM + "forgive bob alice\ntick 12\n")
        memory = world.agents["bob"].find_memories(claim="alice betrayed bob")[0]
        live = memory.rumination()
        self.assertNotIn("resentment", live)
        self.assertNotIn("anger", live)
        self.assertIn("grief", live)

    def test_trust_is_not_the_absence_of_history(self):
        world = run_source(self.PROGRAM + "forgive bob alice\ntrust bob alice\ntick 12\n")
        bond = world.agents["bob"].bond("alice")
        self.assertLess(bond.trust_ceiling, 1.0)
        self.assertLessEqual(round(bond.get("trust"), 6), round(bond.trust_ceiling, 6))
        self.assertGreater(bond.get("grief"), 0.05)

    def test_forgiving_lets_trust_recover_further_than_not_forgiving(self):
        forgiven = run_source(self.PROGRAM + "forgive bob alice\ntrust bob alice\ntick 12\n")
        withheld = run_source(self.PROGRAM + "trust bob alice\ntick 12\n")
        self.assertGreater(
            forgiven.agents["bob"].feels("trust", "alice"),
            withheld.agents["bob"].feels("trust", "alice"),
        )

    def test_an_apology_lands_in_proportion_to_receptivity(self):
        warm = run_source("a = agent\nb = agent\nlove b a 0.9\nhope b a 0.6\nbetray a b\napology a b\n")
        cold = run_source(
            "a = agent\nb = agent\nresentment b a 0.9\ndoubt b a 0.9\nbetray a b\napology a b\n"
        )
        self.assertGreater(warm.agents["b"].feels("hope", "a"), cold.agents["b"].feels("hope", "a"))


class TestReputation(unittest.TestCase):
    PROGRAM = (
        "alice = agent\nbob = agent\ncharlie = agent\ndiana = agent\n"
        "trust bob alice 0.8\n"
        "trust charlie diana 0.7\ntrust diana charlie 0.7\nlove diana charlie 0.4\n"
        "betray alice bob\nwitness charlie alice betraying bob\ntick 10\n"
    )

    def test_a_witness_is_affected_without_being_the_victim(self):
        world = run_source(self.PROGRAM)
        charlie = world.agents["charlie"]
        self.assertGreater(charlie.feels("doubt", "alice"), 0.1)
        self.assertEqual(charlie.find_memories(claim="alice betrayed bob")[0].kind, "witnessed")

    def test_reputation_reaches_someone_who_saw_nothing(self):
        world = run_source(self.PROGRAM)
        diana = world.agents["diana"]
        self.assertGreater(diana.feels("doubt", "alice"), 0.0)
        told = diana.find_memories(claim="alice betrayed bob")
        self.assertTrue(told, "diana should have heard about it")
        self.assertEqual(told[0].kind, "told")
        self.assertEqual(told[0].source, "charlie")

    def test_second_hand_is_weaker_than_first_hand(self):
        world = run_source(self.PROGRAM)
        victim = world.agents["bob"].feels("doubt", "alice")
        witness = world.agents["charlie"].feels("doubt", "alice")
        hearsay = world.agents["diana"].feels("doubt", "alice")
        self.assertGreater(victim, witness)
        self.assertGreater(witness, hearsay)

    def test_nothing_reaches_a_stranger_nobody_trusts(self):
        world = run_source(
            "alice = agent\nbob = agent\ncharlie = agent\n"
            "betray alice bob\nwitness charlie alice betraying bob\n"
            "eve = agent\ntick 10\n"
        )
        self.assertNotIn("alice", world.agents["eve"].bonds)


class TestMemory(unittest.TestCase):
    def test_recall_is_not_a_boolean(self):
        world = run_source(
            'a = agent\nremember a "the door was open"\n'
            'denial a "the door was open"\ndoubt a "the door was open" 0.6\n'
            'hope a "the door was open" 0.4\ntick 3\n'
        )
        memory = world.agents["a"].memories[0]
        self.assertGreater(memory.stances["affirm"], 0.0)
        self.assertGreater(memory.stances["deny"], 0.0)
        self.assertGreater(memory.contradiction_count, 0)
        self.assertEqual(memory.confidence_label, "disputed")

    def test_denial_suppresses_the_claim_and_keeps_the_feeling(self):
        world = run_source(
            'a = agent\nfear a 0.7\nremember a "the door was open"\ndenial a "the door was open"\ntick 8\n'
        )
        agent = world.agents["a"]
        memory = agent.memories[0]
        self.assertTrue(memory.suppressed)
        self.assertEqual(world.memory_tension(agent), 0.0)  # denial is not paying the cost
        self.assertGreater(agent.self_bond.get("fear"), 0.2)  # and the fear is still there

    def test_acceptance_collapses_and_charges_grief(self):
        source = (
            'a = agent\nremember a "the door was open"\n'
            'denial a "the door was open"\ndoubt a "the door was open" 0.5\ntick 3\n'
        )
        before = run_source(source)
        after = run_source(source + 'acceptance a "the door was open"\n')
        self.assertGreater(before.agents["a"].memories[0].contradiction_count, 0)
        self.assertEqual(after.agents["a"].memories[0].contradiction_count, 0)
        self.assertGreater(
            after.agents["a"].self_bond.get("grief"), before.agents["a"].self_bond.get("grief")
        )

    def test_recalling_makes_a_memory_heavier(self):
        quiet = run_source("a = agent\nb = agent\nbetray b a\ntick 6\n")
        rehearsed = run_source('a = agent\nb = agent\nbetray b a\ntick 3\nrecall a "b betrayed a"\ntick 3\n')
        self.assertGreater(rehearsed.agents["a"].memories[0].salience, quiet.agents["a"].memories[0].salience)


class TestContradiction(unittest.TestCase):
    SOURCE = (
        "a = agent\nb = agent\n"
        "love a b 0.8\nanger a b 0.6\ntrust a b 0.4\ndoubt a b 0.7\nhope a b 0.9\nfear a b 0.3\n"
    )

    def test_opposites_are_both_kept(self):
        world = run_source(self.SOURCE)
        bond = world.agents["a"].bond("b")
        for emotion in ("love", "anger", "trust", "doubt", "hope", "fear"):
            self.assertGreater(bond.get(emotion), 0.0)
        self.assertGreater(bond.tension, 1.0)

    def test_ambivalence_slows_an_agent_down(self):
        torn = run_source(self.SOURCE + "tick 6\n")
        clear = run_source("a = agent\nb = agent\nlove a b 0.8\nhope a b 0.9\ntick 6\n")
        torn_acts = [event for event in torn.log if event.kind == "act"]
        clear_acts = [event for event in clear.log if event.kind == "act"]
        self.assertGreater(len(clear_acts), len(torn_acts))

    def test_nothing_collapses_a_contradiction_on_its_own(self):
        world = run_source(self.SOURCE + "tick 10\n")
        self.assertGreater(world.agents["a"].bond("b").tension, 0.3)


class TestRegret(unittest.TestCase):
    def test_regret_keeps_the_untaken_branch_computable(self):
        world = run_source('a = agent\nchoice a "leave" "stay"\nregret a\ntick 5\n')
        branch = world.agents["a"].branches[0]
        self.assertEqual(branch.taken, "leave")
        self.assertEqual(branch.untaken, "stay")
        self.assertFalse(branch.closed)

    def test_regret_grows_when_the_life_you_are_in_gets_worse(self):
        good = run_source(
            'a = agent\nb = agent\nchoice a "leave"\nregret a\nlove a b 0.9\njoy a 0.8\ntick 10\n'
        )
        bad = run_source('a = agent\nchoice a "leave"\nregret a\nlonely a 0.8\nsadness a 0.8\ntick 10\n')
        self.assertGreater(bad.agents["a"].self_bond.get("regret"), good.agents["a"].self_bond.get("regret"))

    def test_acceptance_closes_the_branch(self):
        world = run_source('a = agent\nchoice a "leave"\nregret a\ntick 5\nacceptance a\ntick 2\n')
        self.assertTrue(world.agents["a"].branches[0].closed)

    def test_regretting_without_a_choice_is_an_error(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("a = agent\nregret a\n")
        self.assertIn("no choice to regret", str(caught.exception))


class TestNegotiation(unittest.TestCase):
    BASE = "alice = agent\nbob = agent\ngoal alice price 90\ngoal bob price 50\npropose alice bob\n"

    def test_emotion_decides_where_the_deal_lands(self):
        bob_afraid = run_source(self.BASE + "fear bob alice 0.7\npride alice 0.7\ntick 30\n")
        alice_afraid = run_source(self.BASE + "fear alice bob 0.7\npride bob 0.7\ntick 30\n")
        self.assertGreater(bob_afraid.negotiations[0].agreement, alice_afraid.negotiations[0].agreement)

    def test_an_evenly_matched_pair_lands_near_the_middle(self):
        # Near, but not exactly: `propose` puts hope on the proposer's side of
        # the edge, and hope is a yielding term, so opening the bargaining costs
        # Alice ground.  That is the model working, not a rounding error.
        world = run_source(self.BASE + "trust alice bob 0.5\ntrust bob alice 0.5\ntick 30\n")
        self.assertEqual(world.negotiations[0].status, "agreed")
        self.assertAlmostEqual(world.negotiations[0].agreement, 70.0, delta=3.0)
        self.assertLess(world.negotiations[0].agreement, 70.0)

    def test_a_deal_can_be_reached_and_still_cost_the_relationship(self):
        world = run_source(
            self.BASE + "fear bob alice 0.6\npride alice 0.8\nreject bob alice\nanger alice bob\ntick 30\n"
        )
        self.assertEqual(world.negotiations[0].status, "agreed")
        self.assertGreater(world.agents["bob"].feels("resentment", "alice"), 0.3)

    def test_two_immovable_parties_reach_no_deal(self):
        world = run_source(
            self.BASE + "pride alice 0.95\npride bob 0.95\n"
            "anger alice bob 0.9\nanger bob alice 0.9\n"
            "resentment alice bob 0.9\nresentment bob alice 0.9\ntick 30\n"
        )
        self.assertNotEqual(world.negotiations[0].status, "agreed")


class TestEmergence(unittest.TestCase):
    def test_a_shared_goal_can_be_met_without_anybody_organising_it(self):
        world = run_source(
            "group team\na = agent\nb = agent\nc = agent\n"
            'join a team\njoin b team\njoin c team\ngoal team "rescue"\n'
            "trust a b 0.7\ntrust b c 0.7\ntrust c a 0.4\nhope a 0.7\ntick 25\n"
        )
        self.assertIsNotNone(world.groups["team"].achieved_at)

    def test_the_same_group_fails_when_the_trust_graph_is_broken(self):
        world = run_source(
            "group team\na = agent\nb = agent\nc = agent\n"
            'join a team\njoin b team\njoin c team\ngoal team "rescue"\n'
            "doubt a b 0.7\ndoubt b c 0.7\ndoubt c a 0.7\nfear a 0.6\nfear b 0.6\ntick 25\n"
        )
        self.assertIsNone(world.groups["team"].achieved_at)
        self.assertLess(world.groups["team"].progress, 1.0)

    def test_loneliness_makes_an_agent_go_looking(self):
        world = run_source("a = agent\nb = agent\nlonely a 0.9\nhope a 0.5\ntick 6\n")
        self.assertIn("b", world.agents["a"].bonds)

    def test_being_asked_is_what_produces_giving(self):
        world = run_source(
            "a = agent\nb = agent\nhave a bread 6\nneed a bread 1\nneed b bread 3\ntrust b a 0.5\ntick 20\n"
        )
        self.assertGreater(world.agents["b"].resources.get("bread", 0.0), 0.0)
        self.assertGreater(world.agents["b"].feels("gratitude", "a"), 0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestRiskyResources(unittest.TestCase):
    """A capability is not a good: it is given on trust, and cannot be taken.

    These assert the mechanism rather than any date.  `examples/supply_chain.feel`
    reproduces the shape of a documented attack but runs about twice as fast as
    the real thing, and pinning a tick number here would be fitting constants to
    a single case.
    """

    SETUP = (
        "agent holder seeker\n"
        "have holder key 2\nneed holder key 1\nneed seeker key 1\n"
        "trust seeker holder 0.6\n"
    )

    @staticmethod
    def handover(world) -> int | None:
        for event in world.log:
            if "gave seeker key" in event.text:
                return event.tick
        return None

    def test_a_harmless_resource_is_handed_over_on_need_alone(self):
        world = run_source(self.SETUP + "tick 12\n")
        self.assertIsNotNone(self.handover(world))

    def test_a_risky_one_is_not(self):
        world = run_source(self.SETUP + "risk key 0.9\ntick 12\n")
        self.assertIsNone(self.handover(world), "a stranger should not be handed the keys")

    def test_but_generosity_over_time_opens_it(self):
        # Same risky resource, same threshold; the only difference is a history.
        patient = self.SETUP + "risk key 0.9\n" + ("gift seeker holder favour\ntick 1\n" * 10)
        world = run_source(patient)
        self.assertIsNotNone(self.handover(world))
        self.assertGreater(world.agents["holder"].feels("trust", "seeker"), 0.6)

    def test_the_riskier_it_is_the_longer_it_takes(self):
        def at(risk: float) -> int | None:
            source = self.SETUP + f"risk key {risk}\n" + ("gift seeker holder favour\ntick 1\n" * 14)
            return self.handover(run_source(source))

        cheap, dear = at(0.2), at(0.9)
        self.assertIsNotNone(cheap)
        self.assertIsNotNone(dear)
        self.assertLess(cheap, dear)

    def test_a_capability_cannot_simply_be_taken(self):
        # Bread can be taken by whoever wants it more.  A capability cannot: it
        # only exists because its holder confers it.  The holder here resents the
        # seeker, so giving is off the table and taking is the only route left.
        grabby = "\nresentment holder seeker 0.9\nangry seeker holder 0.9\npride seeker 0.9\ntick 15\n"
        takeable = run_source(self.SETUP + grabby)
        guarded = run_source(self.SETUP + "risk key 0.9" + grabby)
        self.assertTrue(any("took key" in e.text for e in takeable.log), "bread should be takeable")
        self.assertFalse(any("took key" in e.text for e in guarded.log))
        self.assertIsNone(self.handover(guarded), "and it was not given either")

    def test_being_short_of_one_thing_does_not_stop_you_giving_another(self):
        world = run_source(
            "agent holder seeker\n"
            "have holder bread 4\nneed holder bread 1\nneed seeker bread 2\n"
            "need holder sleep 8\nhave holder sleep 0\n"  # exhausted, but not of bread
            "trust holder seeker 0.5\ntick 10\n"
        )
        self.assertGreater(world.agents["seeker"].resources.get("bread", 0.0), 0.0)


class TestCommons(unittest.TestCase):
    """Ostrom's finding, as an assertion.

    Laboratory work on common-pool resources found that groups able to build
    relationships sustain the resource where atomised ones do not, and that the
    advantage *persists after the relationship-building stops*.  That second half
    is a claim about memory rather than incentives, which is why it is testable
    here at all: nothing in `examples/commons.feel` scores anybody's cooperation.
    """

    STOCK = (
        "group harbour\n"
        "agent north south east west\n"
        "join north harbour\njoin south harbour\njoin east harbour\njoin west harbour\n"
        "have north fish 3\nhave south fish 3\nhave east fish 1\nhave west fish 1\n"
        "need north fish 2\nneed south fish 2\nneed east fish 3\nneed west fish 3\n"
        'goal harbour "keep the rotation"\n'
    )
    NEIGHBOURS = (
        "trust north south 0.7\ntrust south north 0.7\n"
        "trust east west 0.65\ntrust west east 0.65\n"
        "trust north east 0.5\ntrust east north 0.5\n"
        "love south west 0.4\nlove west south 0.4\n"
    )

    @staticmethod
    def thefts(world) -> int:
        return sum(1 for event in world.log if "took fish" in event.text)

    @staticmethod
    def mean_trust(world) -> float:
        values = [bond.get("trust") for agent in world.agents.values() for bond in agent.others()]
        return sum(values) / len(values) if values else 0.0

    def test_neighbours_take_from_each_other_less_than_strangers_do(self):
        neighbours = run_source(self.STOCK + self.NEIGHBOURS + "tick 25\n")
        strangers = run_source(self.STOCK + "tick 25\n")
        self.assertLess(self.thefts(neighbours), self.thefts(strangers))
        self.assertEqual(self.thefts(neighbours), 0)

    def test_only_the_group_with_relationships_keeps_the_rotation(self):
        neighbours = run_source(self.STOCK + self.NEIGHBOURS + "tick 25\n")
        strangers = run_source(self.STOCK + "tick 25\n")
        self.assertIsNotNone(neighbours.groups["harbour"].achieved_at)
        self.assertIsNone(strangers.groups["harbour"].achieved_at)
        self.assertEqual(strangers.groups["harbour"].progress, 0.0)

    def test_the_emotional_layer_redistributes_rather_than_creating(self):
        # Worth being honest about what it does not do: the same fish exist in
        # both runs.  What changes is whether the shortfall is shared or taken.
        neighbours = run_source(self.STOCK + self.NEIGHBOURS + "tick 25\n")
        strangers = run_source(self.STOCK + "tick 25\n")

        def shortfall(world):
            return sum(
                max(0.0, agent.needs.get("fish", 0) - agent.resources.get("fish", 0))
                for agent in world.agents.values()
            )

        self.assertAlmostEqual(shortfall(neighbours), shortfall(strangers), places=6)

    def test_the_advantage_outlives_the_head_start_that_created_it(self):
        # The opening deposits decay; what sustains the difference afterwards is
        # the memory of having been given something.
        long_run = run_source(self.STOCK + self.NEIGHBOURS + "tick 60\n")
        strangers = run_source(self.STOCK + "tick 60\n")
        self.assertGreater(self.mean_trust(long_run), self.mean_trust(strangers))
        remembered = [
            memory
            for agent in long_run.agents.values()
            for memory in agent.memories
            if "gave" in memory.claim
        ]
        self.assertTrue(remembered, "the sharing should have left memories behind")
