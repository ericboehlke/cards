package tui

import (
	"reflect"
	"regexp"
	"strconv"
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"
	"github.com/charmbracelet/x/ansi"

	"github.com/ericboehlke/cards/internal/cribbage"
)

func seeded(t *testing.T, seed int64, ascii bool) Model {
	t.Helper()
	m, err := New(Config{Seed: &seed, ASCII: ascii})
	if err != nil {
		t.Fatal(err)
	}
	return m
}

// press feeds keys to the model and returns the result.
func press(m Model, keys ...string) Model {
	for _, k := range keys {
		nm, _ := m.Update(keyMsg(k))
		m = nm.(Model)
	}
	return m
}

func keyMsg(k string) tea.KeyPressMsg {
	switch k {
	case "enter":
		return tea.KeyPressMsg{Code: tea.KeyEnter}
	case "space":
		return tea.KeyPressMsg{Code: tea.KeySpace, Text: " "}
	case "left":
		return tea.KeyPressMsg{Code: tea.KeyLeft}
	case "right":
		return tea.KeyPressMsg{Code: tea.KeyRight}
	case "pgup":
		return tea.KeyPressMsg{Code: tea.KeyPgUp}
	case "pgdown":
		return tea.KeyPressMsg{Code: tea.KeyPgDown}
	case "esc":
		return tea.KeyPressMsg{Code: tea.KeyEscape}
	case "ctrl+c":
		return tea.KeyPressMsg{Code: 'c', Mod: tea.ModCtrl}
	}
	r := []rune(k)
	return tea.KeyPressMsg{Code: r[0], Text: k}
}

func plain(m Model) string { return ansi.Strip(m.View().Content) }

// nextKeys is a simple scripted player: discard the first two cards, then play the first legal card.
func nextKeys(o cribbage.Observation) []string {
	switch o.Phase {
	case "discard":
		return []string{"1", "space", "2", "space", "enter", "esc"}
	case "pegging":
		for i, id := range o.YourHand {
			for _, a := range o.LegalActions {
				if a.Card != nil && *a.Card == id {
					return []string{strconv.Itoa(i + 1), "enter", "esc"}
				}
			}
		}
	}
	return nil
}

// script plays a whole game through the model and returns the keys used.
func script(t *testing.T, seed int64) []string {
	t.Helper()
	m := seeded(t, seed, false)
	var all []string
	for n := 0; !m.Done(); n++ {
		ks := nextKeys(m.Observation())
		if ks == nil || n > 1000 {
			t.Fatalf("stuck in phase %q", m.Observation().Phase)
		}
		m = press(m, ks...)
		if m.Status() != "" {
			t.Fatalf("unexpected status %q", m.Status())
		}
		all = append(all, ks...)
	}
	return all
}

func TestDiscardFlow(t *testing.T) {
	m := seeded(t, 3, false)
	if m.Observation().Phase != "discard" || len(m.Observation().YourHand) != 6 {
		t.Fatalf("bad start: %+v", m.Observation())
	}
	m = press(m, "enter")
	if !strings.Contains(m.Status(), "Select exactly 2") {
		t.Errorf("status %q", m.Status())
	}
	m = press(m, "space", "right", "space", "right", "space")
	if got := len(m.Selected()); got != 2 || !strings.Contains(m.Status(), "already selected") {
		t.Errorf("selected %v status %q", m.Selected(), m.Status())
	}
	m = press(m, "left", "space") // unselect position 1
	if len(m.Selected()) != 1 {
		t.Fatalf("selected %v", m.Selected())
	}
	m = press(m, "right", "space") // select position 2 instead
	if len(m.Selected()) != 2 {
		t.Fatalf("selected %v", m.Selected())
	}
	m = press(m, "enter")
	o := m.Observation()
	if o.Phase != "pegging" || len(o.YourHand) != 4 || m.Status() != "" || len(m.Selected()) != 0 {
		t.Errorf("after discard: %+v status %q", o, m.Status())
	}
	if o.Starter == nil || o.CribSize != 4 {
		t.Errorf("starter/crib: %+v", o)
	}
}

func TestCursorMovement(t *testing.T) {
	m := seeded(t, 3, false)
	m = press(m, "left", "h")
	if m.Cursor() != 0 {
		t.Errorf("cursor %d", m.Cursor())
	}
	m = press(m, "l", "right", "right")
	if m.Cursor() != 3 {
		t.Errorf("cursor %d", m.Cursor())
	}
	m = press(m, "6", "7")
	if m.Cursor() != 5 {
		t.Errorf("cursor %d", m.Cursor())
	}
	m = press(m, "right", "right")
	if m.Cursor() != 5 {
		t.Errorf("cursor %d", m.Cursor())
	}
}

