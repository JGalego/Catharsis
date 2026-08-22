"""feel sort: sorting integers out of envy and shame.

The algorithm is in ``examples/sort.feel``.  It is two ticks long and uses no
actions at all: ``_needs`` deposits envy on edge i->j exactly when v_j > v_i,
and ``SPILL``'s ``envy -> shame`` sums those edges into self-regard.  Rank is
how many people you have made feel small.

These tests check both readouts -- the envy fan-out, which is the comparison
matrix, and the self-shame, which is its row sum -- and they pin the three
preconditions by breaking each one in turn.
"""

import random
import unittest
from pathlib import Path

from catharsis import run_source
from catharsis.field import DECAY

#: Spill rate x envy rate x one tick of decay before the spill reads it.
UNIT = 0.02 * 0.07 * (1.0 - DECAY["envy"])

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sort.feel"


def program(values, *, need=1_000_000, ticks=2, risky=True):
    """The sort, for an arbitrary sequence.  This is what the example does by hand."""
    names = [f"x{i}" for i in range(len(values))]
    lines = [f"agent {' '.join(names)}"]
    if risky:
        lines.append("risk worth 0.9")
    for name, value in zip(names, values, strict=True):
        lines += [f"have {name} worth {value}", f"need {name} worth {need}"]
    lines += [f"curiosity {a} {b} 0.01" for a in names for b in names if a != b]
    lines.append(f"tick {ticks}")
    return "\n".join(lines) + "\n", names


def sort(values, **kwargs):
    """Run it, and return (world, names, the sequence in shame order)."""
    source, names = program(values, **kwargs)
    world = run_source(source)
    order = sorted(names, key=lambda name: -world.agents[name].self_bond.get("shame"))
    return world, names, [values[names.index(name)] for name in order]


class TestItSorts(unittest.TestCase):
    def test_a_handful_of_shapes(self):
        cases = {
            "random": [23, 5, 91, 42, 5, 68, 17, 34],
            "already sorted": list(range(12)),
            "reversed": list(range(12))[::-1],
            "all equal": [5, 5, 5, 5],
            "duplicates": [3, 1, 3, 1, 2, 2],
            "negatives": [-4, 2, -9, 7, 0],
            "two": [1, 0],
            "one": [7],
        }
        for label, values in cases.items():
            with self.subTest(label):
                _, _, result = sort(values)
                self.assertEqual(result, sorted(values))

    def test_random_sequences(self):
        rng = random.Random(20260822)
        for size in (2, 3, 7, 16, 31):
            with self.subTest(size=size):
                values = [rng.randint(-500, 500) for _ in range(size)]
                _, _, result = sort(values)
                self.assertEqual(result, sorted(values))

    def test_the_input_is_never_touched(self):
        # `risk` is what makes this true: envy forms, theft cannot.
        values = [9, 2, 40, 15, 3]
        world, names, _ = sort(values)
        held = [int(world.agents[name].resources["worth"]) for name in names]
        self.assertEqual(held, values)
        self.assertEqual([e.text for e in world.log if e.kind == "act"], [])


class TestTheTwoReadouts(unittest.TestCase):
    """The envy fan-out is the comparison matrix; shame is its row sum."""

    VALUES = [23, 5, 91, 42, 5, 68, 17, 34]

    def test_the_fan_out_is_exactly_the_comparison_matrix(self):
        world, names, _ = sort(self.VALUES)
        for i, name in enumerate(names):
            agent = world.agents[name]
            envied = {bond.target for bond in agent.others() if bond.get("envy") > 0.0}
            expected = {names[j] for j, other in enumerate(self.VALUES) if other > self.VALUES[i]}
            self.assertEqual(envied, expected, f"{name} envies the wrong people")

    def test_shame_is_the_row_sum_and_the_step_is_exact(self):
        world, names, _ = sort(self.VALUES)
        for i, name in enumerate(names):
            corank = sum(1 for other in self.VALUES if other > self.VALUES[i])
            self.assertAlmostEqual(world.agents[name].self_bond.get("shame"), UNIT * corank, places=6)

    def test_ties_land_on_the_same_number(self):
        # Equal values cannot envy each other, so they deposit nothing on each
        # other and are genuinely indistinguishable rather than ordered by luck.
        world, names, _ = sort([4, 9, 4, 9])
        shame = [world.agents[name].self_bond.get("shame") for name in names]
        self.assertEqual(shame[0], shame[2])
        self.assertEqual(shame[1], shame[3])
        self.assertGreater(shame[0], shame[1])

    def test_the_maximum_envies_nobody(self):
        world, names, _ = sort([3, 100, 7])
        self.assertEqual(world.agents["x1"].self_bond.get("shame"), 0.0)
        self.assertEqual([b for b in world.agents["x1"].others() if b.get("envy") > 0], [])


