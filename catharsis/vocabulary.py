"""What you can say in Catharsis, expressed as a table.

Every utterance in the language is a *deposit into the field* plus, sometimes, a
structural side effect.  None of them is a statement in the imperative sense:
``betray`` does not call a betrayal routine, it puts anger, resentment, doubt and
grief on one edge and guilt on another, lays down two memories, and lets the
coupling matrix in :mod:`catharsis.field` work out the consequences over the
following ticks.

Because the vocabulary is data, adding an emotion or an event is a table entry,
not a new branch in an interpreter.
"""

from __future__ import annotations

from dataclasses import dataclass

from .field import EMOTIONS

# Words that carry no meaning and are dropped by the parser, so that programs can
# read like sentences without the grammar growing.
PARTICLES = frozenset(
    {"about", "over", "of", "to", "toward", "towards", "with", "for", "from", "that", "at", "in"}
)

RESERVED = frozenset({"agent", "group"}) | PARTICLES  # extended with the glyphs below


@dataclass(frozen=True)
class Charge:
    """A single deposit: ``emotion`` changes by ``delta`` on ``edge``.

    ``edge`` is one of ``aa``, ``ab``, ``ba``, ``bb`` where ``a`` is the first
    entity named in the utterance and ``b`` the second.  ``modulator`` names a
    runtime factor the deposit is scaled by -- an apology, for instance, lands in
    proportion to how receptive the wronged party currently is.
    """

    edge: str
    emotion: str
    delta: float
    modulator: str | None = None


@dataclass(frozen=True)
class MemorySpec:
    """A memory an utterance lays down."""

    holder: str  # "a" or "b"
    claim: str  # format string over {a} and {b}
    about: str | None  # "a", "b" or None
    kind: str
    signature: str  # which edge's deposits become the emotional signature


@dataclass(frozen=True)
class Utterance:
    """One word of the language."""

    name: str
    params: tuple[str, ...]
    doc: str
    charges: tuple[Charge, ...] = ()
    memories: tuple[MemorySpec, ...] = ()
    effect: str | None = None
    base: float = 0.6
    category: str = "event"


def _emotion_utterance(name: str, doc: str, base: float = 0.6) -> Utterance:
    """``EMOTION x`` charges the self-loop; ``EMOTION x y`` charges ``x -> y``.

    That single rule covers all twenty axes, and is why ``pride charlie`` and
    ``fear diana charlie`` need no separate syntax: self-regard is just the
    reflexive case of a relationship.
    """
    return Utterance(
        name=name,
        params=("agent", "agent?", "text?", "number?"),
        doc=doc,
        charges=(Charge("ab", name, 1.0),),
        base=base,
        category="emotion",
    )


_EMOTION_DOCS = {
    "love": "binds two entities; feeds trust and hope, and makes jealousy possible",
    "trust": "lets claims and actions through with less verification",
    "hope": "keeps a future open; sustains negotiation and resists fear",
    "joy": "rewards an interaction and spreads to the relationships around it",
    "pride": "resists modification, concession and apology",
    "curiosity": "drives inspection of what is unknown",
    "gratitude": "the counterweight to resentment",
    "anger": "amplifies action and burns trust",
    "fear": "inhibits risk, curiosity and hope",
    "doubt": "holds several readings of the same fact at once",
    "sadness": "suppresses activity",
    "grief": "removes without erasing; the afterimage that keeps acting",
    "shame": "makes an entity hard to observe and hard to approach",
    "guilt": "records responsibility and pushes toward reparation",
    "envy": "pulls an entity toward acquiring another's state",
    "jealousy": "makes an entity compete for another's attention",
    "loneliness": "pushes disconnected entities to seek bonds",
    "surprise": "interrupts expectation and opens up curiosity",
    "regret": "the live cost of a road not taken",
    "resentment": "grievance that outlives the anger that made it",
}


