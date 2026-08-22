"""The phase-space page: payload shape, and that the page it writes is well formed."""

import functools
import json
import re
import unittest

from catharsis.parser import parse
from catharsis.phase import (
    DEFAULT_PAIRS,
    DEFAULT_SWEEP,
    build_payload,
    render_html,
)
from catharsis.world import World

PAYLOAD = re.compile(r'<script type="application/json" id="payload">(.*?)</script>', re.S)

#: A full-fidelity payload re-runs a whole program 41 times and samples two
#: 61x61 basin grids per slice, which is about half a minute.  None of that time
#: buys these tests anything, so they build the same shape at low fidelity.
COARSE = {"resolution": 3, "grid": 5, "sweep_steps": 5}


def coarse(**kwargs) -> dict:
    return build_payload(**COARSE, **kwargs)


@functools.lru_cache(maxsize=1)
def field_payload() -> dict:
    """The no-argument payload, built once.  Tests read it; none mutate it."""
    return coarse()


def payload_of(page: str) -> dict:
    match = PAYLOAD.search(page)
    assert match, "the page carries no payload"
    return json.loads(match.group(1))


class TestPayload(unittest.TestCase):
    def test_the_field_on_its_own(self):
        payload = field_payload()
        self.assertEqual(len(payload["slices"]), len(DEFAULT_PAIRS))
        self.assertIn("verdict", payload["whole"])
        self.assertTrue(payload["bifurcation"])
        self.assertIsNone(payload["edge"])

    def test_every_slice_carries_what_the_page_draws(self):
        for slice_ in field_payload()["slices"]:
            for key in ("axes", "spectrum", "field", "manifolds", "basins", "corners", "grid"):
                self.assertIn(key, slice_, f"{slice_['axes']} is missing {key}")

    def test_a_program_puts_a_trajectory_on_the_slice(self):
        world = World(record=True)
        world.run(parse("agent a b\nlove a b 0.4\ntrust a b 0.2\ntick 6\n"))
        payload = coarse(world=world, edge=("a", "b"), title="pair")
        self.assertEqual(payload["title"], "pair")
        self.assertEqual(payload["edge"], ["a", "b"])
        traced = [s for s in payload["slices"] if s.get("path")]
        self.assertTrue(traced, "no slice picked up the run")
        for point in traced[0]["path"]:
            self.assertTrue(0.0 <= point["x"] <= 1.0 and 0.0 <= point["y"] <= 1.0)

    def test_an_edge_that_does_not_exist_draws_nothing(self):
        world = World(record=True)
        world.run(parse("agent a b\nlove a b 0.4\ntick 2\n"))
        payload = coarse(world=world, edge=("a", "nobody"))
        self.assertFalse(any(s.get("path") for s in payload["slices"]))

    def test_the_sweep_finds_the_border_collision(self):
        payload = field_payload()
        self.assertIn("{}", DEFAULT_SWEEP)
        self.assertTrue(payload["collisions"], "the coordination sweep found no switch")
        for collision in payload["collisions"]:
            self.assertTrue(0.0 <= collision <= 1.0)


class TestPage(unittest.TestCase):
    def test_the_page_is_self_contained_and_parses(self):
        page = render_html(field_payload())
        # The only absolute URL allowed is the SVG namespace, which is an
        # identifier rather than something the browser goes and fetches.
        for url in re.findall(r"https?://[^\s\"'()]+", page):
            self.assertEqual(url, "http://www.w3.org/2000/svg")
        self.assertIn("<title>", page)
        self.assertEqual(payload_of(page)["whole"]["verdict"], field_payload()["whole"]["verdict"])

    def test_a_title_with_markup_in_it_is_escaped(self):
        page = render_html(coarse(title="<script>alert(1)</script>"))
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_the_payload_holds_no_nan_or_infinity(self):
        # json.dumps would happily emit those and JSON.parse would reject them.
        page = render_html(field_payload())
        blob = PAYLOAD.search(page).group(1)
        self.assertNotIn("NaN", blob)
        self.assertNotIn("Infinity", blob)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
