"""Tests for the replay page.

The interesting ones are the projection partition (every axis is drawn exactly
once, so nothing silently vanishes from the picture) and the escaping test:
memory claims are program text, and program text ends up inside a script tag.
"""

import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from catharsis import parse, run_source
from catharsis.cli import main
from catharsis.field import EMOTIONS
from catharsis.viz import CHANNELS, build_payload, channel_totals, render_html
from catharsis.world import World, source_line

ROOT = Path(__file__).resolve().parent.parent

PROGRAM = "agent alice bob\nlove alice bob 0.8\nbetray alice bob\ntick 3\n"


def recorded(source: str = PROGRAM) -> World:
    world = World(record=True)
    world.run(parse(source))
    return world


class TestChannels(unittest.TestCase):
    def test_every_drawn_axis_belongs_to_exactly_one_channel(self):
        seen = [emotion for axes in CHANNELS.values() for emotion in axes]
        self.assertEqual(len(seen), len(set(seen)), "an axis is drawn in two lanes")
        for emotion in seen:
            self.assertIn(emotion, EMOTIONS)

    def test_only_surprise_is_left_out(self):
        drawn = {emotion for axes in CHANNELS.values() for emotion in axes}
        self.assertEqual(set(EMOTIONS) - drawn, {"surprise"})

    def test_totals_sum_the_right_axes(self):
        sums = channel_totals({"love": 0.5, "trust": 0.25, "anger": 0.4, "grief": 0.1})
        self.assertAlmostEqual(sums["bond"], 0.75)
        self.assertAlmostEqual(sums["grievance"], 0.4)
        self.assertAlmostEqual(sums["burden"], 0.1)

    def test_an_ambivalent_bond_shows_on_two_channels_at_once(self):
        # The whole point of the projection: this must not net out to one number.
        world = run_source("agent a b\nlove a b 0.9\nanger a b 0.8\n")
        sums = channel_totals(world.agents["a"].bond("b").charge)
        self.assertGreater(sums["bond"], 0.5)
        self.assertGreater(sums["grievance"], 0.5)


class TestRecording(unittest.TestCase):
    def test_nothing_is_recorded_unless_asked(self):
        world = run_source(PROGRAM)
        self.assertEqual(world.frames, [])

    def test_a_frame_per_statement_and_per_tick(self):
        world = recorded()
        # 1 opening frame + 4 statements, of which `tick 3` contributes 3 frames
        self.assertEqual(len(world.frames), 1 + 3 + 3)
        self.assertEqual(world.frames[0]["kind"], "start")
        self.assertEqual([f["kind"] for f in world.frames[-3:]], ["tick", "tick", "tick"])
        self.assertEqual([f["tick"] for f in world.frames[-3:]], [1, 2, 3])

    def test_frames_carry_the_source_line_and_its_text(self):
        world = recorded()
        labelled = [f for f in world.frames if f["label"] == "betray alice bob"]
        self.assertEqual(len(labelled), 1)
        self.assertEqual(labelled[0]["line"], 3)

    def test_events_are_attributed_to_the_frame_they_happened_in(self):
        world = recorded()
        betrayal = next(f for f in world.frames if f["label"] == "betray alice bob")
        self.assertIn("alice betrayed bob", " ".join(betrayal["events"]))
        # ...and are not repeated in the next frame
        following = world.frames[betrayal["index"] + 1]
        self.assertNotIn("alice betrayed bob", " ".join(following["events"]))

    def test_recording_does_not_change_the_result(self):
        from catharsis import to_dict

        self.assertEqual(to_dict(run_source(PROGRAM)), to_dict(recorded()))

    def test_recording_is_deterministic(self):
        self.assertEqual(recorded().frames, recorded().frames)

    def test_a_comment_is_stripped_from_the_label_but_a_hash_in_a_claim_is_not(self):
        program = parse('a = agent\nremember a "tagged #1"   # a comment\n')
        self.assertEqual(source_line(program.statements[1]), 'remember a "tagged #1"')


class TestPayload(unittest.TestCase):
    def test_payload_shape(self):
        payload = build_payload(recorded(), "demo", PROGRAM)
        self.assertEqual(payload["title"], "demo")
        self.assertEqual(payload["agents"], ["alice", "bob"])
        self.assertEqual(payload["source"], PROGRAM)
        self.assertEqual(set(payload["channels"]), set(CHANNELS))
        self.assertTrue(payload["frames"])

    def test_an_unrecorded_world_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            build_payload(run_source(PROGRAM), "demo", PROGRAM)
        self.assertIn("not recorded", str(caught.exception))

    def test_the_payload_survives_a_round_trip(self):
        payload = build_payload(recorded(), "demo", PROGRAM)
        self.assertEqual(json.loads(json.dumps(payload))["agents"], ["alice", "bob"])


class TestRendering(unittest.TestCase):
    def test_the_page_is_standalone(self):
        html = render_html(build_payload(recorded(), "demo", PROGRAM))
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertNotIn('src="http', html)
        self.assertNotIn("@import", html)
        self.assertNotIn("__PAYLOAD__", html)
        self.assertNotIn("__TITLE__", html)

    def test_program_text_cannot_break_out_of_the_script_tag(self):
        hostile = 'a = agent\nremember a "</script><img src=x onerror=alert(1)>"\n'
        html = render_html(build_payload(recorded(hostile), "x", hostile))
        island = re.search(r'<script type="application/json" id="payload">(.*?)</script>', html, re.S)
        self.assertIsNotNone(island, "the JSON island was closed early")
        self.assertNotIn("</", island.group(1))
        # and the claim is still intact once parsed
        payload = json.loads(island.group(1).replace("<\\/", "</"))
        claims = [m["claim"] for m in payload["frames"][-1]["state"]["agents"]["a"]["memories"]]
        self.assertIn("</script><img src=x onerror=alert(1)>", claims)

    def test_the_title_is_escaped(self):
        html = render_html(build_payload(recorded(), "<b>x</b>", PROGRAM))
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertNotIn("<b>x</b>", html)

    def test_both_themes_are_defined(self):
        html = render_html(build_payload(recorded(), "demo", PROGRAM))
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertIn('[data-theme="dark"]', html)
        self.assertIn('[data-theme="light"]', html)


class TestVisualizeCommand(unittest.TestCase):
    def test_it_writes_a_page_next_to_the_program(self):
        out = ROOT / "tests" / "_viz.html"
        program = ROOT / "examples" / "contradiction.feel"
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                code = main(["visualize", str(program), "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())
            body = out.read_text(encoding="utf-8")
            self.assertIn("<svg", body)
            self.assertIn("moments", buffer.getvalue())
        finally:
            out.unlink(missing_ok=True)

    def test_extra_ticks_are_recorded_too(self):
        world = recorded()
        before = len(world.frames)
        world.step()
        self.assertEqual(len(world.frames), before + 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