func TestPeggingFlowAndIllegalPlay(t *testing.T) {
	found := false
	for seed := int64(1); seed < 60 && !found; seed++ {
		m := seeded(t, seed, false)
		for n := 0; !m.Done() && n < 400 && !found; n++ {
			o := m.Observation()
			if o.Phase == "pegging" {
				legal := map[string]bool{}
				for _, a := range o.LegalActions {
					legal[*a.Card] = true
				}
				for i, id := range o.YourHand {
					if legal[id] {
						continue
					}
					before := o
					m2 := press(m, strconv.Itoa(i+1), "enter")
					if m2.Status() == "" {
						t.Fatalf("illegal play %s not surfaced", id)
					}
					a, b := m2.Observation(), before
					if a.Count != b.Count || len(a.YourHand) != len(b.YourHand) || len(m2.Log()) != len(m.Log()) {
						t.Fatalf("illegal play changed state")
					}
					// the status clears on the next key and the model still plays on
					m2 = press(m2, "left")
					if m2.Status() != "" {
						t.Errorf("status not cleared")
					}
					found = true
					break
				}
				// a legal pegging play: enter plays the card under the cursor
				i := 0
				for j, id := range o.YourHand {
					if legal[id] {
						i = j
						break
					}
				}
				m = press(m, strconv.Itoa(i+1), "space")
				if len(m.Selected()) != 0 {
					t.Fatalf("pegging space should not mark cards")
				}
				m = press(m, "enter")
				if len(m.Log()) == 0 || !strings.Contains(strings.Join(m.Log(), "\n"), "you played") {
					t.Fatalf("play not logged: %v", m.Log())
				}
				continue
			}
			ks := nextKeys(o)
			if ks == nil {
				break
			}
			m = press(m, ks...)
		}
	}
	if !found {
		t.Fatal("never saw an unplayable card to test")
	}
}

func TestGameOverAndNewGame(t *testing.T) {
	keys := script(t, 5)
	m := seeded(t, 5, false)
	m = press(m, keys...)
	if !m.Done() || m.Observation().Phase != "complete" {
		t.Fatalf("not done: %+v", m.Observation())
	}
	if !strings.Contains(plain(m), "Press n for a new game") {
		t.Error("game over hint missing")
	}
	m = press(m, "left", "enter")
	if !strings.Contains(m.Status(), "game is over") {
		t.Errorf("status %q", m.Status())
	}
	m = press(m, "n")
	o := m.Observation()
	if m.Done() || o.Phase != "discard" || o.YouScore != 0 || o.OpponentScore != 0 {
		t.Errorf("new game: %+v", o)
	}
	if got := m.Log(); len(got) == 0 || !strings.Contains(got[0], "new game") {
		t.Errorf("log should start with a new-game marker: %v", got)
	}
	// n is ignored mid-game
	m = press(m, nextKeys(m.Observation())...)
	before, beforeLog := m.Observation(), m.Log()
	m = press(m, "n")
	if !reflect.DeepEqual(m.Observation(), before) || !reflect.DeepEqual(m.Log(), beforeLog) {
		t.Error("n mid game changed state")
	}
}

func TestQuitKeys(t *testing.T) {
	for _, k := range []string{"q", "ctrl+c"} {
		m := seeded(t, 1, false)
		nm, cmd := m.Update(keyMsg(k))
		if cmd == nil {
			t.Fatalf("%s: no command", k)
		}
		if _, ok := cmd().(tea.QuitMsg); !ok {
			t.Errorf("%s: not a quit", k)
		}
		if nm.(Model).View().Content != "" {
			t.Errorf("%s: view should clear on quit", k)
		}
	}
}

func TestHelpAndLogScroll(t *testing.T) {
	m := seeded(t, 3, false)
	if strings.Contains(plain(m), "move left") {
		t.Error("full help shown by default")
	}
	m = press(m, "?")
	if !strings.Contains(plain(m), "move left") {
		t.Error("? did not show full help")
	}
	if lines := strings.Split(plain(m), "\n"); len(lines) > m.height {
		t.Errorf("full help overflows: %d lines", len(lines))
	}
	m = press(m, "?")
	// Fill the log so it scrolls.
	for i := 0; i < 40; i++ {
		m.addLog("filler line " + strconv.Itoa(i))
	}
	m.syncLog()
	if !m.vp.AtBottom() {
		t.Fatal("log should follow new lines")
	}
	m = press(m, "pgup")
	if m.vp.AtBottom() {
		t.Error("pgup did not scroll")
	}
	m = press(m, "end")
	if !m.vp.AtBottom() {
		t.Error("end did not return to bottom")
	}
}

func TestViewsFitAndShowKeyInfo(t *testing.T) {
	for _, sz := range [][2]int{{64, 25}, {80, 25}, {100, 40}, {200, 60}} {
		m := seeded(t, 3, false)
		nm, _ := m.Update(tea.WindowSizeMsg{Width: sz[0], Height: sz[1]})
		m = nm.(Model)
		// play a few cards so the pegging area is busy, with the full help open
		m = press(m, nextKeys(m.Observation())...)
		m = press(m, "?")
		lines := strings.Split(plain(m), "\n")
		if len(lines) > sz[1] {
			t.Errorf("%v: %d lines tall", sz, len(lines))
		}
		for _, l := range lines {
			if w := ansi.StringWidth(l); w > sz[0] {
				t.Errorf("%v: line wider than screen (%d): %q", sz, w, l)
			}
		}
		for _, want := range []string{"Your hand", "Pegging", "Count:", "Sequence:", "You ", "Opp "} {
			if !strings.Contains(plain(m), want) {
				t.Errorf("%v: view lacks %q", sz, want)
			}
		}
	}
}

