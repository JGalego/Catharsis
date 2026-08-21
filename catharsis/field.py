"""The emotional field.

Catharsis has no variables in the ordinary sense.  All state that matters lives
as *charge* on the edges of a directed graph of entities: ``alice -> bob``
carries how Alice feels about Bob, and the self-loop ``alice -> alice`` carries
how Alice feels about herself.

This module holds the physics of that field, expressed as data rather than as
control flow:

``DECAY``
    how fast each emotion fades when nothing feeds it.  Grief barely fades.
    Surprise is gone almost immediately.

``COUPLING``
    how emotions feed and drain *each other* on the same edge.  This is why
    ``betray`` does not need to know anything about trust: it deposits anger and
    resentment, and the field does the rest, over time.

``SPILL``
    how an emotion aimed at somebody else leaks onto the self-loop.  Guilt aimed
    at Bob becomes shame aimed at yourself.

``ANTAGONISTS``
    pairs that are *not* collapsed when they co-occur.  Their overlap is
    ``tension`` -- ambivalence -- which is a first-class quantity, not an error.

``TRANSMISSIBILITY``
    how readily an emotion travels along the graph as hearsay.  This is the only
    machinery reputation needs; there is no reputation table anywhere.
"""

from __future__ import annotations

import hashlib

#: Every axis of the field.  Charges live in ``[0, 1]``.
EMOTIONS: tuple[str, ...] = (
    "love",
    "trust",
    "hope",
    "joy",
    "pride",
    "curiosity",
    "gratitude",
    "anger",
    "fear",
    "doubt",
    "sadness",
    "grief",
    "shame",
    "guilt",
    "envy",
    "jealousy",
    "loneliness",
    "surprise",
    "regret",
    "resentment",
)

EMOTION_SET = frozenset(EMOTIONS)

#: Fraction of the charge lost per tick when nothing sustains it.
DECAY: dict[str, float] = {
    "love": 0.010,
    "trust": 0.020,
    "hope": 0.060,
    "joy": 0.100,
    "pride": 0.020,
    "curiosity": 0.080,
    "gratitude": 0.040,
    "anger": 0.120,
    "fear": 0.080,
    "doubt": 0.030,
    "sadness": 0.050,
    "grief": 0.005,
    "shame": 0.060,
    "guilt": 0.040,
    "envy": 0.060,
    "jealousy": 0.080,
    "loneliness": 0.020,
    "surprise": 0.500,
    "regret": 0.010,
    "resentment": 0.020,
}

#: ``(source, target, rate)``: each tick ``target += rate * source``.
#: Negative rates drain.  This table is the reason emotional interactions
#: compose into histories instead of into independent flags.
COUPLING: tuple[tuple[str, str, float], ...] = (
    ("love", "trust", 0.060),
    ("love", "hope", 0.040),
    ("love", "jealousy", 0.020),
    ("love", "loneliness", -0.030),
    ("trust", "love", 0.020),
    ("trust", "doubt", -0.050),
    ("trust", "fear", -0.030),
    ("hope", "trust", 0.030),
    ("hope", "fear", -0.020),
    ("hope", "joy", 0.020),
    ("hope", "sadness", -0.020),
    ("joy", "love", 0.030),
    ("joy", "sadness", -0.040),
    ("joy", "pride", 0.020),
    ("pride", "shame", -0.050),
    ("pride", "guilt", -0.030),
    ("pride", "anger", 0.020),
    ("curiosity", "doubt", 0.020),
    ("curiosity", "fear", -0.020),
    ("gratitude", "love", 0.050),
    ("gratitude", "trust", 0.050),
    ("gratitude", "resentment", -0.050),
    ("anger", "trust", -0.050),
    ("anger", "resentment", 0.050),
    ("anger", "fear", -0.020),
    ("fear", "trust", -0.030),
    ("fear", "hope", -0.040),
    ("fear", "curiosity", -0.050),
    ("doubt", "trust", -0.060),
    ("doubt", "curiosity", 0.030),
    ("sadness", "joy", -0.050),
    ("sadness", "hope", -0.030),
    ("grief", "sadness", 0.035),
    ("grief", "love", 0.020),
    ("grief", "joy", -0.040),
    ("shame", "pride", -0.060),
    ("shame", "loneliness", 0.040),
    ("guilt", "shame", 0.040),
    ("guilt", "pride", -0.050),
    ("envy", "resentment", 0.040),
    ("envy", "curiosity", 0.030),
    ("jealousy", "anger", 0.050),
    ("jealousy", "fear", 0.030),
    ("loneliness", "hope", 0.020),
    ("loneliness", "sadness", 0.030),
    ("surprise", "curiosity", 0.060),
    ("surprise", "doubt", 0.040),
    ("regret", "sadness", 0.040),
    ("regret", "doubt", 0.030),
    ("resentment", "love", -0.030),
    ("resentment", "trust", -0.040),
    ("resentment", "anger", 0.020),
)

