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
- Charm v2 import paths and APIs verified against the module proxy on 2026-10-26 (see Step 5 notes).

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
- [x] Thin model (game, cursor, event log) calling `Env.Step` (`internal/tui`)
- [x] Lip Gloss layout: hands, pegging area, score panel, event log, key help
- [x] Suit glyph fallback (`S/H/D/C`) for width/terminal issues
- [x] `teatest` tests

Step 5 notes:
- Verified libraries (proxy.golang.org, `go list -m -versions`): the stable majors are v2 and use the
  vanity domain `charm.land`: `charm.land/bubbletea/v2 v2.1.0`, `charm.land/lipgloss/v2 v2.0.6`,
  `charm.land/bubbles/v2 v2.2.1` (viewport, help, key). The old `github.com/charmbracelet/{bubbletea,lipgloss,bubbles}`
  paths are v1 (bubbletea v1.3.10, lipgloss v1.1.0, bubbles v1.0.0) and are not used. teatest has no tagged release:
  `github.com/charmbracelet/x/exp/teatest/v2 v2.0.0-20261025003702-835ad0048169` (a pseudo-version; it imports
  `charm.land/bubbletea/v2`). `charm.land/x/exp/teatest/v2` does NOT resolve (module declares the github path), and the
  non-`/v2` teatest is for bubbletea v1. Pin this pseudo-version; it may change.
- v2 API differences from v1 (all confirmed in source): `Model.View()` returns `tea.View` (`tea.NewView(s)`, set
  `v.AltScreen = true` there, no `tea.WithAltScreen` option); keys arrive as `tea.KeyPressMsg` (`msg.String()`: space is
  `"space"`, `"pgup"`, `"pgdown"`, `"ctrl+c"`); lipgloss colors are `color.Color` (`lipgloss.Color("#hex")`),
  `Style.Width` includes border and padding, and Render always emits ANSI (the program downsamples), so tests strip it with
  `x/ansi`; `viewport.New()` takes options and uses `SetWidth/SetHeight`; `help.Model.SetWidth`.
  The viewport's default keymap binds space/j/k/u/d, so key messages are NOT forwarded to it (only pgup/pgdn/home/end are
  mapped by the model).
- Bubble Tea v2 renders diffs, so `teatest.WaitFor` on the output stream only sees the first full frame and later changed
  cells; tests wait for text that arrives in a whole frame and assert the rest on `FinalModel` / `Model.View()`.
- UI: `cribbage play [--seed N] [--ascii]`. Keys: arrows/hl move, 1-6 jump, space selects discards (up to 2), enter
  confirms the discard or, while pegging, always plays the card under the cursor (space does nothing in pegging, so there
  is no hidden mark), `?` full help, pgup/pgdn/home/end scroll the log, `n` new game once over, `q`/ctrl+c quit.
  Go/last card/show/deal happen inside `Env.Step`, so there is no go key and the log shows the whole opponent turn at once
  (no animation delay). Illegal moves (e.g. over 31, wrong discard count) show the engine message in the status line and
  change nothing. Cards the engine does not list as legal are dimmed AND marked `x` under the card (not colour-only).
  Minimum size 64x24; smaller shows a "Terminal too small" message clamped to the terminal (never wider or taller, empty
  at 0x0; keys still work); width is capped at 110. The one-line help footer is shortened to fit at 64 columns (full help
  with `?` fits too); tests check every width 64-120 and heights 24-50, help open and closed, both modes.
- The log box takes all spare height (it grows with the terminal), wraps long lines, and always scrolls to the newest line
  after every step (tested at 64x24 and 100x50), so the latest opponent turn is visible unless you scroll up.
- ASCII mode: `--ascii`, `CARDS_ASCII=1` (`=0` forces unicode), `TERM=dumb`, or a locale (LC_ALL, LC_CTYPE, LANG, first set)
  that is not UTF-8 (unset counts as not UTF-8). It switches to H/D/C/S, `+-|` borders, `#-` bars, `arrows`/`left`/`right`
  key names and ` | ` help separators. A test drives 55 seeded games and asserts every rune of the whole View (ANSI
  stripped) is below 0x80 in all phases, help open and closed, at several sizes including too-small ones.
- `n` starts a fresh game from the same random stream (with `--seed`, the whole session is reproducible); the engine's own
  `Reset` would replay the same decks, so it is not used. Shuffling mirrors `internal/protocol` (100 decks, random first dealer).
- Limits: the opponent is greedy only; no mouse; the crib contents are only visible in the log's show lines; no animation.

### Step 6: SSH via Wish
- [ ] Host key, public-key identity middleware, per-session `tea.Program`
- [ ] Timeouts, per-key session limit, rate limiting; no shell exposure
- [ ] Deployment (systemd or container)
- [ ] Test in tmux and common terminals

### Step 7: Yukon
- [ ] Redesign with tests first, then port/implement in Go

### Cutover
- [ ] Go passes golden fixtures and old fuzz for a while
- [x] Python (including the differential/protocol scripts) removed; see git history before that commit
- Note: after the cutover `scripts/`, `cmd/diffdriver` and `cards/` no longer exist; references above are historical

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
