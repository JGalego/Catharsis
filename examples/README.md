# Examples

Every program here is runnable, and every block of output below was produced by running it.
Each `.feel` file carries its own reasoning in a header comment; this page collects the
results.

```bash
catharsis run examples/<name>.feel            # final state
catharsis run examples/<name>.feel --trace    # narrate every event as it happens
catharsis run examples/<name>.feel --json     # machine-readable state
catharsis run examples/<name>.feel --emoji    # one glyph per emotion
catharsis visualize examples/<name>.feel      # replay it in a browser, frame by frame
```

Every example below is worth watching rather than reading: `visualize` gives you the whole
run with transport controls, so the propagation in §2 and the coordination cascade in §6
are visible as they happen instead of only in the final numbers.

---

## 1. Negotiation — [`negotiation.feel`](negotiation.feel)

Alice wants 90, Bob wants 50, and there is no negotiation algorithm in the runtime. Each
side moves by whatever it can currently bear to give up, which is read straight off the
field: `trust + hope + guilt + love + fear` against `pride + anger + resentment + doubt`.
Alice is proud; Bob is afraid. Fear yields and pride does not.

```
negotiations:
  alice / bob over price: agreed at 80.9 (tick 16)   [16 rounds]

alice
  self: pride 0.65  loneliness 0.16  anger 0.10  sadness 0.10  joy 0.07  resentment 0.06
    -> bob: trust 0.31  gratitude 0.20  doubt 0.19  resentment 0.18  joy 0.14  love 0.11
       [holding: trust/doubt 0.19, gratitude/resentment 0.16]
  goals: price: wants 90, at 80.8628

bob
  self: sadness 0.41  loneliness 0.25  pride 0.07  fear 0.07
    -> alice: resentment 0.37  doubt 0.31  envy 0.30  gratitude 0.20  joy 0.16  fear 0.13
       [holding: gratitude/resentment 0.18]
  goals: price: wants 50, at 80.8628
```

**Why this needs an emotional model.** The price is a fact about the relationship, not about
arithmetic — change one line and the number moves:

| Change | Result |
| --- | --- |
| as written (Bob fearful, Alice proud) | agreed at **80.9**, tick 16 |
| `pride alice 0.7` → `hope alice bob 0.7` | agreed at **75.6**, tick 10 |
| evenly matched, mutual trust, nothing else | agreed at **68.3**, tick 8 |
| both proud, both angry, both resentful | **impasse** — talks break off 21.1 apart |

And the outcome is not one number. Bob got a deal and it cost him the relationship: he ends
at resentment 0.37 while simultaneously holding gratitude 0.20 for the same person. There is
no representation of "grateful and resentful at once" in a language with a numeric
satisfaction score.

---

## 2. Reputation — [`reputation.feel`](reputation.feel)

Alice betrays Bob. Charlie sees it. Diana never met Alice and saw nothing, but she trusts
Charlie. Nothing in the runtime keeps a score for Alice.

```
charlie                                        (witness)
    -> alice: doubt 0.29  resentment 0.26  grief 0.18  anger 0.09   [trust ceiling 0.76]
  memories:
    "alice betrayed bob"
      confidence: certain (1.00)   emotional_weight: medium (0.53)   contradictions: 0
      witnessed   salience 0.94

diana                                          (never met her)
    -> alice: doubt 0.10  resentment 0.07   [trust ceiling 0.93]
  memories:
    "alice betrayed bob"
      confidence: likely (0.84)   emotional_weight: low (0.18)   contradictions: 1
      told | from charlie   salience 0.64
```

**Why this needs an emotional model.** Diana holds a *memory*, with a source, a confidence
and a contradiction — not a number that went down. The damage is strictly graded by how it
reached each person (victim > witness > hearsay), and it arrived through three general
mechanisms with no special case for reputation between them: witnessing puts you in the
victim's shoes at 55% strength, confiding hands over an actual memory believed in proportion
to trust in the teller, and contagion leaks feeling along every edge with a negativity bias.
Run it with `--trace` to watch Charlie tell Diana at tick 1.

---

## 3. Forgiveness — [`forgiveness.feel`](forgiveness.feel)

Can Bob forgive Alice without forgetting what she did?

```
bob
  self: grief 0.67  sadness 0.55  love 0.25  trust 0.13
  bonds:
    -> alice: love 0.82  trust 0.75  hope 0.72  grief 0.32  gratitude 0.28
       [trust ceiling 0.75]   [holding: trust/doubt 0.17]
  memories (3):
    "alice betrayed bob"
      confidence: certain (1.00)   emotional_weight: high (1.00)   contradictions: 0
      experienced | forgiven at tick 10   salience 1.00
      still pushing: grief 0.32  doubt 0.22
```

**Why this needs an emotional model.** `forgiveness != forgetting`: the memory is intact, at
full salience and full confidence, flagged forgiven, and still pushing grief and doubt into
the present every tick — with anger and resentment disarmed. `trust != absence_of_history`:
Bob's trust is 0.75, which is exactly the ceiling his memory allows and not a point more.
Forgiving raised that ceiling from 0.55; nothing available in the language removes it.

