# Cards

A terminal cribbage game written in Go, built with [Bubble Tea](https://charm.land/libs/). You
play against a greedy computer opponent to 121 points.

## Requirements

Go (see `go.mod` for the version).

## Play

```
go run ./cmd/cribbage play            # terminal UI
go run ./cmd/cribbage play --ascii    # H/D/C/S and plain borders instead of suit glyphs
go run ./cmd/cribbage play --seed 1   # reproducible session
```

Keys: arrows or `h`/`l` move, `1`-`6` jump to a card, space selects discards, enter confirms the
discard or plays the card under the cursor, `?` shows help, `n` starts a new game once one is over,
`q` quits. Minimum terminal size is 64x24.

Or build a binary: `go build -o cribbage ./cmd/cribbage`.

## JSON protocol

`cribbage serve --json` speaks JSON lines on stdin/stdout so an LLM or script can play against the
computer; see [docs/cribbage_api.md](docs/cribbage_api.md).

## Layout

* `cmd/cribbage`: the command line program (`play`, `serve`)
* `internal/cards`: cards and card ids
* `internal/cribbage`: scoring, pegging, greedy AI and the game state machine
* `internal/protocol`: JSON-lines protocol
* `internal/tui`: Bubble Tea UI
* `testdata/golden`: golden fixtures for the engine ([format](testdata/golden/README.md))
* `docs/go-port-plan.md`: history and notes from the port from Python

The original Python implementation (including Yukon) was removed after the port; it lives in git
history before the "Remove Python" commit.

## Tests

```
go test ./...
go test -run='^$' -fuzz=FuzzEnv ./internal/cribbage   # native fuzzer
```

## Ideas

### Cribbage

- [ ] Add hail mary and min points option to discard scoring
- [ ] Add pegging value to discard scoring: https://www.cribbage.org/NewSite/tips/colvert2.asp
- [ ] Training with the add star method: http://www.cribbageforum.com/YourCrib.htm
