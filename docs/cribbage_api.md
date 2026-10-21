# Cribbage API for LLM agents

You play as **you** against a computer **opponent** to 121 points. Opponent turns, the show
(counting hands and the crib) and dealing the next round all happen automatically, so after every
call it is your move or the game is over.

## Python

```python
from cards.cribbage.api import CribbageEnv

env = CribbageEnv(seed=1, opponent="greedy")   # or "random"
result = env.reset()                           # {"ok", "error", "events", "observation", "done"}
result = env.step({"type": "discard", "cards": ["5H", "KS"]})
```

## JSON lines

`cribbage api --seed 1 --opponent greedy` writes the opening result, then reads one JSON object per
line and answers each with one JSON line (nothing else is printed to stdout):

```
{"action": {"type": "discard", "cards": ["5H", "KS"]}}
{"action": {"type": "play", "card": "7D"}}
{"command": "observe"}
{"command": "reset", "seed": 3}
```

## Cards

Rank then suit: `A 2 3 4 5 6 7 8 9 T J Q K` and `H D C S`, e.g. `5H`, `TS`, `AC` (`10S` is also accepted).

## Rules summary

* Each player gets six cards and puts two in the **crib**, which belongs to the dealer (the deal
  alternates each round).
* The starter card is turned up. A jack starter scores the dealer **2** (his heels).
* **Pegging**: the player who is not the dealer leads. Players alternate playing one card, keeping
  the running count at 31 or less. Face cards count 10, aces 1. You score for making 15 (2), 31 (2),
  a pair (2), three of a kind (6), four of a kind (12) and a run of 3 or more among the last cards
  played, in any order (its length). If you cannot play, **go is said for you automatically**; when
  neither player can play, the last player to play a card scores **1** and the count restarts at 0
  with the other player leading. Making exactly 31 scores 2 instead of the last card point.
* **The show**: the non-dealer counts their hand with the starter, then the dealer's hand, then the
  dealer's crib: 2 per fifteen, 2 per pair, runs, 4 for a four-card flush in a hand (5 with the
  starter; the crib needs all five), 1 for his nobs (a jack matching the starter's suit).
* The game ends the instant someone reaches 121.

## Observation

| key | meaning |
| --- | --- |
| `phase` | `discard`, `pegging` or `complete` |
| `you_score`, `opponent_score`, `target_score` | pegboard |
| `dealer` | `you` or `opponent` (the crib owner) |
| `your_hand` | your cards now |
| `opponent_cards_in_hand` | how many cards the opponent still holds |
| `crib_size` | cards in the crib so far |
| `starter` | the turned-up card once discarding is done, else `null` |
| `count`, `sequence` | the running count and the cards played in this count (oldest first) |
| `played_this_round` | every card played this round (oldest first), including before a count reset |
| `legal_actions` | every action you may take; always non-empty unless the game is over |
| `winner` | `you`, `opponent` or `null` |
| `prompt` | a short instruction for the current phase |

## Results and errors

`step` returns `{"ok", "error", "events", "observation", "done"}`. `events` lists everything that
happened since your action (each has a human readable `text`). An illegal or malformed action gives
`ok: false` and `error: {"code", "message"}` and changes nothing: try again. Codes: `bad_action`,
`bad_discard`, `bad_play`, `card_not_in_hand`, `exceeds_31`, `not_your_turn`, `wrong_phase`,
`already_discarded`, `game_over`.

## Details worth knowing

* `count` and `sequence` reset to 0 / empty after a 31 or after both players are stuck (go). The
  player after whoever played last then leads; if they have no cards, the same player continues.
* In `show` events, `fifteens`, `pairs`, `runs`, `flush` and `his_nobs` are **points**, not counts
  (two fifteens is `fifteens: 4`). In `play` events `fifteen`, `thirtyone`, `pair` and `run` are
  points, `count` is the count after the card, and `points` is their total.
* A `go` event with `no_cards: true` means that player simply has no cards left.
* The winner's score can exceed 121; the game stops at the first score of 121 or more.
* The opponent discards before you when you are the non-dealer, so `crib_size` may already be 2.
  `opponent_cards_in_hand` is 4 once discarding is done. After the game ends, `your_hand` and
  `opponent_cards_in_hand` are stale and `legal_actions` is empty.
* There is never a need to pass or wait: if you cannot play, the game moves on by itself.