Deleting a boolean cannot express any of this, and neither can subtracting from a trust
score, because the thing doing the work is a record that is still acting.

---

## 4. Unreliable memory — [`unreliable_memory.feel`](unreliable_memory.feel)

`recall` is not a lookup and does not return a boolean.

```
alice recalls, at tick 3:                      (after denial)
    "the door was open"
      confidence: disputed (0.74)   emotional_weight: medium (0.40)   contradictions: 2
      experienced | denied but still ruminating   salience 1.00
      still pushing: grief 0.35  fear 0.10
alice
  self: fear 0.47  grief 0.31
  unresolved: 0.00

alice recalls, at tick 6:                      (after doubt and hope)
    "the door was open"
      confidence: disputed (0.66)   emotional_weight: high (0.90)   contradictions: 4
      experienced | denied but still ruminating   salience 1.00
      still pushing: grief 0.35  doubt 0.30  hope 0.15  fear 0.10

alice recalls, at tick 8:                      (after acceptance)
    "the door was open"
      confidence: certain (1.00)   emotional_weight: high (0.90)   contradictions: 0
  self: grief 0.47  doubt 0.33  fear 0.31  sadness 0.19  hope 0.16
  unresolved: 0.14
```

**Why this needs an emotional model.** Look at `unresolved: 0.00` on the denied memory. That
is the entire semantics of denial: the claim is kept, the contradiction is kept, and the cost
of holding it is refused. Meanwhile her fear sits at 0.47 — the suppressed memory ruminates
at full strength regardless, so the mind drops the fact and the body keeps the feeling.
`acceptance` then collapses the stances into one and charges grief for the half she gave up.
Three distinct, well-defined states that a boolean has no room for.

---

## 5. Emergent society — [`society.feel`](society.feel)

Four agents, some bread, four temperaments, no social algorithm. Run with `--trace`:

```
[tick 1]  charlie took bread from bob
[tick 1]  diana withdrew from charlie
[tick 2]  bob told alice "charlie took bread from bob"
[tick 2]  charlie sought out alice
[tick 3]  bob confronted charlie
[tick 4]  alice gave charlie bread
[tick 6]  charlie told alice "bob confronted charlie"
[tick 7]  charlie withdrew from bob
[tick 11] diana took bread from charlie
[tick 12] alice gave charlie bread
[tick 14] charlie told alice "diana took bread from charlie"
[tick 15] alice told bob "diana took bread from charlie"
[tick 16] charlie withdrew from diana
```

and at tick 30:

```
charlie
  self: sadness 0.43  loneliness 0.39  pride 0.07
    -> alice: love 0.63  trust 0.61  hope 0.33  gratitude 0.25  envy 0.13  jealousy 0.10
    -> diana: resentment 0.25  doubt 0.14  anger 0.07   [trust ceiling 0.85]
    -> bob:   resentment 0.16  anger 0.07  jealousy 0.05   [trust ceiling 0.96]
  resources: bread 2/2 needed
  memories (3):
    "bob confronted charlie"        still pushing: fear 0.07  anger 0.06
    "alice gave charlie bread"      still pushing: gratitude 0.13
    "diana took bread from charlie" still pushing: resentment 0.17  doubt 0.12  anger 0.09

diana
    -> alice: envy 0.29  doubt 0.16  resentment 0.08
    -> charlie: doubt 0.15  resentment 0.08
  unresolved: 0.09
```

**Why this needs an emotional model.** The program specifies an emotional environment and
nothing else. What comes out is a social history: a hungry outsider steals, the theft is
gossiped about, he is confronted, he withdraws — and he is also fed twice by the one person
whose situation lets her, and ends up bonded to her while staying resentful of the two who
took from him or shouted at him. Nobody wrote a rule about alliance formation. The chain
that produced it is a handful of table rows: visible need pulls `give`, giving deposits
gratitude, gratitude feeds trust and drains resentment, trust and love pull `reach_out`.
Note what did *not* happen: Diana, who is equally short of bread, is never given any,
because nobody has a bond to her strong enough to clear the threshold. Isolation is as
emergent as friendship here.

---

## 6. Multi-agent coordination — [`coordination.feel`](coordination.feel) and [`coordination_broken.feel`](coordination_broken.feel)

Three people, one shared goal, nobody in charge. `contribute` is pulled by the mean trust an
agent feels toward its group and held back by the mean doubt.

```
[tick 1]  alice worked toward rescue_team (0.35/4.50)
[tick 5]  alice worked toward rescue_team (1.77/4.50)
[tick 9]  charlie worked toward rescue_team (3.44/4.50)
[tick 11] bob worked toward rescue_team (4.40/4.50)
[tick 12] rescue_team achieved 'rescue' at tick 12
```

The same program with the trust graph broken:

```
group rescue_team
  members: alice, bob, charlie
  goal: rescue (open)
  progress: 0.00 / 4.50
```

