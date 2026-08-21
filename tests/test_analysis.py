"""Catharsis as a dynamical system.

The load-bearing distinction here is between the spectral radius and the
reachable growth.  Charges cannot be negative, so an eigenvector with a negative
component names a state the runtime has no way to be in, and the eigenvalue that
goes with it describes an instability nothing can reach.
"""

import unittest

from catharsis import run_source
from catharsis.analysis import (
    dominant_mode,
    eigenvalues,
    feasible_growth,
    linear_operator,
    portrait,
    runtime_bifurcation,
    spectrum,
    trajectory,
)
from catharsis.field import COUPLING, DECAY, EMOTIONS, SPILL
from catharsis.parser import parse
from catharsis.world import World


class TestOperator(unittest.TestCase):
    def test_the_matrix_is_the_tick(self):
        matrix = linear_operator(("trust", "doubt"))
        self.assertAlmostEqual(matrix[0][0], 1 - DECAY["trust"])
        self.assertAlmostEqual(matrix[1][1], 1 - DECAY["doubt"])
        expected = next(r for s, t, r in COUPLING if s == "doubt" and t == "trust")
        self.assertAlmostEqual(matrix[0][1], expected)

    def test_a_restriction_is_a_projection_not_a_different_model(self):
        full = linear_operator(EMOTIONS)
        index = {name: i for i, name in enumerate(EMOTIONS)}
        part = linear_operator(("love", "trust"))
        for i, a in enumerate(("love", "trust")):
            for j, b in enumerate(("love", "trust")):
                self.assertAlmostEqual(part[i][j], full[index[a]][index[b]])

    def test_the_operator_matches_the_field_when_nobody_acts(self):
        # Small charges: below the threshold where anyone reaches out, so the
        # tick is the field and nothing else.  The remaining error is the
        # saturation in Bond.add, which is second order in the charge.
        world = run_source("agent a b\nlove a b 0.05\ntrust a b 0.04\ntick 1\n")
        self.assertFalse(any(event.kind == "act" for event in world.log))
        bond = world.agents["a"].bond("b")
        matrix = linear_operator(("love", "trust"))
        self.assertAlmostEqual(bond.get("love"), matrix[0][0] * 0.05 + matrix[0][1] * 0.04, places=3)
        self.assertAlmostEqual(bond.get("trust"), matrix[1][0] * 0.05 + matrix[1][1] * 0.04, places=3)

    def test_the_operator_is_the_field_and_not_the_action_layer(self):
        # The same start, scaled up past the point where `a` reaches out.  The
        # runtime now runs ahead of the matrix, and that gap *is* the action
        # layer -- which is why `spectrum` predicts tendencies, not trajectories.
        world = run_source("agent a b\nlove a b 0.5\ntrust a b 0.4\ntick 1\n")
        self.assertTrue(any(event.kind == "act" for event in world.log))
        matrix = linear_operator(("love", "trust"))
        predicted = matrix[0][0] * 0.5 + matrix[0][1] * 0.4
        self.assertGreater(world.agents["a"].bond("b").get("love"), predicted)


class TestEigen(unittest.TestCase):
    def test_a_known_two_by_two(self):
        values = eigenvalues([[2.0, 0.0], [0.0, 3.0]])
        self.assertAlmostEqual(abs(values[0]), 3.0, places=6)
        self.assertAlmostEqual(abs(values[1]), 2.0, places=6)

    def test_a_rotation_comes_out_complex(self):
        values = eigenvalues([[0.0, -1.0], [1.0, 0.0]])
        self.assertTrue(all(abs(abs(z) - 1.0) < 1e-6 for z in values))
        self.assertTrue(any(abs(z.imag) > 0.5 for z in values))

    def test_the_count_is_right(self):
        self.assertEqual(len(eigenvalues(linear_operator(EMOTIONS))), len(EMOTIONS))

    def test_power_iteration_agrees_with_qr(self):
        matrix = linear_operator(EMOTIONS)
        self.assertAlmostEqual(dominant_mode(matrix)[0], abs(eigenvalues(matrix)[0]), places=3)


class TestReachability(unittest.TestCase):
    def test_the_cone_can_disagree_with_the_spectrum(self):
        # trust/doubt: unstable on paper, unreachable in fact, because the
        # growing eigenvector needs one of them to be negative.
        spec = spectrum(("trust", "doubt"))
        self.assertGreater(spec.radius, 1.0)
        self.assertLessEqual(spec.reachable, 1.0)
        self.assertFalse(spec.runs_away)
        self.assertIn("HELD BY THE CONE", spec.verdict)

    def test_the_warm_loop_really_does_run_away(self):
        spec = spectrum(("love", "trust"))
        self.assertTrue(spec.runs_away)
        self.assertGreater(spec.reachable, 1.0)
        names = [name for name, _ in spec.reachable_dominant(3)]
        self.assertIn("trust", names)
        self.assertIn("love", names)

    def test_the_reachable_mode_is_actually_reachable(self):
        # every component non-negative, or it is not a state Catharsis can hold
        _, mode = feasible_growth(linear_operator(EMOTIONS))
        self.assertTrue(all(value >= -1e-9 for value in mode))

    def test_grief_and_sadness_settle(self):
        spec = spectrum(("grief", "sadness"))
        self.assertFalse(spec.runs_away)
        self.assertIn("SETTLES", spec.verdict)

    def test_the_prediction_matches_the_runtime(self):
        # The spectrum says the warm loop grows until something stops it.  What
        # stops it is the saturation in Bond.add, not a balance of forces, so
        # the run should climb hard from 0.3 and then sit still.
        early = run_source("agent a b\nlove a b 0.3\ntrust a b 0.3\ntick 120\n").agents["a"].bond("b")
        self.assertGreater(early.get("love"), 0.9)
        self.assertGreater(early.get("trust"), 0.8)

        late = run_source("agent a b\nlove a b 0.3\ntrust a b 0.3\ntick 600\n").agents["a"].bond("b")
        for emotion in ("love", "trust"):
            self.assertAlmostEqual(late.get(emotion), early.get(emotion), places=2)