class TestThePreconditions(unittest.TestCase):
    """Each one broken in turn, so the example's warnings are checked rather than asserted."""

    def test_without_risk_the_agents_eat_the_input(self):
        values = [9, 2, 40, 15, 3]
        world, names, _ = sort(values, risky=False)
        held = [int(world.agents[name].resources["worth"]) for name in names]
        self.assertNotEqual(held, values, "nothing was stolen, so `risk` is doing nothing")
        self.assertTrue(any(e.kind == "act" for e in world.log))

    def test_a_need_smaller_than_a_value_breaks_the_order(self):
        # `_needs` skips any agent whose deficit is <= 0, so an agent holding
        # more than it needs never envies anyone and ties with the true maximum.
        _, _, result = sort([5, 50, 500], need=100)
        self.assertEqual(result, [5, 500, 50])

    def test_one_tick_is_not_enough(self):
        # Tick 1 lays the envy; the spill that counts it happens on tick 2.
        world, names, _ = sort([1, 2, 3], ticks=1)
        self.assertEqual([world.agents[name].self_bond.get("shame") for name in names], [0.0, 0.0, 0.0])

    def test_the_answer_has_a_window(self):
        # `_needs` also deposits sadness every tick.  Around tick 19 that is
        # enough for `withdraw` to clear the action threshold, and after that the
        # agents are reacting to the comparison rather than performing it.
        values = [40, 12, 87, 3, 61, 25, 99, 7]
        for ticks in (2, 10, 18):
            with self.subTest(ticks=ticks):
                self.assertEqual(sort(values, ticks=ticks)[2], sorted(values))
        late, _, _ = sort(values, ticks=40)
        self.assertTrue(any(e.kind == "act" for e in late.log), "nobody ever reacted, so there is no window")


class TestTheCeiling(unittest.TestCase):
    def test_the_step_does_not_depend_on_n(self):
        # Which is why the sort is exact rather than merely monotone: adjacent
        # ranks are always UNIT apart, however long the sequence.
        for size in (5, 20, 60):
            with self.subTest(size=size):
                world, names, _ = sort(list(range(size)))
                shame = sorted((world.agents[name].self_bond.get("shame") for name in names), reverse=True)
                gaps = [a - b for a, b in zip(shame, shame[1:], strict=False)]
                for gap in gaps:
                    self.assertAlmostEqual(gap, UNIT, places=6)

    def test_where_it_would_run_out(self):
        """Shame is clamped at 1.0, so the sort has a length limit.

        Not exercised directly -- a complete graph on 760 agents is ~577k
        statements -- but it follows from the step being constant, which the
        test above measures.
        """
        self.assertAlmostEqual(UNIT, 0.001316, places=6)
        self.assertEqual(int(1.0 / UNIT) + 1, 760)


class TestTheExample(unittest.TestCase):
    def test_the_shipped_example_sorts_what_it_says_it_sorts(self):
        world = run_source(EXAMPLE.read_text(), str(EXAMPLE))
        rows = sorted(
            ((agent.self_bond.get("shame"), agent.resources["worth"]) for agent in world.agents.values()),
            reverse=True,
        )
        self.assertEqual([int(worth) for _, worth in rows], [5, 5, 17, 23, 34, 42, 68, 91])
        self.assertEqual([e.text for e in world.log if e.kind == "act"], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
