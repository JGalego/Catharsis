"""What agents do, and why they do it.

There is no decision tree in Catharsis.  Every action an agent can take is a row
in this table with two vectors: what pulls it and what holds it back.  Each tick
an agent scores every (action, target) pair as

    pressure = affinity . charge  -  inhibition . charge

reads the charge off the relevant edge of the field, divides by ``1 + tension``
(ambivalence makes you slow), subtracts recent repetition, and takes the
strongest option above a threshold.

The consequence is that adding an emotion changes behaviour everywhere at once,
and no emotion has an ``if`` statement of its own.

Affinity keys are read as:

``anger``
    the actor's charge toward the target on this edge
``self:shame``
    the actor's charge toward itself
``their:fear``
    the *target's* charge toward the actor -- how the world answers back
``deficit`` / ``own_need`` / ``their_need``
    unmet need: the actor's overall, the actor's in the specific resource being
    handed over, and the target's -- the last discounted by how dangerous the
    thing being asked for is
``exposure``
    what handing that resource over would cost if the asker is not what they
    seem, weighed against how far they are actually trusted
``group_trust`` / ``group_doubt``
    mean feeling toward the actor's fellow members
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field

#: Pressure an action must reach before an agent will take it.
THRESHOLD = 0.30


@dataclass(frozen=True)
class Action:
    name: str
    scope: str  # "bond" (needs a target) or "self"
    doc: str
    affinity: dict[str, float] = dc_field(default_factory=dict)
    inhibit: dict[str, float] = dc_field(default_factory=dict)
    requires: str | None = None  # optional named precondition
    #: How strongly doing this again straight away is discouraged.  Most social
    #: moves lose their force when repeated; working at a shared task does not.
    habituation: float = 1.0


ACTIONS: tuple[Action, ...] = (
    Action(
        "reach_out",
        "bond",
        "close the distance to someone you are drawn to",
        affinity={"love": 0.80, "hope": 0.50, "self:loneliness": 0.60, "gratitude": 0.40, "curiosity": 0.20},
        inhibit={"fear": 0.70, "doubt": 0.50, "self:shame": 0.60, "resentment": 0.80, "anger": 0.50},
    ),
    Action(
        "confide",
        "bond",
        "hand somebody a memory of yours; this is how facts, not just feelings, travel",
        affinity={"trust": 0.90, "love": 0.40, "self:loneliness": 0.40},
        inhibit={"doubt": 0.80, "fear": 0.50, "self:shame": 0.50, "self:pride": 0.20},
        requires="can_confide",
    ),
    Action(
        "confront",
        "bond",
        "put the grievance in front of the person who caused it",
        affinity={"anger": 1.00, "resentment": 0.50, "self:pride": 0.40},
        inhibit={"fear": 0.90, "love": 0.60, "guilt": 0.40, "their:anger": 0.20},
    ),
    Action(
        "withdraw",
        "bond",
        "let a relationship go cold",
        affinity={"fear": 0.80, "self:shame": 0.60, "self:sadness": 0.50, "resentment": 0.40, "doubt": 0.30},
        inhibit={"love": 0.50, "hope": 0.50},
    ),
    Action(
        "compete",
        "bond",
        "take what somebody else has",
        affinity={"jealousy": 1.00, "envy": 0.80, "anger": 0.30, "self:pride": 0.30, "deficit": 0.50},
        inhibit={"fear": 0.60, "guilt": 0.50, "love": 0.50, "self:shame": 0.30},
        requires="can_take",
    ),
    Action(
        "give",
        "bond",
        "hand over what somebody else is short of",
        affinity={
            "love": 0.70,
            "trust": 0.40,
            "guilt": 0.90,
            "gratitude": 0.50,
            "their_need": 0.60,
            "self:joy": 0.30,
        },
        inhibit={
            "self:fear": 0.40,
            "resentment": 0.60,
            "envy": 0.30,
            "own_need": 0.70,
            "exposure": 1.60,
        },
        requires="can_give",
    ),
    Action(
        "ask",
        "bond",
        "say out loud that you are short; being asked is what creates the obligation",
        affinity={"deficit": 1.00, "trust": 0.50, "self:hope": 0.40, "love": 0.30},
        inhibit={"self:pride": 0.90, "self:shame": 0.60, "fear": 0.50, "resentment": 0.40},
        requires="can_ask",
    ),
    Action(
        "repair",
        "bond",
        "apologise, unprompted, because the guilt is heavier than the pride",
        affinity={"guilt": 1.20, "love": 0.30, "hope": 0.20, "grief": 0.20},
        inhibit={"self:pride": 0.80, "anger": 0.50, "resentment": 0.30},
        requires="has_guilt",
    ),
    Action(
        "imitate",
        "bond",
        "become a little more like the person you envy",
        affinity={"envy": 0.90, "curiosity": 0.40, "love": 0.20},
        inhibit={"self:pride": 0.60, "resentment": 0.40},
        requires="can_imitate",
    ),
    Action(
        "probe",
        "bond",
        "check what you have been told; trust is what makes you skip this",
        affinity={"curiosity": 0.90, "doubt": 0.70},
        inhibit={"fear": 0.60, "self:shame": 0.30, "trust": 0.50},
    ),
    Action(
        "boast",
        "bond",
        "display, which costs the audience something",
        affinity={"self:pride": 0.90, "self:joy": 0.30},
        inhibit={"self:shame": 0.50, "fear": 0.40, "guilt": 0.30},
    ),
    Action(
        "seek",
        "self",
        "look for anyone at all",
        affinity={"self:loneliness": 1.00, "self:hope": 0.40, "self:curiosity": 0.30},
        inhibit={"self:fear": 0.60, "self:shame": 0.70, "self:sadness": 0.30},
        requires="can_seek",
    ),
    Action(
        "contribute",
        "self",
        "push a shared goal forward, which nobody is ordering anybody to do",
        affinity={"group_trust": 1.00, "self:hope": 0.50, "self:pride": 0.40, "self:guilt": 0.20},
        inhibit={"group_doubt": 0.80, "self:fear": 0.80, "self:sadness": 0.40, "self:shame": 0.30},
        requires="has_group_goal",
        habituation=0.20,
    ),
    Action(
        "brood",
        "self",
        "turn a memory over again, which makes it heavier",
        affinity={"self:grief": 0.60, "self:regret": 0.70, "self:sadness": 0.50, "self:shame": 0.30},
        inhibit={"self:joy": 0.40, "self:hope": 0.20},
        requires="has_memory",
        habituation=0.50,
    ),
)

ACTION_BY_NAME = {action.name: action for action in ACTIONS}
