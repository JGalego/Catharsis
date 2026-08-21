# Catharsis

**Programs with feelings. 💭❤️‍🔥🧠**

[![CI](https://github.com/JGalego/Catharsis/actions/workflows/ci.yml/badge.svg)](https://github.com/JGalego/Catharsis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-lightgrey.svg)](pyproject.toml)

Catharsis is an esoteric programming language in which **emotion is the computational
substrate**. Not the syntax — the substrate.

There are no variables. All state lives as *charge* on the edges of a directed graph of
entities: `alice -> bob` carries how Alice feels about Bob, and the self-loop
`alice -> alice` carries how Alice feels about herself. There is no control flow either.
The only thing resembling a statement is `tick`, which advances a simulation in which
emotions feed and drain each other, memories push their charge back into the present,
feeling travels along relationships as hearsay, and every agent takes whichever action
the field is currently pushing it hardest toward.

```
alice = agent
bob = agent

love alice bob
betray alice bob
grief bob
doubt bob alice
apology alice bob
tick 8
forgive bob alice
```

Nothing above sets a flag. `betray` deposits anger, resentment, doubt and grief on one
edge and guilt on the other, and lays down a memory on both sides. Everything that
follows is the field working — here is what those ten lines actually do:

```console
$ catharsis run intro.feel --trace --quiet
[tick 1] alice apologised to bob (landed 14%)
[tick 1] bob confronted alice
[tick 3] bob turned "alice betrayed bob" over again
[tick 4] bob withdrew from alice
[tick 5] alice apologised to bob (landed 17%)
[tick 7] bob turned "alice betrayed bob" over again
[tick 8] bob withdrew from alice
[tick 8] bob forgave alice: 2 memories disarmed, none deleted (trust ceiling 0.75)
```

The program never told Alice to apologise; her guilt outweighed her pride, so she did,
twice, and it landed at 14% because that is how much of an overture gets through the
resentment Bob is holding. Bob was never told to confront her, brood or withdraw. And
forgiving disarmed his memories rather than removing them — the ceiling on how far he can
trust her again is part of the output.

### The same program, in glyphs

Every emotion and the commonest events have a glyph, and a glyph is a *second spelling*,
not a second language — it resolves through the same alias table as `lonely` →
`loneliness`, so no line of the runtime knows the difference. `tests/test_emoji.py`
asserts that: the two spellings of one program produce byte-identical worlds.

```
alice = 👤          ❤️  love     🤝 trust    🕊️  hope     😄 joy       🦁 pride
bob   = 👤          🔍 curious  🙏 grateful 😠 anger    😨 fear      🤔 doubt
                    😢 sadness  🖤 grief    🙈 shame    😞 guilt     😒 envy
❤️ alice bob         💚 jealousy 🧍 lonely   😲 surprise 🛤️  regret    🧊 resentment
💔 alice bob         💔 betray   🙇 apology  🤲 forgive  👁️  witness   🎁 gift
🖤 bob               🧠 remember 💭 recall   🙅 deny     🧘 accept    🔀 choice
🤔 bob alice         ⏱️  tick     👤 agent
⏱️ 8
🤲 bob alice
```

They earn their place a second time on the way out. `--emoji` renders the field in the
same alphabet, which makes a relationship legible at a glance in a way six emotion words
in a row are not:

```console
$ catharsis run examples/emoji.feel --emoji --quiet
carol
  self: 🧍 0.24  😢 0.09
  bonds:
    -> bob: ❤️ 0.78  🤝 0.43  🕊️ 0.33  💚 0.12
    -> alice: 💚 0.26  😠 0.11  😨 0.07
```

## What makes it different from a conventional language

|  | A conventional language | Catharsis |
| --- | --- | --- |
| State | variables you assign | charge on relationships, which decays, couples and spreads |
| Truth | `true` / `false` | four independent stances per memory, and a confidence read off their balance |
| Contradiction | a bug | a quantity: `tension`, which slows the agent holding it |
| The past | data you may choose to read | an active participant: memories push charge back every tick |
| Deletion | `del x` | `grief` — the thing is gone and its afterimage keeps acting |
| Undo | rewind, or restore a snapshot | `regret` — the road not taken stays live and is *valued* beside the one you're on |
| Behaviour | `if` / `else` | every action scored against the field; the strongest one wins |

Three properties fall out of that rather than being implemented:

- **`forgiveness != forgetting`.** `forgive` disarms a memory: it stops pushing anger and
  resentment. It does not delete it, and the memory goes on holding a *ceiling* on how far
  trust can recover.
- **`trust != absence_of_history`.** Trust is clamped by what happened. Forgiving raises
  the ceiling; nothing removes it.
- **Reputation with no reputation table.** Nothing anywhere scores an agent. Witnessing
  puts you in the victim's shoes at 55% strength, confiding hands somebody an actual
  memory believed in proportion to how much they trust you, and contagion leaks feeling
  along every edge — with warnings travelling further than praise. Reputation is what
  those three do together.

Execution is fully deterministic, with no seeded PRNG anywhere: symmetry is broken by a
content hash, so the same program always produces the same world.

## Getting started

### Prerequisites

Python 3.10 or newer. There are no dependencies — the interpreter is stdlib only.

### Installation

```bash
git clone https://github.com/JGalego/Catharsis.git
cd Catharsis
pip install -e .          # optional: puts a `catharsis` command on your PATH
```

Without installing, `python -m catharsis` works identically from the repository root.

### Running the interpreter

```bash
catharsis run examples/forgiveness.feel          # run a program and print the final state
catharsis run examples/society.feel --trace      # ...and narrate every event as it happens
catharsis run examples/contradiction.feel --emoji  # ...with one glyph per emotion
catharsis run examples/reputation.feel --json
catharsis check examples/negotiation.feel        # parse without running
catharsis words                                  # everything the language can say
```

Useful flags: `--ticks N` runs extra ticks after the program ends, `--quiet` suppresses the
closing report, `--json` emits the whole world as machine-readable state, `--emoji` renders
the field in glyphs.

### Running an example

```console
$ catharsis run examples/forgiveness.feel --quiet
bob
  self: grief 0.67  sadness 0.55  love 0.25  trust 0.13
  bonds:
    -> alice: love 0.82  trust 0.75  hope 0.72  grief 0.32  gratitude 0.28  surprise 0.26   [trust ceiling 0.75]   [holding: trust/doubt 0.17]
  memories (3):
    "alice betrayed bob"
      confidence: certain (1.00)   emotional_weight: high (1.00)   contradictions: 0
      experienced | forgiven at tick 10   salience 1.00
      still pushing: grief 0.32  doubt 0.22
```

Bob has forgiven Alice. His trust has recovered to exactly the ceiling his memory allows
and no further, the memory is intact and still heavy, and it is still pushing grief — but
no longer anger or resentment. That is the difference between forgiving and forgetting,
and it is a fact about the runtime, not a string.

### Running the tests

```bash
python -m unittest discover -s tests -v     # 86 tests, no dependencies
ruff check catharsis tests                  # optional: lint
ruff format --check catharsis tests         # optional: formatting
```

## Examples

Every example is a runnable program with its reasoning in the file itself, and
[`examples/README.md`](examples/README.md) collects the resulting state for each one.

| Example | What it shows |
| --- | --- |
| [negotiation.feel](examples/negotiation.feel) | Two agents bargain to a settled price with no negotiation algorithm anywhere. How far each side moves *is* how it feels: `trust + hope + guilt + love + fear` against `pride + anger + resentment + doubt`. Alice's pride wins her the price; Bob's fear loses it — and he ends up holding gratitude and resentment at the same time. |
| [reputation.feel](examples/reputation.feel) | Alice betrays Bob, Charlie sees it, and Diana — who never met Alice and saw nothing — ends up doubting her, via a memory tagged `told \| from charlie` with its own confidence. The damage is strictly graded: victim > witness > hearsay. |
| [forgiveness.feel](examples/forgiveness.feel) | Can Bob forgive Alice without forgetting what she did? Trust recovers to the ceiling the memory imposes and stops there, grief stays, and the memory keeps ruminating with its hostile half disarmed. |
| [unreliable_memory.feel](examples/unreliable_memory.feel) | `recall` returns a confidence, an emotional weight and a contradiction count, never a boolean. `denial` suppresses the claim and the feeling goes on ruminating at full strength anyway. `acceptance` collapses it and charges grief. |
| [society.feel](examples/society.feel) | Four agents, some bread, some temperament, no social algorithm. What emerges over 30 ticks: theft, gossip about the theft, confrontation, withdrawal, charity, and an outsider who ends up allied with the person who fed him — while a fourth agent, equally hungry, is left isolated because nobody is bonded to her. |
| [coordination.feel](examples/coordination.feel) | Three agents and a shared goal with nobody in charge. Alice has enough hope to move first; the gratitude her work produces raises everyone else's trust until they join in, and the goal is met at tick 12. |
| [coordination_broken.feel](examples/coordination_broken.feel) | The same program with the trust graph broken. Nobody can move first, so the gratitude that would have unlocked the others is never generated, and the group never gets off zero. |
| [regret.feel](examples/regret.feel) | `regret` forks rather than rewinds. The untaken road is kept as a live valuation that drifts upward the longer it is carried, so regret grows when the life you are in goes badly and shrinks when it goes well. |
| [emoji.feel](examples/emoji.feel) | A love triangle written entirely in glyphs, with the state rendered back the same way. Carol is told nothing about what to do with her jealousy; she wedges herself into the couple anyway. |
| [contradiction.feel](examples/contradiction.feel) | Love and anger, trust and doubt, hope and fear, all held at once and never collapsed. Action pressure is divided by `1 + tension`, so ambivalence looks like paralysis without anything in the runtime knowing about ambivalence. |

## How it works

```
catharsis/
  field.py       the physics: decay, coupling, spill, antagonism, transmissibility
  vocabulary.py  every word in the language, as a table of charge deposits
  actions.py     every action an agent can take, as affinity and inhibition vectors
  entity.py      bonds, memories, timelines, alternate histories
  world.py       the tick, and the runtime that hangs off those tables
  lexer.py parser.py ast.py errors.py report.py cli.py
```

The design rule is that **emotions do not get `if` statements**. `field.py` and
`actions.py` are data. Adding an emotion means adding a row to a table, and it changes
behaviour everywhere at once because everything — negotiation, gossip, rumination, action
selection — reads the same twenty axes through the same machinery.

One tick, in full: decay → temperament → coupling → spill onto self-regard → rumination →
unmet needs → contagion → regret drift → open bargains → every agent scores every action
and takes the strongest → shared goals check themselves.

`catharsis words` prints the whole vocabulary: twenty emotions, which take either an entity
(`fear diana charlie`), nobody but themselves (`pride charlie`), or a claim
(`doubt alice "the door was open"`), plus the events — `betray`, `apology`, `forgive`,
`witness`, `gift`, `propose`, `reject`, `agree`, `remember`, `recall`, `denial`,
`acceptance`, `choice`, `regret`, `goal`, `have`, `need`, `trait`, `group`, `join`.

## Status

Version 0.1.0, and deliberately small. The field constants in `field.py` are tuned by hand
and are meant to be argued with — the tests assert properties and inequalities rather than
particular numbers, precisely so the physics can be retuned without lying about what the
language does.

## License

[MIT](LICENSE).
