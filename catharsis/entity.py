"""Entities, bonds, memories and timelines.

An agent in Catharsis is not an object with methods.  It is a bundle of
*pressures*: what it feels about others, what it feels about itself, what it
cannot forget, what it needs, and which of its own choices it is still arguing
with.  Nothing here decides anything -- decisions emerge in :mod:`catharsis.world`
out of the shape of this state.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field

from .field import (
    HOSTILE,
    MEMORY_HOLD,
    SALIENCE_DECAY,
    SALIENCE_FLOOR,
    TRUST_CEILING_WEIGHT,
    clamp,
    tension,
)


@dataclass
class Bond:
    """The directed edge ``source -> target`` and the charge it carries.

    ``alice -> alice`` is a real bond: self-regard is a relationship.
    """

    source: str
    target: str
    charge: dict[str, float] = dc_field(default_factory=dict)
    born: int = 0
    #: Upper bound on trust imposed by live memories.  History is a ceiling.
    trust_ceiling: float = 1.0

    @property
    def reflexive(self) -> bool:
        return self.source == self.target

    def get(self, emotion: str) -> float:
        return self.charge.get(emotion, 0.0)

    def add(self, emotion: str, delta: float) -> float:
        """Deposit charge, with diminishing returns at both ends.

        A deposit fills the headroom that is left rather than a fixed amount, and
        a withdrawal takes a share of what is actually there.  Nothing ever slams
        into 0 or 1, so repeated overtures keep meaning something and no feeling
        can be removed that was never present.
        """
        current = self.charge.get(emotion, 0.0)
        value = clamp(current + delta * ((1.0 - current) if delta > 0 else current))
        self.charge[emotion] = value
        return value

    def set(self, emotion: str, value: float) -> None:
        self.charge[emotion] = clamp(value)

    @property
    def tension(self) -> float:
        return tension(self.charge)

    @property
    def intensity(self) -> float:
        return sum(self.charge.values())


@dataclass
class Memory:
    """An episode that keeps acting on the present.

    A memory is not a record that can be read without cost.  Every tick it
    re-injects a fraction of the charge that formed it back into the bond it is
    about (``rumination``), and while it is salient it caps trust on that bond.
    Stances (``affirm``/``deny``/``doubt``/``hope``) accumulate independently, so
    a memory can be simultaneously believed and denied; that is a state, not a
    bug.
    """

    claim: str
    subject: str
    about: str | None = None
    kind: str = "experienced"  # experienced | witnessed | told | counterfactual | own
    signature: dict[str, float] = dc_field(default_factory=dict)
    salience: float = 1.0
    stances: dict[str, float] = dc_field(default_factory=lambda: {"affirm": 1.0})
    reconciled: bool = False
    reconciled_at: int | None = None
    #: Set by ``denial``.  The claim stops costing tension -- and keeps ruminating
    #: at full strength anyway, which is the whole point of denial.
    suppressed: bool = False
    created_at: int = 0
    revisions: int = 0
    source: str | None = None  # who told it, for hearsay

    @property
    def weight(self) -> float:
        """How heavy the episode is, from the charge that laid it down."""
        return min(1.0, sum(self.signature.values()) / 2.0)

    @property
    def contradiction_count(self) -> int:
        against = self.stances.get("deny", 0.0) + self.stances.get("doubt", 0.0)
        support = self.stances.get("affirm", 0.0) + self.stances.get("hope", 0.0)
        if against <= 0.05 or support <= 0.05:
            return 0
        return int(round(min(against, support) * 4))

    @property
    def confidence(self) -> float:
        """Belief in ``[0, 1]``.  Never a boolean, on purpose."""
        affirm = self.stances.get("affirm", 0.0) + 0.4 * self.stances.get("hope", 0.0)
        deny = self.stances.get("deny", 0.0) + 0.6 * self.stances.get("doubt", 0.0)
        total = affirm + deny
        if total <= 1e-9:
            return 0.5
        return clamp(affirm / total)

    @property
    def confidence_label(self) -> str:
        conf = self.confidence
        disputed = self.stances.get("deny", 0.0) > 0.25 and self.stances.get("affirm", 0.0) > 0.25
        if disputed:
            return "disputed"
        if conf >= 0.85:
            return "certain"
        if conf >= 0.65:
            return "likely"
        if conf >= 0.35:
            return "uncertain"
        if conf >= 0.15:
            return "doubted"
        return "denied"

    @property
    def emotional_weight_label(self) -> str:
        weight = self.weight * self.salience
        if weight >= 0.55:
            return "high"
        if weight >= 0.25:
            return "medium"
        return "low"

    def stance(self, name: str, delta: float) -> None:
        self.stances[name] = clamp(self.stances.get(name, 0.0) + delta, 0.0, 2.0)
        self.revisions += 1

    def rumination(self) -> dict[str, float]:
        """The levels this memory keeps alive on its bond.

        These are *targets*, not increments.  A memory holds a feeling at a
        level and stops pushing once it is there, which is why second-hand
        hearsay never grows into first-hand injury however long it is carried.
        """
        # A denied memory keeps its grip: the mind drops the claim, the body does
        # not drop the feeling.
        credence = max(self.confidence, 0.75) if self.suppressed else self.confidence
        strength = self.salience * credence
        out: dict[str, float] = {}
        for emotion, value in self.signature.items():
            if self.reconciled and emotion in HOSTILE:
                continue
            scale = 0.5 if (self.reconciled and emotion == "doubt") else 1.0
            out[emotion] = value * MEMORY_HOLD.get(emotion, 0.5) * strength * scale
        return out

    def ceiling(self) -> float:
        """The trust ceiling this memory imposes on its bond."""
        if self.about is None:
            return 1.0
        harm = sum(self.signature.get(name, 0.0) for name in ("anger", "resentment", "doubt", "grief"))
        if harm <= 0.0:
            return 1.0
        # Forgiveness raises the ceiling. It does not remove it: what happened
        # still constrains how far this can go, which is the whole distinction
        # between forgiving and forgetting.
        if self.reconciled:
            harm *= 0.55
        return clamp(1.0 - TRUST_CEILING_WEIGHT * min(1.0, harm / 2.0) * self.salience * self.confidence)

    def fade(self) -> None:
        self.salience = max(SALIENCE_FLOOR, self.salience - SALIENCE_DECAY)


@dataclass
class Choice:
    """A fork in an agent's timeline."""

    option: str
    alternative: str | None
    at: int