class TestPortrait(unittest.TestCase):
    def test_a_portrait_has_a_field_and_a_verdict(self):
        port = portrait(("love", "trust"), resolution=5, grid=11)
        self.assertEqual(len(port.field), 25)
        self.assertTrue(port.spectrum.runs_away)

    def test_manifold_slopes_are_json_safe(self):
        for axes in (("love", "trust"), ("trust", "doubt"), ("grief", "sadness")):
            for manifold in portrait(axes, resolution=3, grid=5).manifolds:
                slope = manifold["slope"]
                self.assertTrue(slope is None or abs(slope) < float("inf"))

    def test_settling_finds_one_place_when_there_is_one(self):
        port = portrait(("grief", "sadness"), resolution=3, grid=11)
        self.assertEqual(len(port.corners), 1)
        self.assertEqual(port.corners[0]["index"], 0)


class TestBifurcation(unittest.TestCase):
    TEMPLATE = (
        "group team\nagent alice bob charlie\n"
        "join alice team\njoin bob team\njoin charlie team\n"
        'goal team "rescue"\n'
        "trust alice bob 0.6\ntrust bob charlie 0.6\ntrust charlie alice 0.6\n"
        "doubt alice bob {}\ndoubt bob charlie {}\ndoubt charlie alice {}\n"
        "hope alice 0.7\ntick 25\n"
    )

    def test_coordination_has_a_border_collision(self):
        rows = runtime_bifurcation(self.TEMPLATE, steps=21)
        achieved = [row["achieved"] for row in rows]
        self.assertTrue(achieved[0], "low doubt should coordinate")
        self.assertFalse(achieved[-1], "high doubt should not")
        switches = [i for i in range(1, len(achieved)) if achieved[i] != achieved[i - 1]]
        self.assertEqual(len(switches), 1, "expected exactly one switch")

    def test_the_sweep_moves_every_placeholder(self):
        rows = runtime_bifurcation("agent a b\ndoubt a b {}\ndoubt b a {}\ntick 2\n", steps=3)
        self.assertEqual(len(rows), 3)
        self.assertGreater(rows[-1]["grievance"], rows[0]["grievance"])


class TestStrogatz(unittest.TestCase):
    """The regimes of the 1988 love-affair model, checked against this runtime.

    These assert a *limitation*, which is the point.  ``examples/romeo.feel``
    claims Catharsis cannot reproduce Strogatz's cautious or unrequited regimes;
    if that ever stops being true the example is wrong and should say so.
    """

    PAIR = "love r j 0.4\nlove j r 0.4\n"
    CAUTION = "trait r fear 0.7\ntrait j fear 0.7\n"

    def test_temperament_does_not_reach_an_outward_bond(self):
        # Strogatz's cautiousness is a coefficient on the pair's own dynamics.
        # The nearest thing here is a trait, and a trait lives on the self-loop.
        eager = run_source("agent r j\n" + self.PAIR + "tick 30\n")
        timid = run_source("agent r j\n" + self.CAUTION + self.PAIR + "tick 30\n")

        self.assertGreater(timid.agents["r"].self_bond.get("fear"), 0.2)
        self.assertLess(eager.agents["r"].self_bond.get("fear"), 1e-4)
        self.assertEqual(
            eager.agents["r"].bond("j").charge,
            timid.agents["r"].bond("j").charge,
            "cautiousness changed self-regard and left the bond bit-identical",
        )

    def test_spill_is_the_only_path_between_a_bond_and_the_self_loop(self):
        # ...and it runs one way, which is *why* the test above holds.
        for source, target, _ in SPILL:
            self.assertIn(source, EMOTIONS)
            self.assertIn(target, EMOTIONS)
        world = run_source("agent r j\n" + self.PAIR + "tick 30\n")
        self.assertGreater(world.agents["r"].self_bond.get("joy"), 0.0)

    def test_unrequited_love_does_not_stay_unrequited(self):
        world = run_source("agent r j\nlove r j 0.4\ntick 30\n")
        self.assertGreater(world.agents["j"].bond("r").get("love"), 0.4)

    def test_grievance_is_the_one_regime_that_survives(self):
        world = run_source("agent r j\nlove r j 0.7\nresentment j r 0.7\ntick 30\n")
        self.assertLess(world.agents["j"].bond("r").get("love"), 0.05)
        self.assertGreater(world.agents["j"].bond("r").get("resentment"), 0.2)


class TestTrajectory(unittest.TestCase):
    def test_a_recorded_run_projects_onto_a_slice(self):
        world = World(record=True)
        world.run(parse("agent a b\nlove a b 0.6\ntick 4\n"))
        path = trajectory(world, "a", "b", ("love", "trust"))
        # Every frame but the first, which is recorded before `a` exists: a
        # phase portrait has no point for an agent that has not been declared.
        self.assertEqual(len(path), len(world.frames) - 1)
        self.assertNotIn("a", world.frames[0]["state"]["agents"])
        self.assertTrue(all(0.0 <= point["x"] <= 1.0 for point in path))
        self.assertGreater(path[-1]["y"], path[0]["y"], "trust should have grown from love")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
