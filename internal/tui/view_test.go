package tui

import (
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"
	"github.com/charmbracelet/x/ansi"
)

func resize(m Model, w, h int) Model {
	nm, _ := m.Update(tea.WindowSizeMsg{Width: w, Height: h})
	return nm.(Model)
}

func nonASCII(s string) (rune, bool) {
	for _, r := range ansi.Strip(s) {
		if r >= 0x80 {
			return r, true
		}
	}
	return 0, false
}

// states returns models for one seed at the start, mid-pegging, and game over.
func states(t *testing.T, seed int64, ascii bool) []Model {
	t.Helper()
	m := seeded(t, seed, ascii)
	out := []Model{m}
	for n := 0; !m.Done() && n < 300; n++ {
		ks := nextKeys(m.Observation())
		if ks == nil {
			t.Fatalf("stuck")
		}
		m = press(m, ks...)
		if n == 3 {
			out = append(out, m)
		}
	}
	return append(out, m)
}

func TestASCIIModeIsPureASCII(t *testing.T) {
	sizes := [][2]int{{64, 24}, {66, 30}, {80, 24}, {100, 40}, {140, 50}, {20, 5}, {0, 0}}
	for seed := int64(1); seed <= 55; seed++ {
		m := seeded(t, seed, true)
		step := 0
		check := func(m Model) {
			for _, sz := range sizes[step%len(sizes):][:1] {
				for _, help := range []bool{false, true} {
					mm := resize(m, sz[0], sz[1])
					mm.showHelp = help
					mm.layout()
					if r, bad := nonASCII(mm.View().Content); bad {
						t.Fatalf("seed %d %v help=%v: non-ASCII rune %q (%U):\n%s", seed, sz, help, r, r, plain(mm))
					}
				}
			}
			step++
		}
		check(m)
		for n := 0; !m.Done() && n < 300; n++ {
			ks := nextKeys(m.Observation())
			if ks == nil {
				t.Fatal("stuck")
			}
			m = press(m, ks...)
			check(m)
		}
		check(m)
	}
	// every size for the initial and final states
	for _, m := range states(t, 2, true) {
		for _, sz := range sizes {
			for _, help := range []bool{false, true} {
				mm := resize(m, sz[0], sz[1])
				mm.showHelp = help
				mm.layout()
				if r, bad := nonASCII(mm.View().Content); bad {
					t.Fatalf("%v help=%v: non-ASCII rune %q", sz, help, r)
				}
			}
		}
	}
}

func TestEverythingFitsAtAllSizes(t *testing.T) {
	for _, ascii := range []bool{false, true} {
		for _, base := range states(t, 3, ascii) {
			for _, help := range []bool{false, true} {
				for w := MinWidth; w <= 120; w++ {
					for _, h := range []int{MinHeight, 25, 30, 40, 50} {
						m := resize(base, w, h)
						m.showHelp = help
						m.layout()
						lines := strings.Split(m.View().Content, "\n")
						if len(lines) > h {
							t.Fatalf("ascii=%v help=%v %dx%d: %d lines", ascii, help, w, h, len(lines))
						}
						for _, l := range lines {
							if lw := ansi.StringWidth(l); lw > min(w, maxWidth) {
								t.Fatalf("ascii=%v help=%v %dx%d: width %d: %q", ascii, help, w, h, lw, ansi.Strip(l))
							}
						}
						if f := ansi.Strip(m.footer()); strings.Contains(f, "…") || strings.Contains(f, "...") {
							t.Fatalf("footer truncated at %dx%d: %q", w, h, ansi.Strip(m.footer()))
						}
					}
				}
			}
		}
	}
}

func TestTooSmallNeverExceedsTerminal(t *testing.T) {
	for w := 0; w <= 70; w++ {
		for h := 0; h <= 30; h++ {
			if w >= MinWidth && h >= MinHeight {
				continue
			}
			m := resize(seeded(t, 3, false), w, h)
			v := m.View().Content
			lines := strings.Split(v, "\n")
			if v == "" {
				lines = nil
			}
			if len(lines) > h {
				t.Fatalf("%dx%d: %d lines", w, h, len(lines))
			}
			for _, l := range lines {
				if lw := ansi.StringWidth(l); lw > w {
					t.Fatalf("%dx%d: line width %d: %q", w, h, lw, l)
				}
			}
		}
	}
}