def _base_table() -> dict[str, Utterance]:
    table: dict[str, Utterance] = {}
    for emotion in EMOTIONS:
        table[emotion] = _emotion_utterance(emotion, _EMOTION_DOCS[emotion])

    table["betray"] = Utterance(
        name="betray",
        params=("agent", "agent", "text?"),
        doc="a breaks faith with b: grievance on one edge, guilt on the other, memory on both",
        charges=(
            Charge("ba", "anger", 0.55),
            Charge("ba", "resentment", 0.50),
            Charge("ba", "doubt", 0.65),
            Charge("ba", "grief", 0.35),
            Charge("ba", "trust", -0.50),
            Charge("ba", "love", -0.05),
            Charge("bb", "sadness", 0.30),
            Charge("bb", "grief", 0.20),
            Charge("ab", "guilt", 0.45),
            Charge("aa", "shame", 0.15),
            Charge("aa", "pride", -0.10),
        ),
        memories=(
            MemorySpec("b", "{a} betrayed {b}", "a", "experienced", "ba"),
            MemorySpec("a", "{a} betrayed {b}", "b", "own", "ab"),
        ),
        effect="betray",
    )

    table["apologize"] = Utterance(
        name="apologize",
        params=("agent", "agent"),
        doc="a offers repair to b; it lands only as far as b is currently receptive",
        charges=(
            Charge("ab", "guilt", -0.20),
            Charge("ab", "love", 0.05),
            Charge("ab", "hope", 0.10),
            Charge("ba", "surprise", 0.25),
            Charge("ba", "hope", 0.25, "receptivity"),
            Charge("ba", "resentment", -0.35, "receptivity"),
            Charge("ba", "anger", -0.30, "receptivity"),
            Charge("ba", "doubt", -0.08, "receptivity"),
        ),
        memories=(MemorySpec("b", "{a} apologised to {b}", "a", "experienced", "ba"),),
    )

    table["forgive"] = Utterance(
        name="forgive",
        params=("agent", "agent"),
        doc="a disarms its memories of b without deleting them; grief and the trust ceiling remain",
        charges=(
            Charge("ab", "resentment", -0.85),
            Charge("ab", "anger", -0.80),
            Charge("ab", "doubt", -0.15),
            Charge("aa", "grief", 0.08),
            Charge("aa", "sadness", 0.05),
        ),
        memories=(MemorySpec("a", "{a} forgave {b}", "b", "own", "aa"),),
        effect="forgive",
    )

    table["witness"] = Utterance(
        name="witness",
        params=("agent", "agent", "event", "agent?"),
        doc="a sees b do something to c, and carries a damped copy of the victim's reaction",
        effect="witness",
    )

    table["gift"] = Utterance(
        name="gift",
        params=("agent", "agent", "word", "number?"),
        doc="a hands b a resource; gratitude is the receipt",
        charges=(
            Charge("ba", "gratitude", 0.40),
            Charge("ba", "trust", 0.12),
            Charge("ab", "love", 0.05),
            Charge("aa", "pride", 0.05),
            Charge("aa", "joy", 0.08),
        ),
        effect="gift",
    )

    table["propose"] = Utterance(
        name="propose",
        params=("agent", "agent", "number?"),
        doc="a opens a bargain with b over every dimension they both have a goal on",
        charges=(Charge("ab", "hope", 0.20), Charge("ba", "surprise", 0.10)),
        effect="propose",
    )

    table["reject"] = Utterance(
        name="reject",
        params=("agent", "agent"),
        doc="a refuses b's offer; refusal stings and hardens both sides",
        charges=(
            Charge("ab", "pride", 0.15),
            Charge("ab", "doubt", 0.10),
            Charge("ba", "anger", 0.35),
            Charge("ba", "resentment", 0.20),
            Charge("ba", "hope", -0.15),
            Charge("ba", "doubt", 0.20),
        ),
        memories=(MemorySpec("b", "{a} rejected {b}", "a", "experienced", "ba"),),
        effect="reject",
    )

    table["agree"] = Utterance(
        name="agree",
        params=("agent", "agent"),
        doc="a closes the bargain with b wherever their positions have met",
        charges=(
            Charge("ab", "gratitude", 0.25),
            Charge("ab", "trust", 0.15),
            Charge("ab", "joy", 0.25),
            Charge("ba", "gratitude", 0.20),
            Charge("ba", "trust", 0.15),
            Charge("ba", "joy", 0.25),
        ),
        effect="agree",
    )

    table["remember"] = Utterance(
        name="remember",
        params=("agent", "text?", "agent?"),
        doc="a encodes a claim, stamped with whatever it is feeling right now; with no claim, reports",
        effect="remember",
    )

    table["recall"] = Utterance(
        name="recall",
        params=("agent", "text?"),
        doc="a retrieves a claim, which raises its salience and makes it hurt again",
        effect="recall",
    )

    table["denial"] = Utterance(
        name="denial",
        params=("agent", "text"),
        doc="a refuses a claim without discarding it: the fact is suppressed, the feeling keeps ruminating",
        effect="denial",
    )

    table["acceptance"] = Utterance(
        name="acceptance",
        params=("agent", "text?"),
        doc="a collapses a contradiction into a state, and pays for it in grief",
        effect="acceptance",
    )

    table["choice"] = Utterance(
        name="choice",
        params=("agent", "text", "text?"),
        doc="a takes one option over another, opening a fork that regret can return to",
        effect="choice",
    )

    table["goal"] = Utterance(
        name="goal",
        params=("entity", "word?", "value"),
        doc="an agent's position on a dimension, or a shared objective to be named",
        effect="goal",
    )

    table["have"] = Utterance(
        name="have",
        params=("agent", "word", "number"),
        doc="a holds an amount of a resource",
        effect="have",
    )

    table["need"] = Utterance(
        name="need",
        params=("agent", "word", "number"),
        doc="a requires an amount of a resource; unmet need becomes fear and sadness every tick",
        effect="need",
    )

    table["risk"] = Utterance(
        name="risk",
        params=("word", "number"),
        doc="how exposed handing this resource over leaves the giver; risky things are given on trust, not on need",
        effect="risk",
    )

    table["trait"] = Utterance(
        name="trait",
        params=("agent", "word", "number"),
        doc="a temperament: the self-loop is pulled back toward this value forever",
        effect="trait",
    )

    table["agent"] = Utterance(
        name="agent",
        params=("word+",),
        doc="brings entities into existence; takes as many names as you like",
        effect="agent",
    )

    table["group"] = Utterance(
        name="group",
        params=("word",),
        doc="declares a collective",
        effect="group",
    )

    table["join"] = Utterance(
        name="join",
        params=("agent", "word"),
        doc="a becomes a member of a group",
        effect="join",
    )

    table["tick"] = Utterance(
        name="tick",
        params=("number?",),
        doc="let the field run",
        effect="tick",
    )

    table["observe"] = Utterance(
        name="observe",
        params=("entity?",),
        doc="print the current state of an entity, or of the whole world",
        effect="observe",
    )

    return table


