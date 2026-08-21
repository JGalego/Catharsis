"""Rendering world state for humans and for tests."""

from __future__ import annotations

from .entity import Agent, Group, Memory
from .field import contradictions, dominant
from .vocabulary import GLYPHS


def _name(world, emotion: str) -> str:
    """An emotion's word, or its glyph when the world is rendering in emoji."""
    if getattr(world, "emoji", False):
        return GLYPHS.get(emotion, emotion)
    return emotion


def _charge_line(world, charge: dict[str, float], limit: int = 6) -> str:
    parts = [f"{_name(world, name)} {value:.2f}" for name, value in dominant(charge, limit=limit)]
    return "  ".join(parts) if parts else "-"


def _tension_note(world, charge: dict[str, float]) -> str:
    pairs = contradictions(charge)
    if not pairs:
        return ""
    rendered = ", ".join(
        f"{_name(world, left)}/{_name(world, right)} {overlap:.2f}" for left, right, overlap in pairs[:3]
    )
    return f"   [holding: {rendered}]"


def render_memory(world, agent: Agent, memory: Memory, indent: str = "    ") -> list[str]:
    flags = [memory.kind]
    if memory.source:
        flags.append(f"from {memory.source}")
    if memory.reconciled:
        flags.append(f"forgiven at tick {memory.reconciled_at}")
    if memory.suppressed:
        flags.append("denied but still ruminating")
    lines = [f'{indent}"{memory.claim}"']
    detail = (
        f"{indent}  confidence: {memory.confidence_label} ({memory.confidence:.2f})"
        f"   emotional_weight: {memory.emotional_weight_label} ({memory.weight * memory.salience:.2f})"
        f"   contradictions: {memory.contradiction_count}"
    )
    lines.append(detail)
    lines.append(f"{indent}  {' | '.join(flags)}   salience {memory.salience:.2f}")
    # What it is *currently* pushing, not what it was made of: a forgiven memory
    # keeps its signature and stops pushing the hostile part of it.
    live = memory.rumination()
    if live:
        lines.append(f"{indent}  still pushing: {_charge_line(world, live, limit=4)}")
    elif memory.signature:
        lines.append(
            f"{indent}  pushing nothing (signature: {_charge_line(world, memory.signature, limit=4)})"
        )
    return lines


def render_memories(world, agent: Agent) -> list[str]:
    lines = [f"{agent.name} remembers:"]
    if not agent.memories:
        lines.append("    nothing")
    for memory in agent.memories:
        lines.extend(render_memory(world, agent, memory))
    for branch in agent.branches:
        state = "closed" if branch.closed else "open"
        lines.append(
            f'    alternate history ({state}): took "{branch.taken}", kept "{branch.untaken}" '
            f"since tick {branch.forked_at}"
        )
        actual = agent.wellbeing()
        lines.append(
            f"      valuation: actual {actual:.2f} vs alternate {branch.valuation:.2f}"
            f"   regret {branch.pressure(actual):.2f} (gap {branch.valuation - actual:+.2f})"
            f"   visits {branch.visits}"
        )
    return lines


def render_agent(world, agent: Agent) -> list[str]:
    me = agent.self_bond
    lines = [f"{agent.name}"]
    lines.append(f"  self: {_charge_line(world, me.charge)}{_tension_note(world, me.charge)}")
    others = agent.others()
    if others:
        lines.append("  bonds:")
        for bond in sorted(others, key=lambda b: (-b.intensity, b.target)):
            ceiling = "" if bond.trust_ceiling >= 0.999 else f"   [trust ceiling {bond.trust_ceiling:.2f}]"
            lines.append(
                f"    -> {bond.target}: {_charge_line(world, bond.charge)}{ceiling}{_tension_note(world, bond.charge)}"
            )
    if agent.resources or agent.needs:
        parts = []
        for name in sorted(set(agent.resources) | set(agent.needs)):
            have = agent.resources.get(name, 0.0)
            need = agent.needs.get(name)
            parts.append(f"{name} {have:g}" + (f"/{need:g} needed" if need else ""))
        lines.append("  resources: " + ", ".join(parts))
    if agent.goals or agent.commitments:
        parts = [
            f"{dim}: wants {value:g}, at {agent.stances.get(dim, value):g}"
            for dim, value in sorted(agent.goals.items())
        ]
        parts.extend(agent.commitments)
        lines.append("  goals: " + "; ".join(parts))
    if agent.traits:
        lines.append("  temperament: " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(agent.traits.items())))
    if agent.groups:
        lines.append("  belongs to: " + ", ".join(agent.groups))
    if agent.memories:
        lines.append(f"  memories ({len(agent.memories)}):")
        for memory in agent.memories:
            lines.extend(render_memory(world, agent, memory, indent="    "))
    if agent.timeline:
        chosen = "; ".join(f'"{choice.option}" at tick {choice.at}' for choice in agent.timeline)
        lines.append(f"  chose: {chosen}")
    for branch in agent.branches:
        actual = agent.wellbeing()
        state = "closed" if branch.closed else "open"
        lines.append(
            f'  alternate history ({state}): "{branch.untaken}" instead of "{branch.taken}"'
            f"   regret {branch.pressure(actual):.2f}   idealisation {branch.idealization:.2f}"
        )
    total_tension = agent.tension + world.memory_tension(agent)
    lines.append(f"  unresolved: {total_tension:.2f}")
    return lines