func TestPeggingEnterPlaysCursorCard(t *testing.T) {
	m := seeded(t, 3, false)
	m = press(m, "1", "space", "2", "space", "enter")
	o := m.Observation()
	if o.Phase != "pegging" {
		t.Fatalf("phase %s", o.Phase)
	}
	legal := map[string]bool{}
	for _, a := range o.LegalActions {
		legal[*a.Card] = true
	}
	i := -1
	for j, id := range o.YourHand {
		if legal[id] {
			i = j
			break
		}
	}
	// space marks nothing in pegging; enter plays the card under the cursor
	other := (i + 1) % len(o.YourHand)
	m = press(m, strconvI(i+1), "space", strconvI(other+1))
	if len(m.Selected()) != 0 {
		t.Fatalf("space marked a pegging card: %v", m.Selected())
	}
	want := o.YourHand[other]
	m2 := press(m, "enter")
	if legal[want] {
		if !strings.Contains(ansi.Strip(strings.Join(m2.Log(), "\n")), "you played "+cardLabel(want, false)) {
			t.Errorf("enter did not play cursor card %s: %v", want, m2.Log())
		}
	} else if m2.Status() == "" {
		t.Errorf("unplayable cursor card %s was not rejected", want)
	}
}

func strconvI(i int) string { return string(rune('0' + i)) }

func TestUnplayableCardsHaveNonColorMarker(t *testing.T) {
	for seed := int64(1); seed < 60; seed++ {
		m := seeded(t, seed, false)
		for n := 0; !m.Done() && n < 300; n++ {
			o := m.Observation()
			if o.Phase == "pegging" {
				legal := map[string]bool{}
				for _, a := range o.LegalActions {
					legal[*a.Card] = true
				}
				bad := 0
				for _, id := range o.YourHand {
					if !legal[id] {
						bad++
					}
				}
				lines := strings.Split(plain(m), "\n")
				for k, l := range lines {
					if strings.Contains(l, "Your hand") {
						marks := lines[k+4]
						if got := strings.Count(marks, "x"); got != bad {
							t.Fatalf("seed %d: %d unplayable but %d x markers: %q", seed, bad, got, marks)
						}
						if bad > 0 {
							return
						}
					}
				}
			}
			ks := nextKeys(o)
			if ks == nil {
				break
			}
			m = press(m, ks...)
		}
	}
	t.Fatal("no unplayable card seen")
}

func TestLogRoomAndLatestTurnVisible(t *testing.T) {
	tall := resize(seeded(t, 3, false), 100, 50)
	small := resize(seeded(t, 3, false), 100, 30)
	if tall.vp.Height() <= small.vp.Height()+10 {
		t.Errorf("log does not grow with height: %d vs %d", tall.vp.Height(), small.vp.Height())
	}
	for _, sz := range [][2]int{{64, 24}, {100, 50}} {
		for seed := int64(1); seed <= 8; seed++ {
			m := resize(seeded(t, seed, false), sz[0], sz[1])
			for n := 0; !m.Done() && n < 300; n++ {
				ks := nextKeys(m.Observation())
				for _, k := range ks {
					m = press(m, k)
				}
				if !m.vp.AtBottom() {
					t.Fatalf("%v seed %d: log not at bottom", sz, seed)
				}
				last := ansi.Strip(m.Log()[len(m.Log())-1])
				squash := func(x string) string { return strings.Join(strings.Fields(x), "") }
				if !strings.Contains(squash(ansi.Strip(m.vp.View())), squash(last)) {
					t.Fatalf("%v seed %d: latest log line %q not visible:\n%s", sz, seed, last, plain(m))
				}
			}
		}
	}
}
