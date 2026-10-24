// Package tui is the Bubble Tea terminal UI for single-player cribbage against the greedy opponent.
// The model is thin: all rules live in internal/cribbage and the model only holds the Env, the
// cursor/selection and the event log.
package tui

import (
	crand "crypto/rand"
	"encoding/binary"
	mrand "math/rand/v2"
	"strings"

	"github.com/ericboehlke/cards/internal/cards"
	"github.com/ericboehlke/cards/internal/cribbage"
)

// NumDecks is how many shuffled decks a game gets (one per deal); a game never needs near this many.
const NumDecks = 100

// NewGameFunc starts a fresh game. Tests inject fixed decks through it.
type NewGameFunc func() (*cribbage.Env, cribbage.Result, error)

// Config configures the UI.
type Config struct {
	// Seed, when non-nil, makes shuffling and the first dealer reproducible. Later games in the
	// same session continue the same random stream, so the whole session is reproducible.
	Seed *int64
	// ASCII uses H/D/C/S and ASCII borders instead of unicode suit glyphs.
	ASCII bool
	// NewGame overrides how games are created (tests). Nil means shuffled decks from Seed.
	NewGame NewGameFunc
}

// DetectASCII reports whether the environment calls for the ASCII fallback: CARDS_ASCII=1/true
// forces it, CARDS_ASCII=0/false forces unicode, otherwise it is used when TERM=dumb or the locale
// (LC_ALL, then LC_CTYPE, then LANG) does not name UTF-8 (an unset locale counts as not UTF-8).
func DetectASCII(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("CARDS_ASCII"))) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	}
	if getenv("TERM") == "dumb" {
		return true
	}
	for _, k := range []string{"LC_ALL", "LC_CTYPE", "LANG"} {
		if v := getenv(k); v != "" {
			l := strings.ToLower(v)
			return !(strings.Contains(l, "utf-8") || strings.Contains(l, "utf8"))
		}
	}
	return true
}

// ShuffledGame returns a NewGameFunc that deals shuffled decks from a stream seeded with seed (a
// random seed when nil).
func ShuffledGame(seed *int64) (NewGameFunc, error) {
	var s int64
	if seed != nil {
		s = *seed
	} else {
		var b [8]byte
		if _, err := crand.Read(b[:]); err != nil {
			return nil, err
		}
		s = int64(binary.LittleEndian.Uint64(b[:]))
	}
	rng := mrand.New(mrand.NewPCG(uint64(s), 0x9e3779b97f4a7c15))
	return func() (*cribbage.Env, cribbage.Result, error) {
		decks := make([]cards.Hand, NumDecks)
		for i := range decks {
			d := cards.Deck()
			rng.Shuffle(len(d), func(a, b int) { d[a], d[b] = d[b], d[a] })
			decks[i] = d
		}
		first := "you"
		if rng.IntN(2) == 1 {
			first = "opponent"
		}
		return cribbage.NewEnv(decks, first)
	}, nil
}
