"""The statement forms and guards the examples never happen to reach.

Two kinds of thing live here.  Statements whose less-common spelling nothing in
``examples/`` uses -- a goal that is a phrase rather than a number, a recall that
finds nothing, a second visit to the same regret -- and the defensive guards
inside actions, which are called directly because the preconditions that select
those actions already rule the guard out.
"""

import unittest

from catharsis import run_source
from catharsis.actions import ACTIONS
from catharsis.entity import Agent
from catharsis.errors import CatharsisRuntimeError
from catharsis.parser import parse
from catharsis.vocabulary import VOCABULARY
from catharsis.world import World


def world_of(source: str) -> World:
    lines: list[str] = []
    world = World(sink=lines.append)
    world.run(parse(source))
    world.output = lines
    return world


class TestRejections(unittest.TestCase):
    def test_a_tick_must_go_forward(self):
        for count in ("0", "-3"):
            with self.subTest(count=count), self.assertRaises(CatharsisRuntimeError) as caught:
                run_source(f"agent alice\ntick {count}\n")
            self.assertIn("positive number of steps", str(caught.exception))

    def test_a_group_cannot_share_a_name_with_an_agent(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("agent alice\ngroup alice\n")
        self.assertIn("already an agent", str(caught.exception))

    def test_only_real_events_can_be_witnessed(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("agent alice bob charlie\nwitness charlie alice flurbling bob\n")
        self.assertIn("is not something that can be witnessed", str(caught.exception))

    def test_you_cannot_accept_something_you_never_knew(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source('agent alice\nacceptance alice "the door was open"\n')
        self.assertIn("to accept", str(caught.exception))


class TestGoals(unittest.TestCase):
    def test_a_goal_can_be_a_phrase_rather_than_a_number(self):
        world = run_source('agent alice\ngoal alice "to be forgiven"\n')
        self.assertIn("to be forgiven", world.agents["alice"].commitments)
        self.assertEqual(world.agents["alice"].goals, {})

    def test_a_named_phrase_keeps_its_dimension(self):
        world = run_source('agent alice\ngoal alice work "a good harvest"\n')
        self.assertIn("work:a good harvest", world.agents["alice"].commitments)


class TestClaims(unittest.TestCase):
    def test_doubting_something_you_have_no_memory_of_creates_the_memory(self):
        # A stance on a claim is a stance on whether it happened, so there has
        # to be a claim to hold it.
        world = run_source('agent alice\ndoubt alice "the door was open"\n')
        memories = world.agents["alice"].find_memories(claim="the door was open")
        self.assertEqual(len(memories), 1)
        self.assertGreater(memories[0].stances.get("doubt", 0.0), 0.0)

    def test_denying_something_you_have_no_memory_of_does_the_same(self):
        world = run_source('agent alice\ndenial alice "it happened"\n')
        memories = world.agents["alice"].find_memories(claim="it happened")
        self.assertEqual(len(memories), 1)
        self.assertTrue(memories[0].suppressed)


class TestRecall(unittest.TestCase):
    def test_recall_with_no_claim_prints_everything(self):
        world = world_of("agent alice bob\nbetray alice bob\nrecall bob\n")
        self.assertIn("bob remembers:", "\n".join(world.output))

    def test_recall_of_something_that_was_never_there(self):
        world = world_of('agent alice\nrecall alice "the door was open"\n')
        self.assertIn('alice has no memory of "the door was open"', "\n".join(world.output))
        self.assertTrue(any(event.kind == "recall" for event in world.log))


class TestRemember(unittest.TestCase):
    def test_a_memory_about_somebody_carries_that_edge_into_its_signature(self):
        world = run_source(
            "agent alice bob\nanger alice bob 0.8\nresentment alice bob 0.6\n"
            'pride alice 0.5\nremember alice "the argument" bob\n'
        )
        memory = world.agents["alice"].find_memories(claim="the argument")[0]
        self.assertEqual(memory.about, "bob")
        # Half the self-regard and 60% of the edge toward bob.
        self.assertGreater(memory.signature.get("anger", 0.0), 0.0)
        self.assertGreater(memory.signature.get("pride", 0.0), 0.0)


class TestRegret(unittest.TestCase):
    def test_going_back_to_the_same_road_again_deepens_it(self):
        world = run_source('agent alice\nchoice alice "stayed" "left"\nregret alice\ntick 3\nregret alice\n')
        branches = world.agents["alice"].branches
        self.assertEqual(len(branches), 1, "a second visit forked instead of returning")
        self.assertEqual(branches[0].visits, 2)
        self.assertFalse(branches[0].closed)
        self.assertTrue(any("again (visit 2)" in event.text for event in world.log))

    def test_regret_needs_a_road_not_taken(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("agent alice\nregret alice\n")
        self.assertIn("no choice to regret", str(caught.exception))

    def test_regret_aimed_at_a_claim_is_a_stance_not_a_fork(self):
        # `regret` is category "emotion", so the claim form takes the same path
        # as `doubt alice "the door was open"`.
        world = run_source('agent alice\nregret alice "the door was open"\n')
        self.assertEqual(world.agents["alice"].branches, [])
        self.assertTrue(world.agents["alice"].find_memories(claim="the door was open"))


class TestBargaining(unittest.TestCase):
    def test_an_offer_with_nothing_measurable_in_it(self):
        world = run_source("agent alice bob\npropose alice bob\n")
        self.assertEqual(world.negotiations, [])
        self.assertTrue(any("nothing measurable" in event.text for event in world.log))
        self.assertTrue(world.agents["bob"].find_memories(claim="alice made an offer to bob"))

    def test_proposing_twice_over_the_same_thing_opens_one_negotiation(self):
        world = run_source(
            "agent alice bob\ngoal alice price 90\ngoal bob price 50\npropose alice bob\npropose alice bob\n"
        )
        self.assertEqual(len(world.negotiations), 1)

    def test_agreeing_with_nothing_on_the_table(self):
        world = run_source("agent alice bob\nagree alice bob\n")
        self.assertTrue(any("nothing on the table" in event.text for event in world.log))

    def test_rejecting_counts_a_round(self):
        world = run_source(
            "agent alice bob\ngoal alice price 90\ngoal bob price 50\npropose alice bob\nreject bob alice\n"
        )
        self.assertEqual(world.negotiations[0].rounds, 1)

    def test_rejecting_when_nothing_is_open(self):
        world = run_source("agent alice bob\nreject bob alice\n")
        self.assertTrue(any(event.kind == "reject" for event in world.log))


class TestObserve(unittest.TestCase):
    def test_observing_a_group_by_name(self):
        world = world_of(
            "group crew\nagent alice bob\njoin alice crew\njoin bob crew\n"
            'goal crew "the harvest"\nobserve crew\n'
        )
        self.assertIn("crew", "\n".join(world.output))
        self.assertIn("the harvest", "\n".join(world.output))

    def test_joining_a_group_that_was_never_declared(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("agent alice\njoin alice crew\n")
        self.assertIn("no group named 'crew'", str(caught.exception))

    def test_a_temperament_has_to_be_an_emotion(self):
        with self.assertRaises(CatharsisRuntimeError) as caught:
            run_source("agent alice\ntrait alice patience 0.8\n")
        self.assertIn("is not an emotion", str(caught.exception))


class TestNamedBetrayal(unittest.TestCase):
    def test_a_betrayal_can_say_what_it_was(self):
        # The claim renames the memories both sides just laid down, so the
        # grievance is about a thing rather than about the word "betray".
        world = run_source('agent alice bob\nbetray alice bob "she told them where he was"\n')
        for name in ("alice", "bob"):
            claims = [memory.claim for memory in world.agents[name].memories]
            self.assertIn("she told them where he was", claims, name)
            self.assertNotIn("alice betrayed bob", claims, name)


class TestRememberEverything(unittest.TestCase):
    def test_remember_with_no_claim_prints_what_is_there(self):
        world = world_of("agent alice bob\nbetray alice bob\nremember bob\n")
        self.assertIn("bob remembers:", "\n".join(world.output))


class TestNegotiationBookkeeping(unittest.TestCase):
    OPEN = (
        "agent alice bob\ngoal alice price 90\ngoal bob price 50\n"
        "trust alice bob 0.6\ntrust bob alice 0.6\npropose alice bob\n"
    )

    def test_agreeing_settles_what_is_on_the_table(self):
        world = run_source(self.OPEN + "tick 3\nagree alice bob\n")
        self.assertEqual(world.negotiations[0].status, "agreed")
        self.assertTrue(any("settled price" in event.text for event in world.log))

    def test_a_settled_negotiation_is_skipped_when_looking_for_an_open_one(self):
        world = run_source(self.OPEN + "tick 3\nagree alice bob\nreject bob alice\n")
        # The reject found nothing open, so it counted no round on the closed one.
        self.assertEqual(world.negotiations[0].status, "agreed")

    def test_agreeing_leaves_somebody_elses_talks_alone(self):
        world = run_source(
            "agent alice bob carol dave\n"
            "goal alice price 90\ngoal bob price 50\n"
            "goal carol rent 400\ngoal dave rent 100\n"
            "propose alice bob\npropose carol dave\ntick 2\nagree alice bob\n"
        )
        by_pair = {frozenset((n.left, n.right)): n for n in world.negotiations}
        self.assertEqual(by_pair[frozenset(("alice", "bob"))].status, "agreed")
        self.assertEqual(by_pair[frozenset(("carol", "dave"))].status, "open")

    def test_somebody_elses_negotiation_is_not_yours_to_reject(self):
        world = run_source(
            "agent alice bob carol\n"
            "goal alice price 90\ngoal bob price 50\ngoal carol price 70\n"
            "propose alice bob\nreject carol alice\n"
        )
        self.assertEqual(len(world.negotiations), 1)
        self.assertEqual(world.negotiations[0].rounds, 0)

    def test_talks_break_off_in_feeling_rather_than_in_patience(self):
        world = run_source(
            "agent alice bob\ngoal alice price 1000\ngoal bob price 0\n"
            "anger alice bob 0.95\nanger bob alice 0.95\n"
            "resentment alice bob 0.95\nresentment bob alice 0.95\n"
            "propose alice bob\ntick 200\n"
        )
        self.assertEqual(world.negotiations[0].status, "impasse")
        self.assertTrue(any("broke off talks" in event.text for event in world.log))


class TestPatienceIsNeverNeeded(unittest.TestCase):
    """Why the 60-round limit in `_negotiate` carries a `pragma: no cover`.

    Conceding deposits sadness on whoever gave more, and sadness is a term in
    `yielding`, so each round makes the next concession larger.  Bargaining wears
    people down.  Talks therefore accelerate toward agreement -- or collapse in
    feeling -- and never simply grind on.
    """

    STUBBORN = (
        "agent alice bob\ngoal alice price 1000\ngoal bob price 0\n"
        "trait alice pride 1.0\ntrait bob pride 1.0\npride alice 1.0\npride bob 1.0\n"
        "propose alice bob\n"
    )

    def test_the_concession_rate_only_ever_climbs(self):
        world = World()
        world.run(parse(self.STUBBORN))
        alice, bob = world.agents["alice"], world.agents["bob"]
        rates = []
        for _ in range(12):
            world.step()
            rates.append(world._concession(alice, bob) + world._concession(bob, alice))
        self.assertGreater(rates[-1], rates[0], "bargaining did not wear them down")
        self.assertGreater(alice.self_bond.get("sadness"), 0.0)

    def test_even_maximal_stubbornness_settles_well_inside_sixty_rounds(self):
        world = run_source(self.STUBBORN + "tick 400\n")
        negotiation = world.negotiations[0]
        self.assertEqual(negotiation.status, "agreed")
        self.assertLess(negotiation.rounds, 60)


class TestSeeking(unittest.TestCase):
    def test_a_stranger_is_chosen_through_the_friends_who_know_them(self):
        # `warmth` scores each stranger by how warmly the people you trust feel
        # about them, so an introduction beats a cold approach.
        world = run_source(
            "agent alice bob carol dave\n"
            "trust alice bob 0.9\nlove alice bob 0.8\n"
            "love bob carol 0.9\ntrust bob carol 0.9\n"
            "loneliness alice 0.9\nhope alice 0.6\ncuriosity alice 0.5\n"
        )
        alice = world.agents["alice"]
        self.assertNotIn("carol", alice.bonds)
        world._act_seek(alice, alice)
        self.assertIn("carol", alice.bonds)
        self.assertTrue(any("sought out carol" in event.text for event in world.log))


class TestActionGuards(unittest.TestCase):
    """Called directly: the preconditions that select these already rule the guard out."""

    def pair(self) -> tuple[World, Agent, Agent]:
        world = run_source("agent alice bob\nlove alice bob 0.4\n")
        return world, world.agents["alice"], world.agents["bob"]

    def test_giving_what_nobody_is_short_of(self):
        world, alice, bob = self.pair()
        before = dict(alice.resources)
        world._act_give(alice, bob)
        self.assertEqual(alice.resources, before)
        self.assertFalse(any("gave" in event.text for event in world.log))

    def test_confiding_with_nothing_to_confide(self):
        world, alice, bob = self.pair()
        world._act_confide(alice, bob)
        self.assertEqual(bob.memories, [])

    def test_seeking_when_there_are_no_strangers_left(self):
        world, alice, bob = self.pair()
        world._act_seek(alice, alice)
        self.assertFalse(any("sought out" in event.text for event in world.log))

    def test_brooding_with_nothing_to_brood_on(self):
        world, alice, _ = self.pair()
        world._act_brood(alice, alice)
        self.assertFalse(any("over again" in event.text for event in world.log))

    def test_contributing_when_there_is_no_will_to_do_it(self):
        world = run_source(
            "group crew\nagent alice bob\njoin alice crew\njoin bob crew\n"
            'goal crew "the harvest"\nfear alice 0.9\ndoubt alice bob 0.9\n'
        )
        alice = world.agents["alice"]
        world._act_contribute(alice, alice)
        self.assertEqual(world.groups["crew"].progress, 0.0)


class TestUnreachableEntities(unittest.TestCase):
    """A bond can name someone who is not there; nothing should fall over.

    No statement produces this -- every bond is created toward a name the
    runtime has already validated -- so it is built by hand, which is the only
    way to exercise the guards that assume it might happen anyway.
    """

    def test_a_bond_to_a_name_that_is_not_an_agent_is_stepped_over(self):
        world = run_source("agent alice bob\nlove alice bob 0.6\ntrust alice bob 0.6\n")
        world.agents["alice"].bond("ghost").add("trust", 0.9)
        world.step()
        self.assertNotIn("ghost", world.agents)
        self.assertFalse(any("ghost" in event.text for event in world.log))


class TestPressure(unittest.TestCase):
    def test_giving_can_be_scored_even_when_there_is_nothing_to_give(self):
        """`own_need` is keyed on the resource being handed over.

        When there is no such resource the key has nothing to divide by, and the
        guard returns 0.0 rather than inventing an inhibition.  `can_give`
        already rules this combination out, so `_pressure` is called directly.
        """
        give = next(action for action in ACTIONS if action.name == "give")
        empty = run_source("agent alice bob\nlove alice bob 0.5\ntrust alice bob 0.5\n")
        alice, bob = empty.agents["alice"], empty.agents["bob"]
        self.assertIsNone(empty._giveable_resource(alice, bob))
        self.assertFalse(empty._precondition(give, alice, bob))

        scored = empty._pressure(give, alice, bob)
        # The same feelings, with a shortfall that `give` could actually meet:
        # only `their_need` moves, so `own_need` contributed nothing above.
        stocked = run_source(
            "agent alice bob\nlove alice bob 0.5\ntrust alice bob 0.5\n"
            "have alice bread 5\nneed alice bread 0\nneed bob bread 3\n"
        )
        self.assertTrue(stocked._precondition(give, stocked.agents["alice"], stocked.agents["bob"]))
        self.assertGreater(stocked._pressure(give, stocked.agents["alice"], stocked.agents["bob"]), scored)


class TestGroups(unittest.TestCase):
    def test_a_group_with_no_goal_is_nothing_to_contribute_to(self):
        world = run_source("group crew\nagent alice\njoin alice crew\nhope alice 0.9\npride alice 0.9\n")
        world._act_contribute(world.agents["alice"], world.agents["alice"])
        self.assertEqual(world.groups["crew"].progress, 0.0)
        self.assertFalse(any("worked toward" in event.text for event in world.log))


class TestVocabularyInvariants(unittest.TestCase):
    def test_a_memory_on_b_requires_b(self):
        """The guard in `_apply_memories` has no path, and this is why.

        If an entry ever lays a memory on the second party while leaving that
        party optional, this fails -- and the `pragma: no cover` on that guard
        stops being honest.
        """
        for name, spec in VOCABULARY.items():
            holders = {memory.holder for memory in getattr(spec, "memories", ()) or ()}
            if "b" not in holders:
                continue
            with self.subTest(utterance=name):
                self.assertGreaterEqual(len(spec.params), 2, f"{name} has no second party")
                self.assertEqual(spec.params[1], "agent", f"{name} makes its second party optional")


class TestImitation(unittest.TestCase):
    def test_envy_borrows_a_disposition(self):
        world = run_source(
            "agent alice bob\ntrait bob curiosity 0.8\nenvy alice bob 0.9\ncuriosity alice bob 0.5\ntick 3\n"
        )
        self.assertIn("curiosity", world.agents["alice"].traits)
        self.assertTrue(any("a disposition to curiosity" in e.text for e in world.log))

    def test_and_a_goal_when_there_is_no_disposition_to_take(self):
        world = run_source(
            "agent alice bob\ngoal bob price 60\nenvy alice bob 0.9\ncuriosity alice bob 0.5\ntick 3\n"
        )
        self.assertIn("price", world.agents["alice"].goals)
        self.assertTrue(any("a goal about price" in e.text for e in world.log))

    def test_there_is_nothing_left_to_copy(self):
        world = run_source("agent alice bob\nenvy alice bob 0.9\ncuriosity alice bob 0.5\ntick 3\n")
        world._act_imitate(world.agents["alice"], world.agents["bob"])
        self.assertFalse(any("took a" in e.text for e in world.log))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