func TestDiscardViewGolden(t *testing.T) {
	v := plain(seeded(t, 3, false))
	for _, want := range []string{
		"Cribbage - first to 121",
		"🦆 You",
		"│ xXx │ │ Choose two cards",
		"Choose two cards for your crib.",
		"5♥", "6♦", "7♥", "8♠", "10♥", "J♦",
		"Select 2 cards with space (0 selected), then enter.",
		"New round. Dealer (owns the crib): you.",
		"opponent put two cards in the crib.",
		"←/→ move",
		"enter confirm",
	} {
		if !strings.Contains(v, want) {
			t.Errorf("view lacks %q:\n%s", want, v)
		}
	}
	m := press(seeded(t, 3, false), "space", "right", "space")
	// the markers row shows cursor and selection
	if v := plain(m); !strings.Contains(v, "+") || !strings.Contains(v, "^") || !strings.Contains(v, "(2 selected)") {
		t.Errorf("selection markers missing:\n%s", v)
	}
}

func TestASCIIFallback(t *testing.T) {
	m := seeded(t, 3, true)
	v := plain(m)
	if regexp.MustCompile("[♥♦♣♠█░╭│]").MatchString(v) {
		t.Errorf("unicode in ASCII view:\n%s", v)
	}
	for _, want := range []string{"5H", "6D", "7H", "8S", "10H", "JD", "+-", "[----"} {
		if !strings.Contains(v, want) {
			t.Errorf("ASCII view lacks %q:\n%s", want, v)
		}
	}
	// the log is converted too
	m = press(m, nextKeys(m.Observation())...)
	if v := plain(m); regexp.MustCompile("[♥♦♣♠]").MatchString(v) || !strings.Contains(v, "Starter card turned up") {
		t.Errorf("ASCII log:\n%s", v)
	}
	// unicode keeps red styling on hearts/diamonds
	if raw := seeded(t, 3, false).View().Content; !strings.Contains(raw, "\x1b[") {
		t.Error("no styling")
	}
}

func TestTooSmall(t *testing.T) {
	m := seeded(t, 3, false)
	nm, _ := m.Update(tea.WindowSizeMsg{Width: 40, Height: 10})
	m = nm.(Model)
	v := plain(m)
	if !strings.Contains(v, "Terminal too small (40x10)") || !strings.Contains(v, "64x25") || strings.Contains(v, "Your hand") {
		t.Errorf("view:\n%s", v)
	}
	// keys still work and growing again restores the table
	m = press(m, "space")
	nm, _ = m.Update(tea.WindowSizeMsg{Width: 80, Height: 30})
	if v := plain(nm.(Model)); !strings.Contains(v, "Your hand") || len(nm.(Model).Selected()) != 1 {
		t.Errorf("did not recover:\n%s", v)
	}
}

func TestDetectASCII(t *testing.T) {
	env := func(kv map[string]string) func(string) string { return func(k string) string { return kv[k] } }
	cases := []struct {
		name string
		env  map[string]string
		want bool
	}{
		{"utf8", map[string]string{"LANG": "en_US.UTF-8", "TERM": "xterm"}, false},
		{"utf8 no dash", map[string]string{"LC_ALL": "C.utf8"}, false},
		{"unset locale", map[string]string{"TERM": "xterm"}, true},
		{"posix", map[string]string{"LANG": "C"}, true},
		{"LC_ALL beats LANG", map[string]string{"LC_ALL": "C", "LANG": "en_US.UTF-8"}, true},
		{"dumb", map[string]string{"LANG": "en_US.UTF-8", "TERM": "dumb"}, true},
		{"forced on", map[string]string{"LANG": "en_US.UTF-8", "CARDS_ASCII": "1"}, true},
		{"forced off", map[string]string{"TERM": "dumb", "CARDS_ASCII": "0"}, false},
	}
	for _, c := range cases {
		if got := DetectASCII(env(c.env)); got != c.want {
			t.Errorf("%s: %v, want %v", c.name, got, c.want)
		}
	}
}

func TestPretty(t *testing.T) {
	got := pretty("you played TH, count 10, and 7D with AS; Starter card turned up: 10C.", false, false)
	if got != "you played 10♥, count 10, and 7♦ with A♠; Starter card turned up: 10♣." {
		t.Errorf("got %q", got)
	}
	if got := pretty("Show: you hand 5H TS", true, false); got != "Show: you hand 5H 10S" {
		t.Errorf("got %q", got)
	}
}

func TestSessionIsReproducible(t *testing.T) {
	a, b := script(t, 11), script(t, 11)
	if strings.Join(a, ",") != strings.Join(b, ",") || len(a) == 0 {
		t.Error("same seed, different game")
	}
}
