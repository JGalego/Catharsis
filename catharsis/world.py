"""The Catharsis runtime.

A program does not execute instructions.  It deposits charge into a field and
then lets the field run.  ``tick`` is the only thing resembling control flow, and
all it does is advance the simulation one step:

1. everything fades a little (:data:`~catharsis.field.DECAY`)
2. temperament pulls each entity back toward its baseline
3. emotions feed and drain each other (:data:`~catharsis.field.COUPLING`)
4. outward feeling leaks onto self-regard (:data:`~catharsis.field.SPILL`)
5. memories ruminate: the past pushes charge back into the present
6. unmet needs become fear, sadness and envy
7. feeling travels between entities as hearsay (contagion)
8. roads not taken drift upward in value, and become regret
9. open bargains move by however much each side can bear to concede
10. every agent scores every action it could take, and takes the strongest one
11. shared goals check whether they have been met

Nothing in that list is specific to any one emotion.  All twenty axes go through
the same machinery, which is what makes the behaviour compose.
"""

from __future__ import annotations

from dataclasses import dataclass

from .actions import ACTION_BY_NAME, ACTIONS, THRESHOLD, Action
from .ast import Declare, Program, Utter
from .entity import Agent, Branch, Choice, Group, Memory, Negotiation
from .errors import CatharsisRuntimeError, suggest
from .field import (
    CONTAGION,
    CONTAGION_FLOOR,
    COUPLING,
    DECAY,
    HEARSAY,
    RUMINATION,
    SPILL,
    TRANSMISSIBILITY,
    WITNESS_DAMPING,
    clamp,
    jitter,
)
from .vocabulary import VOCABULARY, Utterance, claim_stance

#: How fast temperament reasserts itself.
TEMPERAMENT_RATE = 0.08

#: Maximum share of the remaining gap a negotiator will close in one round.
MAX_CONCESSION = 0.40

#: How many actionless ticks ``settle`` needs before it believes the field is
#: done.  Must exceed the time for full habituation to wear off, or a resting
#: agent looks like a finished one.
QUIET_TICKS = 8


def source_line(node) -> str:
    """The statement as the author wrote it, minus any trailing comment."""
    text = getattr(node, "text", "") or ""
    quoted = False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            text = text[:index]
            break
    return " ".join(text.split()) or "(nothing)"


@dataclass
class Event:
    tick: int
    kind: str
    text: str

    def __str__(self) -> str:
        return f"[tick {self.tick}] {self.text}"


@dataclass
class Decision:
    agent: str
    action: str
    target: str
    pressure: float


