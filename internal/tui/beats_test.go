package tui

import (
	"strings"
	"testing"

	"github.com/charmbracelet/x/ansi"
)

// untilCounting plays the scripted player (without the trailing esc) until the round-end count
// starts, and returns the model on its first counting beat.
func untilCounting(t *testing.T, seed int64, ascii bool) Model {
	t.Helper()
	m := seeded(t, seed, ascii)
	for n := 0; n < 400 && !m.counting(); n++ {
		ks := nextKeys(m.Observation())
		if len(ks) == 0 {
			t.Fatalf("no keys at %+v", m.Observation())
		}
		if m.playing() { // a pegging beat: any key skips it
			m = press(m, "esc")
			continue
		}
		m = press(m, ks[:len(ks)-1]...)
	}
	if !m.counting() {
		t.Fatal("never reached the count")
	}
	return m
}

func TestCountingWalksThroughBeats(t *testing.T) {
	m := untilCounting(t, 3, false)
	before := m.shownYou + m.shownOpp
	if before >= m.obs.YouScore+m.obs.OpponentScore && len(m.beats) > 1 {
		t.Fatalf("board already at the engine score (%d) before counting", before)
	}
	// game input is ignored while counting
	if nm := press(m, "left", "1", "x"); nm.bi != m.bi {
		t.Error("movement keys advanced the count")
	}
	seen := map[string]bool{}
	for m.counting() {
		seen[m.beats[m.bi].kind] = true
		v := plain(m)
		if !strings.Contains(v, "This round") || !strings.Contains(v, "Round total") {
			t.Fatalf("no ledger:\n%s", v)
		}
		m = press(m, "enter")
	}
	for _, k := range []string{"hand", "crib"} {
		if !seen[k] {
			t.Errorf("no %s beat (saw %v)", k, seen)
		}
	}
	if m.shownYou != m.obs.YouScore || m.shownOpp != m.obs.OpponentScore {
		t.Errorf("board %d-%d != engine %d-%d", m.shownYou, m.shownOpp, m.obs.YouScore, m.obs.OpponentScore)
	}
	if m.playing() || !strings.Contains(plain(m), "Your hand") {
		t.Error("hand not back after the count")
	}
}

func TestEscSkipsCount(t *testing.T) {
	m := press(untilCounting(t, 3, false), "esc")
	if m.playing() || m.shownYou != m.obs.YouScore || m.shownOpp != m.obs.OpponentScore {
		t.Errorf("playing=%v board %d-%d engine %d-%d", m.playing(), m.shownYou, m.shownOpp, m.obs.YouScore, m.obs.OpponentScore)
	}
}

func TestLedgerMatchesScoreChange(t *testing.T) {
	m := untilCounting(t, 3, false)
	m = press(m, "esc")
	tot := m.ledger.total()
	if tot[0]+tot[1] == 0 {
		t.Error("empty ledger")
	}
	if tot[0] > m.obs.YouScore || tot[1] > m.obs.OpponentScore {
		t.Errorf("ledger %v exceeds score %d-%d", tot, m.obs.YouScore, m.obs.OpponentScore)
	}
}

func TestCountingFitsAtAllSizes(t *testing.T) {
	for _, ascii := range []bool{false, true} {
		base := untilCounting(t, 3, ascii)
		for m0 := base; m0.counting(); m0 = press(m0, "enter") {
			for w := MinWidth; w <= 120; w += 7 {
				for _, h := range []int{MinHeight, 30, 50} {
					for _, help := range []bool{false, true} {
						m := resize(m0, w, h)
						m.showHelp = help
						m.layout()
						lines := strings.Split(m.View().Content, "\n")
						if len(lines) > h {
							t.Fatalf("ascii=%v %dx%d: %d lines", ascii, w, h, len(lines))
						}
						for _, l := range lines {
							if lw := ansi.StringWidth(l); lw > w {
								t.Fatalf("ascii=%v %dx%d: width %d: %q", ascii, w, h, lw, ansi.Strip(l))
							}
						}
					}
				}
			}
		}
	}
}

func TestPeggingBeatsAdvanceOnTick(t *testing.T) {
	m := seeded(t, 3, false)
	for n := 0; n < 400; n++ {
		if m.playing() && !m.roundEnd && len(m.beats) > 1 {
			g := m.gen
			nm, _ := m.Update(beatTickMsg{g - 1}) // stale tick: ignored
			if nm.(Model).bi != m.bi {
				t.Fatal("stale tick advanced")
			}
			nm, _ = m.Update(beatTickMsg{g})
			if nm.(Model).bi != m.bi+1 {
				t.Fatal("tick did not advance")
			}
			return
		}
		ks := nextKeys(m.Observation())
		if m.playing() {
			m = press(m, "esc")
		} else {
			m = press(m, ks[:len(ks)-1]...)
		}
	}
	t.Skip("no multi-beat pegging step in this game")
}