#: Alternative spellings.  These are conveniences, not separate semantics.
ALIASES: dict[str, str] = {
    "jealous": "jealousy",
    "lonely": "loneliness",
    "curious": "curiosity",
    "angry": "anger",
    "afraid": "fear",
    "scared": "fear",
    "proud": "pride",
    "ashamed": "shame",
    "grieve": "grief",
    "mourn": "grief",
    "grateful": "gratitude",
    "resent": "resentment",
    "envious": "envy",
    "hopeful": "hope",
    "sad": "sadness",
    "happy": "joy",
    "surprised": "surprise",
    "apology": "apologize",
    "apologise": "apologize",
    "deny": "denial",
    "regretting": "regret",
    "betraying": "betray",
    "forgiving": "forgive",
    "helping": "gift",
    "rejecting": "reject",
    "apologising": "apologize",
    "apologizing": "apologize",
    "accept": "acceptance",
}

#: One glyph per emotional axis.
#:
#: These are a second spelling, not a second language: ``GLYPHS`` feeds straight
#: into :data:`ALIASES` below, so an emoji resolves to the same utterance as its
#: word and there is not one line of runtime that knows the difference.  That is
#: the point -- because the vocabulary is a table, a whole alternative surface
#: syntax is a dict, and it can be checked by asserting that both spellings of a
#: program produce an identical world.
#:
#: They earn their place a second time on the way out: a bond rendered as
#: ``❤️ 0.82  🤝 0.75  🕊️ 0.72  🖤 0.32`` is readable at a glance in a way that
#: six emotion words in a row are not.  See ``catharsis run --emoji``.
GLYPHS: dict[str, str] = {
    "love": "❤️",
    "trust": "🤝",
    "hope": "🕊️",
    "joy": "😄",
    "pride": "🦁",
    "curiosity": "🔍",
    "gratitude": "🙏",
    "anger": "😠",
    "fear": "😨",
    "doubt": "🤔",
    "sadness": "😢",
    "grief": "🖤",
    "shame": "🙈",
    "guilt": "😞",
    "envy": "😒",
    "jealousy": "💚",
    "loneliness": "🧍",
    "surprise": "😲",
    "regret": "🛤️",
    "resentment": "🧊",
}