#: ``(bond emotion, self emotion, rate)``: what an emotion aimed outward does to
#: the way an entity feels about itself.
SPILL: tuple[tuple[str, str, float], ...] = (
    ("guilt", "shame", 0.050),
    ("guilt", "pride", -0.030),
    ("love", "loneliness", -0.040),
    ("trust", "fear", -0.020),
    ("gratitude", "joy", 0.030),
    ("jealousy", "loneliness", 0.040),
    ("envy", "shame", 0.020),
    ("grief", "grief", 0.015),
    ("grief", "loneliness", 0.030),
    ("resentment", "sadness", 0.020),
    ("fear", "fear", 0.030),
)

#: Pairs that are allowed to coexist.  ``min(a, b)`` of each pair, scaled by the
#: weight, is *tension*: the cost of holding a contradiction.  Nothing in the
#: runtime ever resolves these automatically -- only ``acceptance`` does.
ANTAGONISTS: tuple[tuple[str, str, float], ...] = (
    ("love", "anger", 1.0),
    ("love", "resentment", 1.0),
    ("trust", "doubt", 1.0),
    ("trust", "resentment", 0.8),
    ("hope", "fear", 0.9),
    ("joy", "sadness", 0.8),
    ("pride", "shame", 1.0),
    ("gratitude", "resentment", 0.9),
    ("curiosity", "fear", 0.5),
)

#: How readily an emotion travels as hearsay along the relationship graph.
#: Absent emotions (grief, guilt, shame, pride, loneliness, regret) are private:
#: they cannot be caught from somebody else.  Note the negativity bias -- warning
#: travels further than praise, and reputation emerges from exactly that.
TRANSMISSIBILITY: dict[str, float] = {
    "doubt": 1.00,
    "resentment": 0.85,
    "anger": 0.70,
    "fear": 0.60,
    "trust": 0.45,
    "love": 0.20,
    "gratitude": 0.40,
    "envy": 0.30,
    "curiosity": 0.35,
}

#: Rate at which hearsay closes the gap toward what an observer could catch.
CONTAGION = 0.15

#: Ceiling on second-hand feeling: what you catch from somebody else is at most
#: this share of what they feel, before trust and transmissibility scale it down
#: further.  Second-hand never becomes first-hand.
HEARSAY = 0.60

#: An observer must trust the source at least this much to catch anything.
CONTAGION_FLOOR = 0.20

#: Seeing something happen to somebody else puts you in their shoes at this
#: strength.  Below 1.0 because you are not the one it happened to.
WITNESS_DAMPING = 0.55

#: Rate at which a memory pulls its bond back toward the level it sustains.
#: Rumination is relaxation, not accumulation: a memory holds a feeling at a
#: level, and stops pushing once it is there.
RUMINATION = 0.12

#: How much of its original charge a memory can keep alive, per emotion.
#: Derived from :data:`DECAY`, so that what burns out fast (anger, surprise) is
#: not sustained by remembering, while what does not (grief, resentment, love)
#: is.  This is the difference between still being angry and still being hurt.
MEMORY_HOLD: dict[str, float] = {emotion: 0.06 / (0.06 + rate) for emotion, rate in DECAY.items()}

#: Memories fade this slowly, and never below :data:`SALIENCE_FLOOR`.
SALIENCE_DECAY = 0.006
SALIENCE_FLOOR = 0.05

#: Emotions a *reconciled* memory stops re-injecting.  Forgiveness disarms a
#: memory; it does not delete it, and the rest of the signature keeps ruminating.
HOSTILE = frozenset({"anger", "resentment", "jealousy", "envy"})

#: How much a live memory caps trust on the edge it concerns.  This is why
#: ``trust != absence_of_history``: a forgiven betrayal still lowers the ceiling.
TRUST_CEILING_WEIGHT = 0.45


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    return low if value < low else high if value > high else value


def jitter(*parts: object) -> float:
    """A stable pseudo-random value in ``[0, 1)`` derived from ``parts``.

    Catharsis never uses a seeded PRNG for symmetry breaking, because that makes
    results depend on evaluation order.  A content hash gives the same answer for
    the same situation no matter when it is asked, so programs are reproducible.
    """
    key = "\x1f".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(digest, "big") / 2.0**64


def tension(charge: dict[str, float]) -> float:
    """Total unresolved contradiction held in a charge vector."""
    total = 0.0
    for left, right, weight in ANTAGONISTS:
        total += weight * min(charge.get(left, 0.0), charge.get(right, 0.0))
    return total


def contradictions(charge: dict[str, float], threshold: float = 0.15) -> list[tuple[str, str, float]]:
    """The antagonist pairs currently held together, strongest first."""
    found = []
    for left, right, weight in ANTAGONISTS:
        overlap = weight * min(charge.get(left, 0.0), charge.get(right, 0.0))
        if overlap >= threshold:
            found.append((left, right, overlap))
    found.sort(key=lambda item: (-item[2], item[0], item[1]))
    return found


def dominant(charge: dict[str, float], limit: int = 4, threshold: float = 0.05) -> list[tuple[str, float]]:
    """The strongest emotions in a charge vector, strongest first."""
    items = [(name, value) for name, value in charge.items() if value >= threshold]
    items.sort(key=lambda item: (-item[1], item[0]))
    return items[:limit]
