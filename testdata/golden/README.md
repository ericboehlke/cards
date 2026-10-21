# Golden fixtures for cribbage

Language-neutral fixtures that pin down the behaviour of the Python implementation
(`cards/cribbage`). A port should load each file, replay the inputs and assert the outputs match
exactly. Regenerate with `python -m cards.test.gen_golden --out testdata/golden`;
`cards/test/test_golden.py` fails if the committed files drift from the Python code.

All files are pure JSON, written with sorted keys. Everything is deterministic.

## Conventions

* **Card ids**: rank then suit. Ranks `A 2 3 4 5 6 7 8 9 T J Q K` (ace low, no wraparound, `T` is
  ten), suits `H D C S`. Example: `5H`, `TS`, `AC`.
* Card values for counting: ace 1, 2-10 face value, `J Q K` 10. For runs and pairs, rank order is
  `A=1 ... K=13`.
* **Players**: `pegging.json` names players `"PLAYER1"` / `"PLAYER2"`; `scoring.json` has no
  players. In `games.json` events and observations use `"you"` (PLAYER1, the agent) and
  `"opponent"` (PLAYER2).
* **Compare structured fields, not prose.** The `text` of events, `observation.prompt` and error
  `message`s are human oriented and non-normative; a port may word them differently. They contain
  Python quirks (for example "you has no cards left (go)." and `wrong_phase` messages that embed
  the Python enum name such as `PEGGING`). Error `code`s are normative. The frozen text is only
  there so the Python test catches accidental drift.

## scoring.json

`{"cases": [...]}`. Each case:

| field | meaning |
| --- | --- |
| `name` | description (handcrafted) or `random N` |
| `hand` | four card ids |
| `starter` | card id of the starter |
| `is_crib` | crib hands need a five-card flush; in a normal hand a four-card flush also scores |
| `total` | expected score of the hand |
| `breakdown` | points by category: `fifteens`, `pairs`, `runs`, `flush`, `his_nobs`; they sum to `total` |

## pegging.json

`{"cases": [...]}`. Each case is `{"name", "steps"}`, a sequence of plays on one pegging round
starting from an empty table. Each step:

| field | meaning |
| --- | --- |
| `player` | who acts |
| `play` | a card id, or `"go"` (the player cannot play; see below) |
| `scores` | for both players: `{fifteen, thirtyone, go, pair, run, total}` points earned by this step |
| `count_after` | running count after the step |
| `sequence_after` | card ids in the current sequence (since the last reset to 0) |

Rules: a card scores 2 for making 15, 2 for 31, pairs/trips/quads for the trailing run of equal
ranks (2/6/12), and a run of the longest trailing group of 3+ cards that are consecutive ranks in
any order. The count resets to 0 after 31. A `go` on an empty sequence does nothing. The first `go`
scores nothing; when the other player has also said go, the player who played the last card scores
`go: 1` (it shows up under that player in `scores`, which may not be the player that acted) and the
sequence resets. Playing a card that would exceed 31 is invalid and raises in Python; no fixture covers it (in
`games.json` it is the `exceeds_31` error, but no step exercises it). Random cases end with
both players saying go so the last card point appears.

## games.json

`{"games": [...]}`. Full games of the `CribbageEnv` API 
(`cards/cribbage/api.py`, `docs/cribbage_api.md`) against the **greedy** opponent, which uses no randomness (the `random`
opponent depends on Python's RNG and is not used here). Each game:

| field | meaning |
| --- | --- |
| `opponent` | always `"greedy"` |
| `first_dealer` | `"you"` or `"opponent"`; the deal alternates every round |
| `decks` | list of full 52-card orders, one per deal, exactly as used (no shuffling) |
| `initial` | the result of constructing/resetting the environment |
| `steps` | list of `{"action", "result"}` applied in order |

**Deck semantics**: deal N (from 0) uses `decks[N]`. Cards 0-5 go to you, 6-11 to the opponent,
card 12 is the starter; the rest is unused. Observations list `your_hand` sorted by rank, then suit order `H D C S`. The `decks` list
holds exactly as many decks as the game needed.

`initial` and every `result` are `{ok, error, events, observation, done}`. Expect exact equality
including the `text` fields of events and `observation.prompt`. Each action was chosen as the
first entry of the previous `observation.legal_actions`, except the optional illegal probes at the
start of game 0 (the only game with `first_dealer` `"you"` and probes) which have `ok: false` and an `error` `{code, message}` and change nothing.

Illegal-action probes appear only in game 0. In the `CribbageEnv` Python API `decks` replaces the
shuffle: the engine's own `deck=` argument is ignored when `decks=` is given, and `first_dealer` is
ignored without `decks` (the first dealer is then a random cut). If the supplied decks run out
before the game ends the Env emits a `decks_exhausted` event and the game ends with no winner; the
fixtures supply enough decks that this never happens.

Opponent behaviour is part of what is frozen, and `ai.json` isolates it (below).

## ai.json

`{"discards": [...], "plays": [...]}` for the greedy opponent. Hand order everywhere means cards
sorted by rank (`A`..`K`), then suit `H D C S`.

Discard case: `hand` (six ids in hand order), `ai_is_dealer` (true if the AI owns the crib; the
starter is unknown at discard time), `chosen` (the two discarded ids) and the full `ranking`, best
first, with `hand_score` and `crib_score` as float64 values.

Algorithm (`rank_discards`): for each of the 15 two-card discards, enumerated with
`itertools.combinations` over the hand in hand order (so pairs are lexicographic by hand
position), the kept four cards are scored with the real hand scorer (not a crib) against every
possible starter, namely the 46 cards not in the six-card hand, iterated in deck order (suits
`H D C S`, ranks `A`..`K`). `hand_score` is the float64 sum of the integer scores divided by the
number of starters (a single division of an exact integer sum; a port should do the same, in
float64). `crib_score` comes from the Schell tables
(`cards/cribbage/discard_table.py`, from http://www.cribbageforum.com/SchellDiscard.htm), indexed by
the two discarded ranks (1-13): `player_crib_discard_table` if the AI is dealer, else the negated
`opponent_crib_discard_table`. The total `hand_score + crib_score` is sorted descending with a
stable sort, so ties keep the combination order above; the first entry is chosen. Total
comparisons are exact float64 comparisons of the sums, so reproduce the same operations.

Play case: `hand` (the AI's remaining cards in hand order), `sequence` (card ids played since the
count last reset to 0, oldest first, alternating players, which does not affect scoring), `chosen`
(a card id, or null if no card can be played). The AI plays the card with the highest pegging
score (`score_play`, the same rules as `pegging.json`) among cards that keep the count at 31 or
less; ties go to the earliest card in hand order.
