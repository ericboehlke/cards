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
- [ ] Go module layout (`go.mod`, `internal/cards`, `internal/cribbage`)
- [ ] Cards, hands, `card_id` parsing
- [ ] Scoring passes `scoring.json`
- [ ] Pegging passes `pegging.json`
- [ ] Discard table + greedy AI pass `ai.json` (float64 summation order, tie-breaks per README)
- [ ] Full game engine passes `games.json` (structured fields; `text`/`message` non-normative)
- [ ] CI / `go test ./...` wired up

### Step 3: port fuzz and oracle checks
- [ ] Port invariants from `fuzz_cribbage.py` to Go
- [ ] One-off differential run: Python oracle vs Go engine on shared injected decks and actions

### Step 4: JSON protocol in Go
- [ ] `cribbage serve --json` speaking the `api_cli.py` stdin/stdout protocol
- [ ] Existing Python agent/fuzz tooling runs against the Go binary unchanged
- [ ] Decide whether to expose `decks` in the protocol for replay

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