class World:
    """Everything that exists, and the rules by which it changes."""

    def __init__(self, sink=None, trace: bool = False, emoji: bool = False, record: bool = False) -> None:
        self.agents: dict[str, Agent] = {}
        self.groups: dict[str, Group] = {}
        self.negotiations: list[Negotiation] = []
        #: resource -> how much handing it over exposes the giver.
        self.risk: dict[str, float] = {}
        self.tick_count = 0
        self.log: list[Event] = []
        self.sink = sink if sink is not None else (lambda line: None)
        self.trace = trace
        #: Render state with one glyph per emotion instead of the word.
        self.emoji = emoji
        #: When recording, every statement and every tick leaves a full snapshot
        #: behind, so the whole run can be replayed rather than only summarised.
        self.recording = record
        self.frames: list[dict] = []
        self._logged = 0
        self._line = 0
        self.filename = "<source>"

    # ------------------------------------------------------------------
    # plumbing
    # ------------------------------------------------------------------
    def emit(self, line: str = "") -> None:
        self.sink(line)

    def record(self, kind: str, text: str) -> None:
        event = Event(self.tick_count, kind, text)
        self.log.append(event)
        if self.trace:
            self.emit(str(event))

    def fail(self, node, message: str, hint: str | None = None) -> CatharsisRuntimeError:
        return CatharsisRuntimeError(
            message,
            line=getattr(node, "line", 0),
            column=getattr(node, "column", 0),
            text=getattr(node, "text", ""),
            filename=self.filename,
            hint=hint,
        )

    def require(self, name, node, what: str = "agent") -> Agent:
        if not isinstance(name, str) or name not in self.agents:
            known = list(self.agents) + list(self.groups)
            raise self.fail(
                node,
                f"no {what} named '{name}'",
                suggest(str(name), known)
                or (
                    f"declare it first with '{name} = agent'"
                    if known
                    else "declare an agent with 'name = agent'"
                ),
            )
        return self.agents[name]

    # ------------------------------------------------------------------
    # program execution
    # ------------------------------------------------------------------
    def run(self, program: Program) -> World:
        self.filename = program.filename
        self.capture("(before anything happens)", "start")
        for statement in program.statements:
            if isinstance(statement, Declare):
                self.declare(statement)
                self.capture(source_line(statement), "utterance")
            else:
                self.utter(statement)
                # A tick has already captured a frame for each step it ran.
                if VOCABULARY[statement.verb].effect != "tick":
                    self.capture(source_line(statement), "utterance")
        return self

    def capture(self, label: str, kind: str) -> None:
        """Freeze the whole world, labelled with whatever just happened."""
        if not self.recording:
            return
        from .report import to_dict

        events = [event.text for event in self.log[self._logged :]]
        self._logged = len(self.log)
        self.frames.append(
            {
                "index": len(self.frames),
                "tick": self.tick_count,
                "line": self._line,
                "label": label,
                "kind": kind,
                "events": events,
                "state": to_dict(self),
            }
        )

    def declare(self, node: Declare) -> Agent:
        self._line = node.line
        return self.bring_into_being(node.name, node)

    def bring_into_being(self, name: str, node) -> Agent:
        if name in self.agents:
            raise self.fail(node, f"'{name}' is already an agent", "each agent is declared once")
        if name in self.groups:
            raise self.fail(node, f"'{name}' is already a group")
        agent = Agent(name, born=self.tick_count)
        agent.bond(name, at=self.tick_count)  # everyone has a relationship with themselves
        self.agents[name] = agent
        self.record("declare", f"{name} exists")
        return agent

    def _effect_agent(self, node: Utter, a, b) -> None:
        for name in node.slot(0, ()):
            self.bring_into_being(str(name), node)

    def utter(self, node: Utter) -> None:
        self._line = node.line
        spec = VOCABULARY[node.verb]
        a, b = self._principals(spec, node)
        scale = 1.0
        if spec.category == "emotion":
            explicit = self._numeric_slot(spec, node)
            scale = spec.base if explicit is None else explicit
        if spec.category == "emotion" and a is not None:
            claim = self._text_slot(spec, node)
            if claim is not None:
                self._stance_on_claim(a, node.verb, claim, scale)
                return
        applied: dict[str, dict[str, float]] = {}
        if a is not None and spec.charges:
            applied = self._apply_charges(spec, a, b if b is not None else a, scale)
        if a is not None:
            self._lay_memories(spec, a, b, applied)
        if spec.effect:
            getattr(self, f"_effect_{spec.effect}")(node, a, b)
        elif a is not None:
            target = f" -> {b.name}" if b is not None and b is not a else ""
            self.record("utter", f"{node.verb} {a.name}{target}")
        for agent in self.agents.values():
            agent.refresh_trust_ceilings()

    def _principals(self, spec: Utterance, node: Utter) -> tuple[Agent | None, Agent | None]:
        a = b = None
        for index, param in enumerate(spec.params):
            if param.rstrip("?") != "agent":
                continue
            value = node.slot(index)
            if value is None:
                continue
            agent = self.require(value, node)
            if a is None:
                a = agent
            elif b is None:
                b = agent
        return a, b

    @staticmethod
    def _text_slot(spec: Utterance, node: Utter) -> str | None:
        for index, param in enumerate(spec.params):
            if param.rstrip("?") == "text":
                value = node.slot(index)
                if value is not None:
                    return str(value)
        return None

    def _stance_on_claim(self, agent: Agent, emotion: str, claim: str, intensity: float) -> None:
        """An emotion aimed at a claim is a position on whether it happened."""
        matches = agent.find_memories(claim=claim)
        if not matches:
            matches = [
                agent.remember(
                    Memory(
                        claim=claim,
                        subject=agent.name,
                        kind="experienced",
                        signature={},
                        stances={"affirm": 0.0},
                        created_at=self.tick_count,
                    )
                )
            ]
        stance = claim_stance(emotion)
        for memory in matches:
            memory.stance(stance, intensity * 0.8)
            memory.signature[emotion] = max(memory.signature.get(emotion, 0.0), intensity)
            memory.salience = clamp(memory.salience + 0.05)
        self.record("stance", f'{agent.name}: {emotion} about "{claim}" ({stance} +{intensity * 0.8:.2f})')

    @staticmethod
    def _numeric_slot(spec: Utterance, node: Utter) -> float | None:
        for index, param in enumerate(spec.params):
            if param.rstrip("?") == "number":
                value = node.slot(index)
                if value is not None:
                    return float(value)
        return None

    def _edge(self, code: str, a: Agent, b: Agent):
        left = a if code[0] == "a" else b
        right = a if code[1] == "a" else b
        return left.bond(right.name, at=self.tick_count), left, right

    def _apply_charges(
        self, spec: Utterance, a: Agent, b: Agent, scale: float
    ) -> dict[str, dict[str, float]]:
        applied: dict[str, dict[str, float]] = {}
        for charge in spec.charges:
            bond, holder, _ = self._edge(charge.edge, a, b)
            delta = charge.delta * scale
            if charge.modulator == "receptivity":
                delta *= self._receptivity(bond.source, bond.target)
            bond.add(charge.emotion, delta)
            if delta > 0:
                applied.setdefault(charge.edge, {})[charge.emotion] = delta
            holder.refresh_trust_ceilings()
        return applied

    def _receptivity(self, holder: str, toward: str) -> float:
        """How much of an overture actually lands, given what is already there."""
        agent = self.agents.get(holder)
        bond = None if agent is None else agent.bonds.get(toward)
        if bond is None:
            return 0.5
        warm = bond.get("love") + bond.get("hope") + bond.get("gratitude") + 0.5 * bond.get("trust") + 0.38
        cold = 1.0 + 2.0 * bond.get("resentment") + bond.get("doubt") + bond.get("anger")
        return clamp(warm / cold)

    def _lay_memories(
        self, spec: Utterance, a: Agent, b: Agent | None, applied: dict[str, dict[str, float]]
    ) -> None:
        for memory_spec in spec.memories:
            holder = a if memory_spec.holder == "a" else b
            if holder is None:  # pragma: no cover - see TestVocabularyInvariants
                # No entry lays a memory on `b` while leaving `b` optional --
                # `betray`, `apologize` and `reject` all require both agents --
                # so this is a guard against a future table entry, not a path.
                continue
            names = {"a": a.name, "b": (b.name if b is not None else a.name)}
            about = None
            if memory_spec.about is not None:
                about = names[memory_spec.about]
            signature = dict(applied.get(memory_spec.signature, {}))
            holder.remember(
                Memory(
                    claim=memory_spec.claim.format(**names),
                    subject=holder.name,
                    about=about,
                    kind=memory_spec.kind,
                    signature=signature,
                    created_at=self.tick_count,
                )
            )

    # ------------------------------------------------------------------
    # utterance effects
    # ------------------------------------------------------------------
    def _effect_tick(self, node: Utter, a, b) -> None:
        count = node.slot(0, 1.0)
        steps = int(count)
        if steps < 1:
            raise self.fail(node, "tick needs a positive number of steps")
        for _ in range(steps):
            self.step()

    def _effect_settle(self, node: Utter, a, b) -> None:
        """Tick until the field goes quiet.

        Every other statement in Catharsis runs for a length fixed by the program
        text, which is why every program used to halt and why the language was
        strictly weaker than a Turing machine.  This one runs until no agent's
        pressure clears the action threshold -- a data-dependent stopping
        condition, and the missing ingredient.  A program using it may not
        terminate, which is the price of the power.

        The optional bound is a safety valve for programs that are meant to
        terminate; without it there is none, on purpose.
        """
        limit = node.slot(0)
        bound = int(limit) if limit is not None else None
        if bound is not None and bound < 1:
            raise self.fail(node, "settle needs a positive bound")
        started = self.tick_count
        idle = 0
        while bound is None or self.tick_count - started < bound:
            before = len(self.log)
            self.step()
            acted = any(event.kind == "act" for event in self.log[before:])
            # Quiet means quiet for a while.  A single actionless tick proves
            # nothing: habituation wears off at a fixed rate, so an agent that
            # cannot move this tick may well move in three.
            idle = 0 if acted else idle + 1
            if idle >= QUIET_TICKS:
                break
        self.record("settle", f"quiet after {self.tick_count - started} ticks")

    def _effect_observe(self, node: Utter, a, b) -> None:
        from .report import render_agent, render_group, render_world

        name = node.slot(0)
        if name is None:
            for line in render_world(self):
                self.emit(line)
            return
        if name in self.groups:
            for line in render_group(self, self.groups[name]):
                self.emit(line)
            return
        agent = self.require(name, node, "agent or group")
        for line in render_agent(self, agent):
            self.emit(line)

    def _effect_group(self, node: Utter, a, b) -> None:
        name = str(node.slot(0))
        if name in self.agents:
            raise self.fail(node, f"'{name}' is already an agent")
        self.groups.setdefault(name, Group(name))
        self.record("group", f"group {name} exists")

    def _effect_join(self, node: Utter, a: Agent, b) -> None:
        name = str(node.slot(1))
        group = self.groups.get(name)
        if group is None:
            raise self.fail(
                node,
                f"no group named '{name}'",
                suggest(name, self.groups) or f"declare it with 'group {name}'",
            )
        if a.name not in group.members:
            group.members.append(a.name)
            a.groups.append(name)
            group.required = 1.5 * len(group.members)
            # membership is a relationship, not a label
            for other in group.members:
                if other == a.name:
                    continue
                a.bond(other, at=self.tick_count).add("curiosity", 0.10)
                self.agents[other].bond(a.name, at=self.tick_count).add("curiosity", 0.10)
        self.record("join", f"{a.name} joined {name}")

    def _effect_goal(self, node: Utter, a, b) -> None:
        name = str(node.slot(0))
        dimension = node.slot(1)
        value = node.slot(2)
        if name in self.groups:
            group = self.groups[name]
            group.goal = str(value) if dimension is None else f"{dimension} {value}"
            group.required = 1.5 * max(1, len(group.members))
            self.record("goal", f"{name} wants {group.goal}")
            return
        agent = self.require(name, node, "agent or group")
        if isinstance(value, str) or dimension is None:
            agent.commitments.append(str(value) if dimension is None else f"{dimension}:{value}")
            self.record("goal", f"{agent.name} wants {agent.commitments[-1]}")
            return
        dimension = str(dimension)
        agent.goals[dimension] = float(value)
        agent.stances[dimension] = float(value)
        self.record("goal", f"{agent.name} wants {dimension} = {value:g}")

    def _effect_risk(self, node: Utter, a, b) -> None:
        resource = str(node.slot(0))
        self.risk[resource] = clamp(float(node.slot(1)))
        self.record("risk", f"{resource} is risky to give away ({self.risk[resource]:.2f})")

    def _effect_have(self, node: Utter, a: Agent, b) -> None:
        a.resources[str(node.slot(1))] = float(node.slot(2))
        self.record("have", f"{a.name} has {node.slot(2):g} {node.slot(1)}")

    def _effect_need(self, node: Utter, a: Agent, b) -> None:
        a.needs[str(node.slot(1))] = float(node.slot(2))
        self.record("need", f"{a.name} needs {node.slot(2):g} {node.slot(1)}")

    def _effect_trait(self, node: Utter, a: Agent, b) -> None:
        emotion = str(node.slot(1))
        if emotion not in DECAY:
            raise self.fail(
                node,
                f"'{emotion}' is not an emotion, so it cannot be a temperament",
                suggest(emotion, DECAY) or "temperaments are baselines on the twenty emotional axes",
            )
        a.traits[emotion] = clamp(float(node.slot(2)))
        a.self_bond.add(emotion, a.traits[emotion] * 0.5)
        self.record("trait", f"{a.name} is disposed to {emotion} ({a.traits[emotion]:.2f})")

    def _effect_gift(self, node: Utter, a: Agent, b: Agent) -> None:
        resource = str(node.slot(2))
        amount = float(node.slot(3, 1.0))
        a.resources[resource] = a.resources.get(resource, 0.0) - amount
        b.resources[resource] = b.resources.get(resource, 0.0) + amount
        b.remember(
            Memory(
                claim=f"{a.name} gave {b.name} {resource}",
                subject=b.name,
                about=a.name,
                kind="experienced",
                signature={"gratitude": 0.40},
                created_at=self.tick_count,
            )
        )
        self.record("gift", f"{a.name} gave {b.name} {amount:g} {resource}")

    def _effect_betray(self, node: Utter, a: Agent, b: Agent) -> None:
        claim = node.slot(2)
        if isinstance(claim, str):
            for memory in b.find_memories(about=a.name):
                if memory.created_at == self.tick_count:
                    memory.claim = claim
            for memory in a.find_memories(about=b.name):
                if memory.created_at == self.tick_count:
                    memory.claim = claim
        self.record("betray", f"{a.name} betrayed {b.name}")

    def _effect_forgive(self, node: Utter, a: Agent, b: Agent) -> None:
        touched = 0
        for memory in a.find_memories(about=b.name):
            if memory.reconciled or memory.kind == "own":
                continue
            memory.reconciled = True
            memory.reconciled_at = self.tick_count
            touched += 1
        a.refresh_trust_ceilings()
        ceiling = a.bond(b.name).trust_ceiling
        self.record(
            "forgive",
            f"{a.name} forgave {b.name}: {touched} memories disarmed, none deleted "
            f"(trust ceiling {ceiling:.2f})",
        )

    def _effect_witness(self, node: Utter, a: Agent, b: Agent) -> None:
        observer, actor = a, b
        event_word = str(node.slot(2))
        target_name = node.slot(3)
        from .vocabulary import lookup

        spec = lookup(event_word)
        if spec is None:
            raise self.fail(
                node,
                f"'{event_word}' is not something that can be witnessed",
                suggest(event_word, VOCABULARY),
            )
        victim = self.require(target_name, node) if target_name is not None else None
        damping = WITNESS_DAMPING
        bond = observer.bond(actor.name, at=self.tick_count)
        signature: dict[str, float] = {}
        for charge in spec.charges:
            if charge.edge != "ba":  # step into the victim's shoes, damped
                continue
            delta = charge.delta * damping
            bond.add(charge.emotion, delta)
            if delta > 0:
                signature[charge.emotion] = delta
        observer.self_bond.add("surprise", 0.20)
        names = {"a": actor.name, "b": victim.name if victim else "someone"}
        claim = spec.memories[0].claim.format(**names) if spec.memories else f"{actor.name} {spec.name}"
        observer.remember(
            Memory(
                claim=claim,
                subject=observer.name,
                about=actor.name,
                kind="witnessed",
                signature=signature,
                created_at=self.tick_count,
            )
        )
        if victim is not None:
            observer.bond(victim.name, at=self.tick_count).add("grief", 0.12)
        observer.refresh_trust_ceilings()
        self.record("witness", f"{observer.name} saw {actor.name} {spec.name} {names['b']}")

    def _effect_remember(self, node: Utter, a: Agent, b: Agent | None) -> None:
        claim = node.slot(1)
        if claim is None:
            from .report import render_memories

            for line in render_memories(self, a):
                self.emit(line)
            return
        signature = {emotion: value * 0.5 for emotion, value in a.self_bond.charge.items() if value > 0.05}
        about = b.name if b is not None else None
        if b is not None:
            for emotion, value in a.bond(b.name).charge.items():
                if value > 0.05:
                    signature[emotion] = signature.get(emotion, 0.0) + value * 0.6
        a.remember(
            Memory(
                claim=str(claim),
                subject=a.name,
                about=about,
                kind="experienced",
                signature=signature,
                created_at=self.tick_count,
            )
        )
        self.record("remember", f'{a.name} remembers "{claim}"')

    def _effect_recall(self, node: Utter, a: Agent, b) -> None:
        from .report import render_memories, render_memory

        claim = node.slot(1)
        if claim is None:
            for line in render_memories(self, a):
                self.emit(line)
            return
        matches = a.find_memories(claim=str(claim))
        if not matches:
            self.emit(f'{a.name} has no memory of "{claim}"')
            self.record("recall", f'{a.name} could not recall "{claim}"')
            return
        self.emit(f"{a.name} recalls, at tick {self.tick_count}:")
        for memory in matches:
            memory.salience = clamp(memory.salience + 0.10)
            immediate: dict[tuple[str, str, str], float] = {}
            self._pull(immediate, a, memory, 0.60)  # remembering is not free
            self._apply_deltas(immediate)
            for line in render_memory(self, a, memory):
                self.emit(line)
        self.record("recall", f'{a.name} recalled "{claim}"')

    def _effect_denial(self, node: Utter, a: Agent, b) -> None:
        claim = str(node.slot(1))
        matches = a.find_memories(claim=claim)
        if not matches:
            matches = [
                a.remember(
                    Memory(
                        claim=claim,
                        subject=a.name,
                        kind="experienced",
                        signature={},
                        stances={"affirm": 0.0},
                        created_at=self.tick_count,
                    )
                )
            ]
        for memory in matches:
            memory.stance("deny", 0.5)
            memory.suppressed = True
        self.record("denial", f'{a.name} denies "{claim}" (kept, suppressed, still ruminating)')

    def _effect_acceptance(self, node: Utter, a: Agent, b) -> None:
        claim = node.slot(1)
        if claim is not None:
            matches = a.find_memories(claim=str(claim))
            if not matches:
                raise self.fail(node, f'{a.name} has no memory of "{claim}" to accept')
            for memory in matches:
                affirm = memory.stances.get("affirm", 0.0) + 0.4 * memory.stances.get("hope", 0.0)
                deny = memory.stances.get("deny", 0.0) + 0.6 * memory.stances.get("doubt", 0.0)
                loser = min(affirm, deny)
                winner = "affirm" if affirm >= deny else "deny"
                memory.stances = {winner: 1.0}
                memory.suppressed = False
                memory.stance(winner, 0.0)
                a.self_bond.add("grief", 0.15 * memory.weight + 0.10 * loser)
                a.self_bond.add("sadness", 0.10 * loser)
                self.record("acceptance", f'{a.name} accepts "{memory.claim}" as {winner}')
            return
        resolved = self._collapse_tension(a)
        closed = 0
        for branch in a.branches:
            if not branch.closed:
                branch.closed = True
                branch.closed_at = self.tick_count
                closed += 1
                a.self_bond.add("grief", 0.10)
        a.self_bond.set("regret", a.self_bond.get("regret") * 0.3)
        self.record(
            "acceptance",
            f"{a.name} accepts what is: {resolved} contradictions collapsed, {closed} alternate histories closed",
        )

    def _collapse_tension(self, agent: Agent) -> int:
        from .field import ANTAGONISTS

        resolved = 0
        for bond in agent.bonds.values():
            for left, right, _weight in ANTAGONISTS:
                low_name = left if bond.get(left) <= bond.get(right) else right
                overlap = min(bond.get(left), bond.get(right))
                if overlap < 0.15:
                    continue
                # The losing side is cut back to a quarter of itself, and the
                # difference is paid out as grief: resolving a contradiction
                # costs you whichever half you gave up.
                bond.set(low_name, bond.get(low_name) * 0.25)
                agent.self_bond.add("grief", overlap * 0.35)
                agent.self_bond.add("sadness", overlap * 0.20)
                resolved += 1
        return resolved

    def _effect_choice(self, node: Utter, a: Agent, b) -> None:
        option = str(node.slot(1))
        alternative = node.slot(2)
        a.timeline.append(Choice(option, None if alternative is None else str(alternative), self.tick_count))
        a.remember(
            Memory(
                claim=f"{a.name} chose '{option}'",
                subject=a.name,
                kind="own",
                signature={
                    emotion: value * 0.4 for emotion, value in a.self_bond.charge.items() if value > 0.05
                },
                created_at=self.tick_count,
            )
        )
        self.record("choice", f'{a.name} chose "{option}"')

    def _effect_regret(self, node: Utter, a: Agent, b) -> None:
        if not a.timeline:
            raise self.fail(
                node,
                f"{a.name} has made no choice to regret",
                f'record one first, e.g. choice {a.name} "leave" "stay"',
            )
        point = a.timeline[-1]
        named = node.slot(1)
        untaken = str(named) if named is not None else (point.alternative or f"not {point.option}")
        for branch in a.branches:
            if branch.point is point and branch.untaken == untaken:
                branch.visits += 1
                branch.closed = False
                branch.idealization = min(0.9, branch.idealization + 0.10)
                self.record("regret", f'{a.name} returns to "{untaken}" again (visit {branch.visits})')
                return
        actual = a.wellbeing()
        a.branches.append(
            Branch(
                point=point,
                taken=point.option,
                untaken=untaken,
                forked_at=self.tick_count,
                valuation=actual,
                actual_at_fork=actual,
                visits=1,
            )
        )
        self.record("regret", f'{a.name} keeps "{untaken}" alive beside "{point.option}"')

    def _effect_propose(self, node: Utter, a: Agent, b: Agent) -> None:
        shared = sorted(set(a.goals) & set(b.goals))
        opened = []
        for dimension in shared:
            if self._negotiation(a.name, b.name, dimension) is not None:
                continue
            gap = abs(a.stances[dimension] - b.stances[dimension])
            self.negotiations.append(
                Negotiation(
                    left=a.name,
                    right=b.name,
                    dimension=dimension,
                    opened_at=self.tick_count,
                    initial_gap=gap,
                )
            )
            opened.append(dimension)
        if opened:
            self.record("propose", f"{a.name} opened talks with {b.name} over {', '.join(opened)}")
        else:
            b.remember(
                Memory(
                    claim=f"{a.name} made an offer to {b.name}",
                    subject=b.name,
                    about=a.name,
                    kind="experienced",
                    signature={"hope": 0.15},
                    created_at=self.tick_count,
                )
            )
            self.record("propose", f"{a.name} made {b.name} an offer with nothing measurable in it")

    def _negotiation(self, left: str, right: str, dimension: str | None = None) -> Negotiation | None:
        for negotiation in self.negotiations:
            if negotiation.status != "open":
                continue
            if {negotiation.left, negotiation.right} != {left, right}:
                continue
            if dimension is None or negotiation.dimension == dimension:
                return negotiation
        return None

    def _effect_reject(self, node: Utter, a: Agent, b: Agent) -> None:
        negotiation = self._negotiation(a.name, b.name)
        if negotiation is not None:
            negotiation.rounds += 1
        self.record("reject", f"{a.name} rejected {b.name}")

    def _effect_agree(self, node: Utter, a: Agent, b: Agent) -> None:
        closed = []
        for negotiation in self.negotiations:
            if negotiation.status != "open" or {negotiation.left, negotiation.right} != {a.name, b.name}:
                continue
            self._settle(negotiation)
            closed.append(negotiation.dimension)
        if closed:
            self.record("agree", f"{a.name} and {b.name} settled {', '.join(closed)}")
        else:
            self.record("agree", f"{a.name} and {b.name} agree, with nothing on the table")

    # ------------------------------------------------------------------
    # the tick
    # ------------------------------------------------------------------
    def step(self) -> None:
        self.tick_count += 1
        self._decay()
        deltas: dict[tuple[str, str, str], float] = {}
        self._temperament(deltas)
        self._couple(deltas)
        self._spill(deltas)
        self._ruminate(deltas)
        self._needs(deltas)
        self._contagion(deltas)
        self._apply_deltas(deltas)
        self._regret()
        self._negotiate()
        self._act()
        self._collectives()
        for agent in self.agents.values():
            agent.rest()
            agent.refresh_trust_ceilings()
        self.capture(f"tick {self.tick_count}", "tick")

    def _apply_deltas(self, deltas: dict[tuple[str, str, str], float]) -> None:
        for (holder, target, emotion), delta in deltas.items():
            self.agents[holder].bond(target, at=self.tick_count).add(emotion, delta)

    @staticmethod
    def _add(
        deltas: dict[tuple[str, str, str], float], holder: str, target: str, emotion: str, delta: float
    ) -> None:
        key = (holder, target, emotion)
        deltas[key] = deltas.get(key, 0.0) + delta

    def _decay(self) -> None:
        for agent in self.agents.values():
            for bond in agent.bonds.values():
                for emotion in list(bond.charge):
                    value = bond.charge[emotion] * (1.0 - DECAY[emotion])
                    if value < 1e-4:
                        del bond.charge[emotion]
                    else:
                        bond.charge[emotion] = value

    def _temperament(self, deltas) -> None:
        for agent in self.agents.values():
            for emotion, baseline in agent.traits.items():
                current = agent.self_bond.get(emotion)
                self._add(deltas, agent.name, agent.name, emotion, (baseline - current) * TEMPERAMENT_RATE)

    def _couple(self, deltas) -> None:
        for agent in self.agents.values():
            for bond in agent.bonds.values():
                for source, target, rate in COUPLING:
                    value = bond.get(source)
                    if value <= 1e-4:
                        continue
                    self._add(deltas, bond.source, bond.target, target, rate * value)

    def _spill(self, deltas) -> None:
        for agent in self.agents.values():
            for bond in agent.others():
                for source, target, rate in SPILL:
                    value = bond.get(source)
                    if value <= 1e-4:
                        continue
                    self._add(deltas, agent.name, agent.name, target, rate * value)

    def _ruminate(self, deltas) -> None:
        for agent in self.agents.values():
            for memory in agent.memories:
                memory.fade()
                self._pull(deltas, agent, memory, RUMINATION)

    def _pull(self, deltas, agent: Agent, memory: Memory, rate: float) -> None:
        """Move a bond toward the level its memory sustains, never past it."""
        target = memory.about if memory.about in self.agents else agent.name
        bond = agent.bond(target, at=self.tick_count)
        for emotion, level in memory.rumination().items():
            shortfall = level - bond.get(emotion)
            if shortfall > 0:
                self._add(deltas, agent.name, target, emotion, rate * shortfall)

    def _needs(self, deltas) -> None:
        for agent in self.agents.values():
            for resource, needed in sorted(agent.needs.items()):
                if needed <= 0:
                    continue
                deficit = max(0.0, needed - agent.resources.get(resource, 0.0)) / needed
                if deficit <= 0:
                    continue
                self._add(deltas, agent.name, agent.name, "fear", 0.09 * deficit)
                self._add(deltas, agent.name, agent.name, "sadness", 0.05 * deficit)
                mine = agent.resources.get(resource, 0.0)
                for other in agent.bonds:
                    if other == agent.name:
                        continue
                    theirs = self.agents[other].resources.get(resource, 0.0)
                    if theirs > mine:
                        self._add(deltas, agent.name, other, "envy", 0.07 * deficit)

    def _contagion(self, deltas) -> None:
        """Feeling travels along relationships, in proportion to trust.

        This is the whole of reputation.  Nothing anywhere keeps a score.
        """
        for observer in self.agents.values():
            for link in observer.others():
                credence = link.get("trust") * (1.0 - 0.6 * link.get("doubt"))
                if credence < CONTAGION_FLOOR:
                    continue
                source = self.agents.get(link.target)
                if source is None:
                    continue
                for onward in source.others():
                    if onward.target == observer.name:
                        continue
                    mine = observer.bonds.get(onward.target)
                    for emotion, transmissibility in TRANSMISSIBILITY.items():
                        value = onward.get(emotion)
                        if value <= 0.05:
                            continue
                        # What you catch is bounded by what they feel, damped by
                        # how much you believe them.  Hearsay relaxes toward that
                        # ceiling and then stops.
                        ceiling = HEARSAY * credence * transmissibility * value
                        held = 0.0 if mine is None else mine.get(emotion)
                        flow = CONTAGION * (ceiling - held)
                        if flow < 0.002:
                            continue
                        if mine is None and flow < 0.010:
                            continue  # too faint to make a stranger matter
                        self._add(deltas, observer.name, onward.target, emotion, flow)

    def _regret(self) -> None:
        for agent in self.agents.values():
            if not agent.branches:
                continue
            actual = agent.wellbeing()
            pressure = 0.0
            for branch in agent.branches:
                branch.drift()
                pressure = max(pressure, branch.pressure(actual))
            if pressure > agent.self_bond.get("regret"):
                agent.self_bond.set("regret", pressure)

    # ------------------------------------------------------------------
    # negotiation: no algorithm, only what each side can bear to give up
    # ------------------------------------------------------------------
    def _negotiate(self) -> None:
        for negotiation in self.negotiations:
            if negotiation.status != "open":
                continue
            left = self.agents[negotiation.left]
            right = self.agents[negotiation.right]
            dimension = negotiation.dimension
            gap = right.stances[dimension] - left.stances[dimension]
            tolerance = max(0.02 * max(negotiation.initial_gap, 1.0), 0.5)
            if abs(gap) <= tolerance:
                self._settle(negotiation)
                continue
            left_rate = self._concession(left, right)
            right_rate = self._concession(right, left)
            left_move = gap * min(MAX_CONCESSION, left_rate)
            right_move = -gap * min(MAX_CONCESSION, right_rate)
            left.stances[dimension] += left_move
            right.stances[dimension] += right_move
            negotiation.rounds += 1
            negotiation.concessions[left.name] = negotiation.concessions.get(left.name, 0.0) + abs(left_move)
            negotiation.concessions[right.name] = negotiation.concessions.get(right.name, 0.0) + abs(
                right_move
            )
            # whoever gave more this round feels it
            difference = abs(left_move) - abs(right_move)
            scale = abs(gap) if gap else 1.0
            if abs(difference) > 1e-9 and scale > 0:
                giver, taker = (left, right) if difference > 0 else (right, left)
                magnitude = min(0.06, abs(difference) / scale * 0.20)
                giver.bond(taker.name, at=self.tick_count).add("resentment", magnitude)
                giver.self_bond.add("sadness", magnitude * 0.5)
                taker.self_bond.add("pride", magnitude * 0.8)
            if self._collapsed(left, right) and self._collapsed(right, left):
                negotiation.status = "impasse"
                negotiation.closed_at = self.tick_count
                for one, two in ((left, right), (right, left)):
                    one.bond(two.name, at=self.tick_count).add("resentment", 0.20)
                    one.self_bond.add("sadness", 0.15)
                    one.remember(
                        Memory(
                            claim=f"talks with {two.name} over {dimension} collapsed",
                            subject=one.name,
                            about=two.name,
                            kind="experienced",
                            signature={"resentment": 0.20, "sadness": 0.10},
                            created_at=self.tick_count,
                        )
                    )
                self.record("impasse", f"{left.name} and {right.name} broke off talks over {dimension}")
            elif negotiation.rounds > 60:  # pragma: no cover - see TestPatienceIsNeverNeeded
                # A safety net that cannot fire.  Conceding deposits sadness on
                # the conceder, and sadness is a term in `yielding`, so every
                # round makes the next concession larger: talks accelerate
                # toward agreement, or collapse in feeling first.  Kept because
                # it is cheap and the physics is meant to be argued with.
                negotiation.status = "impasse"
                negotiation.closed_at = self.tick_count
                self.record("impasse", f"{left.name} and {right.name} ran out of patience over {dimension}")

    def _concession(self, agent: Agent, other: Agent) -> float:
        """How far somebody will move, derived entirely from how they feel."""
        bond = agent.bond(other.name, at=self.tick_count)
        me = agent.self_bond
        yielding = (
            0.8 * bond.get("trust")
            + 0.6 * bond.get("hope")
            + 0.9 * bond.get("guilt")
            + 0.5 * bond.get("love")
            + 0.7 * bond.get("fear")
            + 0.7 * me.get("fear")
            + 0.3 * me.get("loneliness")
            + 0.4 * me.get("sadness")
            + 0.2
        )
        holding = (
            1.0
            + 2.0 * me.get("pride")
            + 1.5 * bond.get("anger")
            + 1.5 * bond.get("resentment")
            + 0.5 * bond.get("doubt")
            + 0.8 * bond.get("envy")
        )
        return 0.35 * yielding / holding

    @staticmethod
    def _collapsed(agent: Agent, other: Agent) -> bool:
        bond = agent.bond(other.name)
        return bond.get("hope") < 0.10 and (bond.get("anger") + bond.get("resentment")) > 0.90

    def _settle(self, negotiation: Negotiation) -> None:
        left = self.agents[negotiation.left]
        right = self.agents[negotiation.right]
        dimension = negotiation.dimension
        agreement = (left.stances[dimension] + right.stances[dimension]) / 2.0
        negotiation.status = "agreed"
        negotiation.agreement = agreement
        negotiation.closed_at = self.tick_count
        for one, two in ((left, right), (right, left)):
            one.stances[dimension] = agreement
            bond = one.bond(two.name, at=self.tick_count)
            bond.add("gratitude", 0.25)
            bond.add("trust", 0.15)
            bond.add("joy", 0.25)
            distance = abs(agreement - one.goals[dimension])
            span = max(abs(one.goals[dimension] - two.goals[dimension]), 1.0)
            one.self_bond.add("pride", clamp(0.35 * (1.0 - distance / span)))
            one.self_bond.add("sadness", clamp(0.25 * (distance / span)))
            one.remember(
                Memory(
                    claim=f"{one.name} and {two.name} settled {dimension} at {agreement:.1f}",
                    subject=one.name,
                    about=two.name,
                    kind="experienced",
                    signature={"gratitude": 0.25, "joy": 0.20},
                    created_at=self.tick_count,
                )
            )
        self.record(
            "agreement",
            f"{left.name} and {right.name} agreed {dimension} = {agreement:.1f} "
            f"after {negotiation.rounds} rounds",
        )

    # ------------------------------------------------------------------
    # action selection
    # ------------------------------------------------------------------
    def _act(self) -> None:
        decisions: list[Decision] = []
        for agent in self.agents.values():
            decision = self._decide(agent)
            if decision is not None:
                decisions.append(decision)
        for decision in decisions:
            agent = self.agents[decision.agent]
            agent.tire(decision.action, decision.target, ACTION_BY_NAME[decision.action].habituation)
            getattr(self, f"_act_{decision.action}")(agent, self.agents[decision.target])

    def _decide(self, agent: Agent) -> Decision | None:
        best: Decision | None = None
        for action in ACTIONS:
            targets = [bond.target for bond in agent.others()] if action.scope == "bond" else [agent.name]
            for target_name in targets:
                target = self.agents.get(target_name)
                if target is None:
                    continue
                if not self._precondition(action, agent, target):
                    continue
                pressure = self._pressure(action, agent, target)
                if best is None or pressure > best.pressure:
                    best = Decision(agent.name, action.name, target_name, pressure)
        if best is None or best.pressure < THRESHOLD:
            return None
        return best

    def _pressure(self, action: Action, agent: Agent, target: Agent) -> float:
        edge = agent.bonds.get(target.name)

        def read(key: str) -> float:
            if key.startswith("self:"):
                return agent.self_bond.get(key[5:])
            if key.startswith("their:"):
                back = target.bonds.get(agent.name)
                return 0.0 if back is None else back.get(key[6:])
            if key == "deficit":
                return self._deficit(agent)
            if key == "their_need":
                # How much somebody's need moves you depends on what they are
                # asking for.  Nobody hands over the keys because the asker
                # looks like they could use them.
                return self._deficit(target) * (1.0 - self._exposure(agent, target))
            if key == "own_need":
                # Short of *this* thing, specifically.  A person with nothing in
                # the cupboard is not thereby unwilling to lend a book.
                resource = self._giveable_resource(agent, target)
                if resource is None:
                    return 0.0
                needed = agent.needs.get(resource, 0.0)
                if needed <= 0:
                    return 0.0
                return clamp(max(0.0, needed - agent.resources.get(resource, 0.0)) / needed)
            if key == "exposure":
                # What you would be handing over, weighed against how far you
                # actually trust the person asking.  For a harmless resource
                # this is zero and the term disappears.
                bond = agent.bonds.get(target.name)
                trust = 0.0 if bond is None else bond.get("trust")
                return self._exposure(agent, target) * (1.0 - trust)
            if key == "group_trust":
                return self._group_feeling(agent, "trust")
            if key == "group_doubt":
                return self._group_feeling(agent, "doubt")
            return 0.0 if edge is None else edge.get(key)

        score = sum(weight * read(key) for key, weight in action.affinity.items())
        score -= sum(weight * read(key) for key, weight in action.inhibit.items())
        ambivalence = edge.tension if edge is not None else agent.self_bond.tension
        score /= 1.0 + ambivalence
        score -= 0.75 * agent.act_cost(action.name, target.name)
        score += (jitter(agent.name, target.name, action.name, self.tick_count) - 0.5) * 0.01
        return score

    def _deficit(self, agent: Agent) -> float:
        total = 0.0
        for resource, needed in agent.needs.items():
            if needed > 0:
                total += max(0.0, needed - agent.resources.get(resource, 0.0)) / needed
        return clamp(total)

    def _group_feeling(self, agent: Agent, emotion: str) -> float:
        values = []
        for group_name in agent.groups:
            for member in self.groups[group_name].members:
                if member == agent.name:
                    continue
                bond = agent.bonds.get(member)
                values.append(0.0 if bond is None else bond.get(emotion))
        return sum(values) / len(values) if values else 0.0

    def _precondition(self, action: Action, agent: Agent, target: Agent) -> bool:
        requirement = action.requires
        if requirement is None:
            return True
        if requirement == "has_memory":
            return bool(agent.memories)
        if requirement == "has_guilt":
            bond = agent.bonds.get(target.name)
            return bond is not None and bond.get("guilt") >= 0.10
        if requirement == "can_confide":
            bond = agent.bonds.get(target.name)
            if bond is None or bond.get("trust") < 0.15:
                return False  # you tell things to people you trust
            return bool(self._tellable(agent, target))
        if requirement == "can_take":
            return self._contested_resource(agent, target) is not None
        if requirement == "can_give":
            return self._giveable_resource(agent, target) is not None
        if requirement == "can_ask":
            return self._giveable_resource(target, agent) is not None
        if requirement == "can_imitate":
            return bool(set(target.traits) - set(agent.traits)) or bool(set(target.goals) - set(agent.goals))
        if requirement == "can_seek":
            return any(name not in agent.bonds for name in self.agents if name != agent.name)
        if requirement == "has_group_goal":
            return any(
                self.groups[name].goal is not None and self.groups[name].achieved_at is None
                for name in agent.groups
            )
        return True  # pragma: no cover - unknown requirement is a table bug

    #: A resource this risky is a capability rather than a good: it exists only
    #: because its holder confers it, so it cannot be carried off.  Commit access
    #: cannot be stolen from someone the way bread can.
    TAKEABLE_RISK = 0.5

    def _contested_resource(self, agent: Agent, target: Agent) -> str | None:
        best = None
        margin = 0.0
        for resource, amount in sorted(target.resources.items()):
            if self.risk.get(resource, 0.0) > self.TAKEABLE_RISK:
                continue
            if amount - agent.resources.get(resource, 0.0) > margin:
                margin = amount - agent.resources.get(resource, 0.0)
                best = resource
        return best if margin >= 1.0 else None

    def _exposure(self, agent: Agent, target: Agent) -> float:
        """How dangerous the thing this agent would hand over actually is."""
        resource = self._giveable_resource(agent, target)
        return 0.0 if resource is None else self.risk.get(resource, 0.0)

    def _giveable_resource(self, agent: Agent, target: Agent) -> str | None:
        for resource, needed in sorted(target.needs.items()):
            short = needed - target.resources.get(resource, 0.0)
            spare = agent.resources.get(resource, 0.0) - agent.needs.get(resource, 0.0)
            if short > 0 and spare >= 1.0:
                return resource
        return None

    # ------------------------------------------------------------------
    # what the actions do
    # ------------------------------------------------------------------
    def _act_reach_out(self, agent: Agent, target: Agent) -> None:
        bond = agent.bond(target.name, at=self.tick_count)
        bond.add("love", 0.06)
        bond.add("hope", 0.04)
        agent.self_bond.add("loneliness", -0.10)
        welcome = self._receptivity(target.name, agent.name)
        back = target.bond(agent.name, at=self.tick_count)
        if welcome >= 0.35:
            back.add("love", 0.05 * welcome)
            back.add("gratitude", 0.08 * welcome)
            back.add("trust", 0.03 * welcome)
            target.self_bond.add("loneliness", -0.06)
            self.record("act", f"{agent.name} reached out to {target.name}, and was met")
        else:
            bond.add("doubt", 0.08)
            agent.self_bond.add("sadness", 0.08)
            agent.self_bond.add("shame", 0.05)
            back.add("doubt", 0.03)
            self.record("act", f"{agent.name} reached out to {target.name} and found nothing there")

    def _act_confide(self, agent: Agent, target: Agent) -> None:
        memory = self._tellable(agent, target)
        if memory is None:
            return
        belief = target.bond(agent.name, at=self.tick_count).get("trust")
        copy = Memory(
            claim=memory.claim,
            subject=target.name,
            about=memory.about,
            kind="told",
            signature={emotion: value * 0.5 for emotion, value in memory.signature.items()},
            salience=min(0.7, memory.salience * 0.7),
            stances={"affirm": clamp(0.2 + belief), "doubt": clamp(1.0 - belief)},
            created_at=self.tick_count,
            source=agent.name,
        )
        stored = target.remember(copy)
        if memory.about is not None and memory.about in self.agents and memory.about != target.name:
            immediate: dict[tuple[str, str, str], float] = {}
            self._pull(immediate, target, stored, 0.60 * belief)
            self._apply_deltas(immediate)
        agent.bond(target.name, at=self.tick_count).add("trust", 0.03)
        agent.self_bond.add("loneliness", -0.06)
        target.refresh_trust_ceilings()
        self.record("act", f'{agent.name} told {target.name} "{memory.claim}"')

    @staticmethod
    def _tellable(agent: Agent, target: Agent) -> Memory | None:
        """The memory an agent would pass on.

        Never one about the listener, and never one they already have: people
        tell each other news.  Without that second rule two friends retell the
        same story forever and talk themselves into a rage.
        """
        known = {(m.claim, m.about) for m in target.memories}
        candidates = [
            m
            for m in agent.memories
            if m.about not in (None, target.name) and (m.claim, m.about) not in known and m.kind != "own"
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda m: (m.salience * m.weight, m.claim))

    def _act_confront(self, agent: Agent, target: Agent) -> None:
        bond = agent.bond(target.name, at=self.tick_count)
        bond.add("anger", -0.30)
        bond.add("resentment", -0.06)
        back = target.bond(agent.name, at=self.tick_count)
        back.add("fear", 0.20)
        back.add("anger", 0.22)
        back.add("doubt", 0.08)
        target.self_bond.add("sadness", 0.08)
        target.remember(
            Memory(
                claim=f"{agent.name} confronted {target.name}",
                subject=target.name,
                about=agent.name,
                kind="experienced",
                signature={"fear": 0.20, "anger": 0.22},
                created_at=self.tick_count,
            )
        )
        self.record("act", f"{agent.name} confronted {target.name}")

    def _act_withdraw(self, agent: Agent, target: Agent) -> None:
        bond = agent.bond(target.name, at=self.tick_count)
        for emotion in ("love", "trust", "hope"):
            bond.set(emotion, bond.get(emotion) * 0.85)
        agent.self_bond.add("loneliness", 0.08)
        agent.self_bond.add("sadness", 0.05)
        target.self_bond.add("loneliness", 0.05)
        target.bond(agent.name, at=self.tick_count).add("doubt", 0.05)
        self.record("act", f"{agent.name} withdrew from {target.name}")

    def _act_compete(self, agent: Agent, target: Agent) -> None:
        resource = self._contested_resource(agent, target)
        if resource is None:
            return
        if self._standing(agent) > self._standing(target):
            agent.resources[resource] = agent.resources.get(resource, 0.0) + 1.0
            target.resources[resource] = target.resources.get(resource, 0.0) - 1.0
            agent.self_bond.add("joy", 0.15)
            agent.self_bond.add("pride", 0.10)
            back = target.bond(agent.name, at=self.tick_count)
            back.add("anger", 0.30)
            back.add("resentment", 0.25)
            back.add("doubt", 0.20)
            target.self_bond.add("sadness", 0.10)
            target.remember(
                Memory(
                    claim=f"{agent.name} took {resource} from {target.name}",
                    subject=target.name,
                    about=agent.name,
                    kind="experienced",
                    signature={"anger": 0.30, "resentment": 0.25, "doubt": 0.20},
                    created_at=self.tick_count,
                )
            )
            target.refresh_trust_ceilings()
            self.record("act", f"{agent.name} took {resource} from {target.name}")
        else:
            agent.self_bond.add("shame", 0.15)
            agent.self_bond.add("sadness", 0.10)
            bond = agent.bond(target.name, at=self.tick_count)
            bond.add("envy", 0.10)
            bond.add("fear", 0.10)
            target.self_bond.add("pride", 0.08)
            self.record("act", f"{agent.name} tried to take {resource} from {target.name} and failed")

    def _standing(self, agent: Agent) -> float:
        """How hard somebody will push. Desperation counts for as much as pride."""
        me = agent.self_bond
        return (
            me.get("pride")
            + me.get("anger")
            + 0.5 * me.get("joy")
            + 0.6 * self._deficit(agent)
            - 0.6 * me.get("fear")
            - 0.4 * me.get("shame")
        )

    def _act_give(self, agent: Agent, target: Agent) -> None:
        resource = self._giveable_resource(agent, target)
        if resource is None:
            return
        agent.resources[resource] = agent.resources.get(resource, 0.0) - 1.0
        target.resources[resource] = target.resources.get(resource, 0.0) + 1.0
        back = target.bond(agent.name, at=self.tick_count)
        back.add("gratitude", 0.25)
        back.add("trust", 0.10)
        bond = agent.bond(target.name, at=self.tick_count)
        bond.add("guilt", -0.50)  # meeting the need is what discharges it
        bond.add("love", 0.04)
        agent.self_bond.add("pride", 0.06)
        agent.self_bond.add("joy", 0.10)
        target.remember(
            Memory(
                claim=f"{agent.name} gave {target.name} {resource}",
                subject=target.name,
                about=agent.name,
                kind="experienced",
                signature={"gratitude": 0.25},
                created_at=self.tick_count,
            )
        )
        self.record("act", f"{agent.name} gave {target.name} {resource}")

    def _act_ask(self, agent: Agent, target: Agent) -> None:
        resource = self._giveable_resource(target, agent)
        if resource is None:
            return
        bond = agent.bond(target.name, at=self.tick_count)
        bond.add("hope", 0.12)
        agent.self_bond.add("shame", 0.03)  # asking costs something
        agent.self_bond.add("pride", -0.04)
        surplus = target.resources.get(resource, 0.0) - target.needs.get(resource, 0.0)
        back = target.bond(agent.name, at=self.tick_count)
        # A request you could meet and have not met yet.  The more obviously you
        # could meet it, the heavier it sits.
        back.add("guilt", 0.18 + 0.06 * min(3.0, surplus))
        back.add("curiosity", 0.06)
        target.remember(
            Memory(
                claim=f"{agent.name} asked {target.name} for {resource}",
                subject=target.name,
                about=agent.name,
                kind="experienced",
                signature={"guilt": 0.18},
                created_at=self.tick_count,
            )
        )
        self.record("act", f"{agent.name} asked {target.name} for {resource}")

    def _act_repair(self, agent: Agent, target: Agent) -> None:
        spec = VOCABULARY["apologize"]
        applied = self._apply_charges(spec, agent, target, 1.0)
        self._lay_memories(spec, agent, target, applied)
        landed = self._receptivity(target.name, agent.name)
        self.record("act", f"{agent.name} apologised to {target.name} (landed {landed:.0%})")

    def _act_imitate(self, agent: Agent, target: Agent) -> None:
        borrowed = None
        for name, value in sorted(target.traits.items()):
            if name not in agent.traits:
                agent.traits[name] = value * 0.7
                borrowed = f"a disposition to {name}"
                break
        if borrowed is None:
            for name, value in sorted(target.goals.items()):
                if name not in agent.goals:
                    agent.goals[name] = value
                    agent.stances[name] = value
                    borrowed = f"a goal about {name}"
                    break
        if borrowed is None:
            return
        bond = agent.bond(target.name, at=self.tick_count)
        bond.add("envy", -0.20)
        bond.add("curiosity", -0.05)
        target.self_bond.add("pride", 0.06)
        agent.self_bond.add("shame", 0.03)
        self.record("act", f"{agent.name} took {borrowed} from {target.name}")

    def _act_probe(self, agent: Agent, target: Agent) -> None:
        bond = agent.bond(target.name, at=self.tick_count)
        bond.add("curiosity", -0.15)
        found = [
            m for m in target.memories if m.about is not None and m.kind != "own" and m.about != agent.name
        ]
        if not found:
            bond.add("doubt", -0.05)
            self.record("act", f"{agent.name} looked into {target.name} and found nothing")
            return
        memory = max(found, key=lambda m: (m.salience * m.weight, m.claim))
        mine = agent.find_memories(claim=memory.claim)
        if mine and abs(mine[0].confidence - memory.confidence) > 0.30:
            for existing in mine:
                existing.stance("doubt", 0.30)
            bond.add("doubt", 0.10)
            self.record("act", f'{agent.name} found {target.name} remembers "{memory.claim}" differently')
        else:
            agent.remember(
                Memory(
                    claim=memory.claim,
                    subject=agent.name,
                    about=memory.about,
                    kind="told",
                    signature={emotion: value * 0.35 for emotion, value in memory.signature.items()},
                    salience=0.5,
                    stances={"affirm": 0.6, "doubt": 0.4},
                    created_at=self.tick_count,
                    source=target.name,
                )
            )
            bond.add("doubt", -0.05)
            bond.add("trust", 0.03)
            self.record("act", f'{agent.name} checked with {target.name} and learned "{memory.claim}"')
        agent.refresh_trust_ceilings()

    def _act_boast(self, agent: Agent, target: Agent) -> None:
        back = target.bond(agent.name, at=self.tick_count)
        if back.get("love") > 0.50:
            back.add("gratitude", 0.05)
        else:
            back.add("envy", 0.12)
            back.add("doubt", 0.05)
        agent.self_bond.add("pride", 0.03)
        agent.self_bond.add("joy", 0.03)
        self.record("act", f"{agent.name} held forth in front of {target.name}")

    def _act_seek(self, agent: Agent, _target: Agent) -> None:
        strangers = [name for name in self.agents if name != agent.name and name not in agent.bonds]
        if not strangers:
            return

        def warmth(name: str) -> tuple[float, str]:
            score = 0.0
            for link in agent.others():
                friend = self.agents[link.target]
                theirs = friend.bonds.get(name)
                if theirs is not None:
                    score += link.get("trust") * (theirs.get("love") + theirs.get("trust"))
            return (-score, name)

        chosen = self.agents[sorted(strangers, key=warmth)[0]]
        bond = agent.bond(chosen.name, at=self.tick_count)
        bond.add("curiosity", 0.20)
        bond.add("love", 0.08)
        bond.add("hope", 0.10)
        chosen.bond(agent.name, at=self.tick_count).add("curiosity", 0.10)
        agent.self_bond.add("loneliness", -0.12)
        self.record("act", f"{agent.name} sought out {chosen.name}")

    def _act_contribute(self, agent: Agent, _target: Agent) -> None:
        for group_name in agent.groups:
            group = self.groups[group_name]
            if group.goal is None or group.achieved_at is not None:
                continue
            me = agent.self_bond
            amount = clamp(
                0.5 * self._group_feeling(agent, "trust")
                + 0.3 * me.get("hope")
                + 0.2 * me.get("pride")
                - 0.3 * me.get("fear")
            )
            if amount <= 0.01:
                return
            group.progress += amount
            for member in group.members:
                if member == agent.name:
                    continue
                other = self.agents[member]
                other.bond(agent.name, at=self.tick_count).add("gratitude", 0.10)
                other.bond(agent.name, at=self.tick_count).add("trust", 0.05)
            me.add("pride", 0.08)
            me.add("joy", 0.05)
            self.record(
                "act",
                f"{agent.name} worked toward {group_name} ({group.progress:.2f}/{group.required:.2f})",
            )
            return

    def _act_brood(self, agent: Agent, _target: Agent) -> None:
        if not agent.memories:
            return
        memory = max(agent.memories, key=lambda m: (m.salience * m.weight, m.claim))
        memory.salience = clamp(memory.salience + 0.06)
        immediate: dict[tuple[str, str, str], float] = {}
        self._pull(immediate, agent, memory, 0.35)
        self._apply_deltas(immediate)
        agent.self_bond.add("sadness", 0.06)
        self.record("act", f'{agent.name} turned "{memory.claim}" over again')

    # ------------------------------------------------------------------
    def _collectives(self) -> None:
        for group in self.groups.values():
            if group.goal is None or group.achieved_at is not None or not group.members:
                continue
            if group.progress >= group.required:
                group.achieved_at = self.tick_count
                for name in group.members:
                    agent = self.agents[name]
                    agent.self_bond.add("joy", 0.35)
                    agent.self_bond.add("pride", 0.25)
                    for other in group.members:
                        if other != name:
                            agent.bond(other, at=self.tick_count).add("gratitude", 0.20)
                            agent.bond(other, at=self.tick_count).add("trust", 0.10)
                    agent.remember(
                        Memory(
                            claim=f"{group.name} achieved {group.goal}",
                            subject=name,
                            about=None,
                            kind="experienced",
                            signature={"joy": 0.30, "pride": 0.25},
                            created_at=self.tick_count,
                        )
                    )
                self.record("goal", f"{group.name} achieved '{group.goal}' at tick {self.tick_count}")

    # ------------------------------------------------------------------
    def memory_tension(self, agent: Agent) -> float:
        total = 0.0
        for memory in agent.memories:
            if memory.suppressed:
                continue  # denial is exactly the refusal to pay this
            against = memory.stances.get("deny", 0.0) + memory.stances.get("doubt", 0.0)
            support = memory.stances.get("affirm", 0.0) + memory.stances.get("hope", 0.0)
            total += min(against, support) * memory.salience * max(memory.weight, 0.2)
        return total


def run_source(source: str, filename: str = "<source>", sink=None, trace: bool = False) -> World:
    """Parse and execute Catharsis source, returning the resulting world."""
    from .parser import parse

    world = World(sink=sink, trace=trace)
    world.run(parse(source, filename))
    return world