#: Glyphs for the events that have an obvious one.  Deliberately partial: an
#: emoji nobody would guess is worse than the word it replaces.
EVENT_GLYPHS: dict[str, str] = {
    "betray": "💔",
    "apologize": "🙇",
    "forgive": "🤲",
    "witness": "👁️",
    "gift": "🎁",
    "remember": "🧠",
    "recall": "💭",
    "denial": "🙅",
    "acceptance": "🧘",
    "choice": "🔀",
    "tick": "⏱️",
}

#: Every glyph the language answers to, mapped to what it means.
ALL_GLYPHS: dict[str, str] = {**GLYPHS, **EVENT_GLYPHS}

#: ``👤 alice bob carol`` and ``alice = 👤`` both declare.
AGENT_GLYPH = "👤"
EVENT_GLYPHS["agent"] = AGENT_GLYPH
ALL_GLYPHS["agent"] = AGENT_GLYPH

ALIASES.update({glyph: name for name, glyph in ALL_GLYPHS.items()})

VOCABULARY: dict[str, Utterance] = _base_table()

# ``regret`` is both an emotion axis and an act of returning to a fork, so it gets
# an effect hook on top of its charge deposit.
#: Aiming an emotion at a *claim* rather than at an entity makes it a stance on
#: the memory of that claim.  The rule is that feeling anything about something
#: except doubt or hope is a way of believing it happened.
CLAIM_STANCE: dict[str, str] = {"doubt": "doubt", "surprise": "doubt", "hope": "hope"}


def claim_stance(emotion: str) -> str:
    return CLAIM_STANCE.get(emotion, "affirm")


VOCABULARY["regret"] = Utterance(
    name="regret",
    params=("agent", "text?"),
    doc="a reopens its last choice and keeps the road not taken alive as a shadow history",
    charges=(Charge("aa", "regret", 0.35),),
    effect="regret",
    category="emotion",
)


def resolve(word: str) -> str:
    """Map an alias or gerund onto a canonical utterance name."""
    if word in VOCABULARY:
        return word
    if word in ALIASES:
        return ALIASES[word]
    if word.endswith("ing") and word[:-3] in VOCABULARY:
        return word[:-3]
    if word.endswith("ing") and word[:-3] + "e" in VOCABULARY:
        return word[:-3] + "e"
    if word.endswith("ed") and word[:-2] in VOCABULARY:
        return word[:-2]
    if word.endswith("s") and word[:-1] in VOCABULARY:
        return word[:-1]
    return word


def lookup(word: str) -> Utterance | None:
    return VOCABULARY.get(resolve(word))


#: Emotion words, for validating ``trait`` and diagnostics.
EMOTION_WORDS = frozenset(EMOTIONS)