**Why this needs an emotional model.** Alice moves first because she is the only one with
enough hope to clear the threshold. Her contributions generate gratitude in the other two,
gratitude feeds trust, and trust is what `contribute` is made of — so Charlie joins at tick 9
and Bob at tick 11 without anybody recruiting them. In the broken version nobody can move
first, so the gratitude that would have unlocked the others is never generated and the group
sits at exactly zero forever. Coordination is not a feature of the runtime; it is a fixed
point of the relationships, and you can lose it by editing the feelings.

---

## 7. Regret and alternate histories — [`regret.feel`](regret.feel)

`regret` forks rather than rewinds.

```
alice remembers:
    "alice chose 'leave'"
    alternate history (open): took "leave", kept "stay" since tick 0
      valuation: actual -0.60 vs alternate 0.81   regret 1.00 (gap +1.41)   visits 1

    ... after a second choice, made while regretting the first:
    "alice chose 'come back'"
      still pushing: regret 0.34  sadness 0.14  loneliness 0.10  doubt 0.06
    alternate history (open): took "come back", kept "keep going" since tick 16
      valuation: actual -0.36 vs alternate -0.39   regret 0.00 (gap -0.03)   visits 1

    ... after acceptance:
    alternate history (closed): "stay" instead of "leave"   regret 0.00   idealisation 0.77
```

**Why this needs an emotional model.** The branch is not a saved snapshot to be restored; it
is a live valuation pinned to how Alice was doing at the fork and drifting upward every tick,
because an unlived option has nothing to disappoint you with. Her regret is the gap between
the two, so it *grows when the life she is in goes badly* and shrinks when it goes well —
which is why the first fork sits at maximum regret and the second, opened while things were
already bad, sits at zero. Both histories stay computationally accessible until `acceptance`
closes them, and closing them costs grief. Note also that the choice she made *while*
regretting carries the regret in its own memory signature.

---

## 8. Contradiction — [`contradiction.feel`](contradiction.feel)

```
alice                                          (at tick 0)
    -> bob: hope 0.90  love 0.80  doubt 0.70  anger 0.60  trust 0.40  fear 0.30
       [holding: love/anger 0.60, trust/doubt 0.40, hope/fear 0.27]
  unresolved: 1.27

alice                                          (at tick 10, nothing tidied away)
    -> bob: love 0.74  hope 0.55  doubt 0.43  trust 0.38  anger 0.19  resentment 0.14
       [holding: trust/doubt 0.38, love/anger 0.19]
  unresolved: 0.93

alice                                          (after acceptance)
  self: grief 0.19  sadness 0.13
    -> bob: love 0.73  hope 0.51  doubt 0.39  trust 0.16   [holding: trust/doubt 0.16]
  unresolved: 0.54
```

**Why this needs an emotional model.** There is no "love minus anger" anywhere. Both charges
sit on the same edge and their overlap is a first-class quantity, `tension`, which is neither
an error nor inert: action pressure is divided by `1 + tension`, so an agent holding a real
contradiction acts less often than one that is merely indifferent. Ambivalence looks like
paralysis from the outside, and that falls out of the arithmetic rather than out of a rule
about ambivalence. `acceptance` is the only thing that collapses a contradiction, and it pays
out whichever side loses as grief.

---

## 9. The emoji shorthand — [`emoji.feel`](emoji.feel)

A love triangle, written entirely in glyphs.

```
👤 alice bob carol

❤️ alice bob 0.9
❤️ bob alice 0.7
🤝 bob alice 0.8

❤️ carol bob 0.8
💚 carol alice 0.7
🧍 carol 0.6

⏱️ 12
```

```console
$ catharsis run examples/emoji.feel --emoji --quiet
alice
    -> bob: ❤️ 0.88  🤝 0.57  🕊️ 0.35  🙏 0.28  💚 0.13
bob
    -> alice: ❤️ 0.81  🤝 0.80  🕊️ 0.33  🙏 0.28  💚 0.11
    -> carol: ❤️ 0.19  🤝 0.17  🙏 0.17
carol
  self: 🧍 0.24  😢 0.09
    -> bob: ❤️ 0.78  🤝 0.43  🕊️ 0.33  💚 0.12
    -> alice: 💚 0.26  😠 0.11  😨 0.07
```

**Why this needs an emotional model.** Two things, one of which is not about emoji at all.

The shorthand itself is a *spelling*, not a dialect: a glyph resolves through the same
alias table as `lonely` → `loneliness`, and `tests/test_emoji.py` asserts that a program
and its word-for-word transcription produce byte-identical worlds. A whole alternative
surface syntax costs one dict, which is the clearest demonstration going that the
vocabulary really is data.

And the behaviour underneath is the usual thing: nobody tells Carol what to do about her
jealousy. `reach_out` is pulled by love and loneliness and inhibited by fear and doubt, so
she has more pressure to approach Bob than anyone else does, and over twelve ticks she
wedges herself into the couple — ending with real warmth toward Bob (❤️ 0.78) and a
hardening rivalry with Alice (💚 0.26 with 😠 and 😨 behind it) that she was never
instructed to develop. Note that Bob now has a bond back to Carol and Alice does not.