@dataclass
class Branch:
    """A road not taken, kept alive and computable.

    Catharsis does not rewind to explore an alternative past.  It keeps the
    counterfactual as a *shadow valuation* that drifts upward the longer it is
    carried -- the grass-is-greener term -- and the gap between the two
    valuations is the agent's live regret.
    """

    point: Choice
    taken: str
    untaken: str
    forked_at: int
    valuation: float = 0.0
    actual_at_fork: float = 0.0
    idealization: float = 0.0
    closed: bool = False
    closed_at: int | None = None
    visits: int = 0

    def drift(self, rate: float = 0.035, cap: float = 0.9) -> None:
        """Unlived options improve with age.  That is what makes regret grow."""
        if self.closed:
            return
        self.idealization = min(cap, self.idealization + rate)
        self.valuation = self.actual_at_fork + self.idealization

    def pressure(self, actual: float) -> float:
        if self.closed:
            return 0.0
        return clamp(self.valuation - actual)


@dataclass
class Agent:
    """An entity in the field."""

    name: str
    bonds: dict[str, Bond] = dc_field(default_factory=dict)
    memories: list[Memory] = dc_field(default_factory=list)
    timeline: list[Choice] = dc_field(default_factory=list)
    branches: list[Branch] = dc_field(default_factory=list)
    resources: dict[str, float] = dc_field(default_factory=dict)
    needs: dict[str, float] = dc_field(default_factory=dict)
    stances: dict[str, float] = dc_field(default_factory=dict)  # negotiation positions
    goals: dict[str, float] = dc_field(default_factory=dict)  # original positions
    commitments: list[str] = dc_field(default_factory=list)  # group goals
    groups: list[str] = dc_field(default_factory=list)
    traits: dict[str, float] = dc_field(default_factory=dict)
    fatigue: dict[tuple[str, str], float] = dc_field(default_factory=dict)
    born: int = 0

    # -- bonds ------------------------------------------------------------
    def bond(self, target: str, create: bool = True, at: int = 0) -> Bond:
        existing = self.bonds.get(target)
        if existing is not None:
            return existing
        if not create:
            raise KeyError(target)
        bond = Bond(self.name, target, born=at)
        self.bonds[target] = bond
        return bond

    @property
    def self_bond(self) -> Bond:
        return self.bond(self.name)

    def feels(self, emotion: str, target: str | None = None) -> float:
        bond = self.bonds.get(target if target is not None else self.name)
        return 0.0 if bond is None else bond.get(emotion)

    def others(self) -> list[Bond]:
        return [bond for name, bond in self.bonds.items() if name != self.name]

    # -- wellbeing --------------------------------------------------------
    def wellbeing(self) -> float:
        """A scalar summary used only where a scalar is unavoidable.

        Regret needs to compare two lives; this is how it does it.
        """
        me = self.self_bond
        positive = me.get("joy") + me.get("pride") + 0.5 * me.get("hope")
        negative = (
            me.get("sadness")
            + me.get("grief")
            + me.get("shame")
            + me.get("loneliness")
            + 0.5 * me.get("fear")
        )
        outward = 0.0
        for bond in self.others():
            outward += 0.35 * (bond.get("love") + bond.get("trust") + bond.get("gratitude"))
            outward -= 0.35 * (bond.get("resentment") + bond.get("fear") + bond.get("jealousy"))
        deficit = sum(max(0.0, need - self.resources.get(res, 0.0)) for res, need in self.needs.items())
        return positive - negative + outward - 0.3 * deficit

    @property
    def tension(self) -> float:
        return sum(bond.tension for bond in self.bonds.values())

    # -- memory -----------------------------------------------------------
    def find_memories(self, claim: str | None = None, about: str | None = None) -> list[Memory]:
        found = []
        for memory in self.memories:
            if claim is not None and memory.claim != claim:
                continue
            if about is not None and memory.about != about:
                continue
            found.append(memory)
        return found

    def remember(self, memory: Memory) -> Memory:
        """Add a memory, or reinforce an identical one."""
        for existing in self.memories:
            if existing.claim == memory.claim and existing.about == memory.about:
                # Hearing it again makes it more present and more believed, but
                # a retold story never becomes heavier than the heaviest telling:
                # otherwise two friends could amplify a rumour without limit.
                existing.salience = clamp(existing.salience + 0.2)
                existing.stance("affirm", 0.2)
                if not memory.reconciled:
                    # Doing it again reopens what was forgiven.
                    existing.reconciled = False
                    existing.reconciled_at = None
                for emotion, value in memory.signature.items():
                    existing.signature[emotion] = max(existing.signature.get(emotion, 0.0), value)
                return existing
        self.memories.append(memory)
        return memory

    def refresh_trust_ceilings(self) -> None:
        ceilings: dict[str, float] = {}
        for memory in self.memories:
            if memory.about is None:
                continue
            ceilings[memory.about] = min(ceilings.get(memory.about, 1.0), memory.ceiling())
        for name, bond in self.bonds.items():
            bond.trust_ceiling = ceilings.get(name, 1.0)
            if bond.get("trust") > bond.trust_ceiling:
                bond.set("trust", bond.trust_ceiling)

    # -- fatigue ----------------------------------------------------------
    def act_cost(self, action: str, target: str) -> float:
        return self.fatigue.get((action, target), 0.0)

    def tire(self, action: str, target: str, amount: float = 1.0) -> None:
        key = (action, target)
        self.fatigue[key] = min(1.5, self.fatigue.get(key, 0.0) + amount)

    def rest(self, rate: float = 0.30) -> None:
        for key in list(self.fatigue):
            value = self.fatigue[key] - rate
            if value <= 0.0:
                del self.fatigue[key]
            else:
                self.fatigue[key] = value


@dataclass
class Group:
    """A named collective with an optional shared goal."""

    name: str
    members: list[str] = dc_field(default_factory=list)
    goal: str | None = None
    progress: float = 0.0
    required: float = 0.0
    achieved_at: int | None = None


@dataclass
class Negotiation:
    """An open bargain over a shared numeric dimension."""

    left: str
    right: str
    dimension: str
    opened_at: int
    initial_gap: float
    status: str = "open"  # open | agreed | impasse
    agreement: float | None = None
    closed_at: int = 0
    rounds: int = 0
    concessions: dict[str, float] = dc_field(default_factory=dict)

    @property
    def parties(self) -> tuple[str, str]:
        return (self.left, self.right)