def render_group(world, group: Group) -> list[str]:
    lines = [f"group {group.name}"]
    lines.append("  members: " + (", ".join(group.members) or "nobody"))
    if group.goal:
        state = f"achieved at tick {group.achieved_at}" if group.achieved_at else "open"
        lines.append(f"  goal: {group.goal} ({state})")
        lines.append(f"  progress: {group.progress:.2f} / {group.required:.2f}")
    return lines


def render_world(world) -> list[str]:
    lines = [f"=== world at tick {world.tick_count} ==="]
    for agent in world.agents.values():
        lines.extend(render_agent(world, agent))
    for group in world.groups.values():
        lines.extend(render_group(world, group))
    open_or_closed = [n for n in world.negotiations]
    if open_or_closed:
        lines.append("negotiations:")
        for negotiation in open_or_closed:
            if negotiation.status == "agreed":
                detail = f"agreed at {negotiation.agreement:.1f} (tick {negotiation.closed_at})"
            elif negotiation.status == "impasse":
                detail = f"impasse (tick {negotiation.closed_at})"
            else:
                left = world.agents[negotiation.left].stances[negotiation.dimension]
                right = world.agents[negotiation.right].stances[negotiation.dimension]
                detail = f"open: {negotiation.left} at {left:.1f}, {negotiation.right} at {right:.1f}"
            lines.append(
                f"  {negotiation.left} / {negotiation.right} over {negotiation.dimension}: {detail}"
                f"   [{negotiation.rounds} rounds]"
            )
    return lines


def to_dict(world) -> dict:
    """A machine-readable snapshot, used by ``catharsis run --json`` and tests."""
    return {
        "tick": world.tick_count,
        "agents": {
            name: {
                "self": dict(sorted(agent.self_bond.charge.items())),
                "bonds": {
                    bond.target: {
                        "charge": dict(sorted(bond.charge.items())),
                        "tension": round(bond.tension, 6),
                        "trust_ceiling": round(bond.trust_ceiling, 6),
                    }
                    for bond in sorted(agent.others(), key=lambda b: b.target)
                },
                "memories": [
                    {
                        "claim": memory.claim,
                        "kind": memory.kind,
                        "about": memory.about,
                        "confidence": round(memory.confidence, 6),
                        "confidence_label": memory.confidence_label,
                        "emotional_weight": memory.emotional_weight_label,
                        "contradictions": memory.contradiction_count,
                        "salience": round(memory.salience, 6),
                        "reconciled": memory.reconciled,
                        "suppressed": memory.suppressed,
                        "source": memory.source,
                    }
                    for memory in agent.memories
                ],
                "resources": dict(sorted(agent.resources.items())),
                "needs": dict(sorted(agent.needs.items())),
                "goals": dict(sorted(agent.goals.items())),
                "positions": dict(sorted(agent.stances.items())),
                "groups": list(agent.groups),
                "wellbeing": round(agent.wellbeing(), 6),
                "unresolved": round(agent.tension + world.memory_tension(agent), 6),
                "alternate_histories": [
                    {
                        "taken": branch.taken,
                        "untaken": branch.untaken,
                        "open": not branch.closed,
                        "regret": round(branch.pressure(agent.wellbeing()), 6),
                        "visits": branch.visits,
                    }
                    for branch in agent.branches
                ],
            }
            for name, agent in world.agents.items()
        },
        "groups": {
            name: {
                "members": list(group.members),
                "goal": group.goal,
                "progress": round(group.progress, 6),
                "required": round(group.required, 6),
                "achieved_at": group.achieved_at,
            }
            for name, group in world.groups.items()
        },
        "negotiations": [
            {
                "parties": list(negotiation.parties),
                "dimension": negotiation.dimension,
                "status": negotiation.status,
                "agreement": None if negotiation.agreement is None else round(negotiation.agreement, 6),
                "rounds": negotiation.rounds,
            }
            for negotiation in world.negotiations
        ],
    }
