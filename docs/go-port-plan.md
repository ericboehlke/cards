# Go port plan: cards as an SSH app (Charm)

Living progress doc. Update the checkboxes and "Notes / decisions" as work lands so any agent session can resume.

## Goal

Move this project (Python terminal card games: cribbage, plus an unfinished Yukon) to Go, using the
Charm libraries (Bubble Tea, Lip Gloss, Bubbles, Wish; https://charm.land/libs/) so the games are
served as a TUI over SSH (`ssh host`).

- **Gain:** single static binary, no Python on the server, real TUI (cursor selection, panels, resize),
  SSH public key as free player identity, per-session concurrency.
- **Lose:** Python iteration speed, seed parity across languages (hence injected decks), the Python
  LLM harness unless Go speaks the same JSON protocol.
- **Rule:** keep functionality. The Python implementation plus the golden fixtures are the spec until
  the Go version passes them all.
- Not yet verified: Charm v2 import paths and APIs (written from memory; check before use).

## Scope (Python, about 4,400 lines)

| Piece | Port effort |
|---|---|
| `cards/cards` (Card, Suit, `card_id`) | Small |
| Cribbage engine (`cribbage.py`, `pegging.py`, `scoring.py`, `hand.py`, `discards.py`) | Medium, already a pure state machine (`apply` -> events) |
| `discard_table.py` | Trivial, generate a Go map |
| Cribbage I/O (`cli.py`, `api.py`, `api_cli.py`) | Rewrite (Charm replaces CLI; JSON protocol kept) |
| Yukon | Redesign with tests first |
| Tests, oracle, fuzz | Port selectively |

## Checklist

Branch: `develop`.

### Step 1: freeze the Python spec (DONE, commit `feb8ba8`)
- [x] Deck injection: `Cribbage(decks=, first_dealer=)`, `CribbageEnv(decks=, first_dealer=)`
- [x] Fixture generator: `python -m cards.test.gen_golden --out testdata/golden`
- [x] Fixtures: `scoring.json`, `pegging.json`, `games.json`, `ai.json` + `testdata/golden/README.md` (schemas)
- [x] Drift test `cards/test/test_golden.py`; full suite passes (118 tests)
- [x] Independent review (fixtures cross-checked against `oracle_cribbage.py`); findings fixed

### Step 2: Go engine, no UI
- [x] Go module layout (`go.mod`, `internal/cards`, `internal/cribbage`)
- [x] Cards, hands, `card_id` parsing
- [x] Scoring passes `scoring.json`
- [x] Pegging passes `pegging.json`
- [x] Discard table + greedy AI pass `ai.json` (float64 summation order, tie-breaks per README)
- [x] Full game engine passes `games.json` (structured fields; `text`/`message` non-normative)
- [x] CI / `go test ./...` wired up (`.github/workflows/go.yml`)

### Step 3: port fuzz and oracle checks
- [x] Port invariants from `fuzz_cribbage.py` to Go (`internal/cribbage/fuzz_test.go`, `oracle_test.go`; native target `FuzzEnv`)
- [x] One-off differential run: Python oracle vs Go engine on shared injected decks and actions (`scripts/diff_python_go.py` + `cmd/diffdriver`)

Step 3 notes:
- `oracle_test.go` is a test-only port of `oracle_cribbage.py`; it is compared with `ScoreHand`/`ScoreHandBreakdown`
  and `CardsInPlay.Play` on random inputs. `fuzz_test.go` plays seeded games through `Game` (random and greedy
  players, illegal probes that must leave state unchanged) with the same rule checker as the Python fuzzer, and
  fuzzes `Env` with junk actions. Run the native fuzzer with `go test -run='^$' -fuzz=FuzzEnv ./internal/cribbage`.
- Differential run: `uv run python scripts/diff_python_go.py --seed N --games M [--junk P]` builds `cmd/diffdriver`,
  plays the Python `CribbageEnv` on seeded shuffled decks (some games with only 1-3 decks to hit `decks_exhausted`)
  with legal actions mixed with junk (bad types, wrong counts, odd card id spellings, cards not held, over 31), then
  replays the same decks and actions on the Go `Env` and compares every result with `text`/`prompt`/`message`
  stripped. Last run: 7000 games (seeds 0-3999 at 25% junk,
  100000-102999 at 60% junk), about 372k agent actions of which about 126k were rejected, 4.8k wins, 2.2k games ended
  by `decks_exhausted`: 0 differences in events, observations, error codes, `done` or scores. Deliberately breaking a
  Go scoring value or error code makes the run fail, so the comparison is live. Go-side fuzz found no rule violations
  either. (`not_your_turn` cannot occur through the Env API, so only `Game` fuzz covers it.)
  Limits: greedy opponent only; junk is limited to JSON shapes the Go `ActionInput` can represent (no non-string
  card values).

### Step 4: JSON protocol in Go
- [x] `cribbage serve --json` speaking the `api_cli.py` stdin/stdout protocol
- [x] Go binary is checked against Python over the protocol (no external Python agent/fuzz tooling exists in the repo; `scripts/check_protocol.py` and `cards/test/test_go_protocol.py` cover parity)
- [x] Decide whether to expose `decks` in the protocol for replay (yes: optional `decks`/`first_dealer` on `reset`)

### Step 5: Bubble Tea UI
- [ ] Thin model (game, cursor, event log) calling `apply`
- [ ] Lip Gloss layout: hands, pegging area, score panel, event log, key help
- [ ] Suit glyph fallback (`S/H/D/C`) for width/terminal issues
- [ ] `teatest` tests

### Step 6: SSH via Wish
- [ ] Host key, public-key identity middleware, per-session `tea.Program`
- [ ] Timeouts, per-key session limit, rate limiting; no shell exposure
- [ ] Deployment (systemd or container)
- [ ] Test in tmux and common terminals

### Step 7: Yukon
- [ ] Redesign with tests first, then port/implement in Go

### Cutover
- [ ] Go passes golden fixtures and old fuzz for a while
- [ ] Move Python to `legacy/` or tag it, then remove it

## Notes / decisions

- Deck injection semantics: `decks` is a list of full 52-card orders, one per deal; indexes 0-5 go to
  "you", 6-11 to the opponent, 12 is the starter. Dealing past the last deck ends the game with no
  winner (`decks_exhausted` event). Details in `testdata/golden/README.md`.
- Fixtures use only the deterministic `greedy` opponent; the `random` opponent is not covered.
- `uv.lock` is untracked and was not part of step 1. Regenerate with `uv lock` if missing.
- Run tests with `uv run --with pytest python -m pytest -q`.
- Step 4: `cmd/cribbage` + `internal/protocol` implement `serve --json [--seed N]`; only the greedy
  opponent (`--opponent random` is rejected with exit 2). The Go binary shuffles its own decks.
  The repo has no Python agent script that launches the protocol; the Python fuzzer drives the
  engine in-process. Protocol parity is verified by `scripts/check_protocol.py` (and
  `cards/test/test_go_protocol.py`), which launch any server command (`CRIBBAGE_SERVE_CMD`) and
  compare every reply with `CribbageEnv`. Protocol docs: `docs/cribbage_api.md`.
