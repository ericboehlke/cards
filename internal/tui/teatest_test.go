package tui

import (
	"reflect"
	"strings"
	"testing"
	"time"

	tea "charm.land/bubbletea/v2"
	"github.com/charmbracelet/x/ansi"
	"github.com/charmbracelet/x/exp/teatest/v2"
)

func waitFor(t *testing.T, tm *teatest.TestModel, sub string) {
	t.Helper()
	teatest.WaitFor(t, tm.Output(), func(b []byte) bool {
		return strings.Contains(ansi.Strip(string(b)), sub)
	}, teatest.WithDuration(5*time.Second))
}

func send(tm *teatest.TestModel, keys []string) {
	for _, k := range keys {
		tm.Send(keyMsg(k))
	}
}

func finish(t *testing.T, tm *teatest.TestModel) Model {
	t.Helper()
	if err := tm.Quit(); err != nil {
		t.Fatal(err)
	}
	return tm.FinalModel(t, teatest.WithFinalTimeout(5*time.Second)).(Model)
}

// TestFullSeededGame drives a whole seeded game with scripted keys through a real tea.Program.
func TestFullSeededGame(t *testing.T) {
	keys := script(t, 5)
	m := seeded(t, 5, false)
	tm := teatest.NewTestModel(t, m, teatest.WithInitialTermSize(80, 30))
	waitFor(t, tm, "Your hand")
	send(tm, keys)
	waitFor(t, tm, "Game over")
	tm.Send(keyMsg("q"))
	fm := tm.FinalModel(t, teatest.WithFinalTimeout(5*time.Second)).(Model)
	// the program's final state equals a pure replay of the same keys
	want := press(seeded(t, 5, false), keys...)
	if !fm.Done() || !fm.quitting {
		t.Errorf("final: %+v quitting=%v", fm.Observation(), fm.quitting)
	}
	if !reflect.DeepEqual(fm.Observation(), want.Observation()) {
		t.Errorf("observation differs from replay:\n%+v\n%+v", fm.Observation(), want.Observation())
	}
	if !reflect.DeepEqual(fm.Log(), want.Log()) {
		t.Errorf("log differs from replay (%d vs %d lines)", len(fm.Log()), len(want.Log()))
	}
	if o := want.Observation(); o.Phase != "complete" || (o.YouScore < 121 && o.OpponentScore < 121) {
		t.Fatalf("replay not finished: %+v", o)
	}
}

func TestTeatestKeysAndResize(t *testing.T) {
	tm := teatest.NewTestModel(t, seeded(t, 3, false), teatest.WithInitialTermSize(80, 30))
	waitFor(t, tm, "Your hand")
	tm.Send(keyMsg("space"))
	tm.Send(keyMsg("enter"))
	tm.Send(tea.WindowSizeMsg{Width: 40, Height: 10})
	waitFor(t, tm, "Terminal too small (40x10)")
	tm.Send(tea.WindowSizeMsg{Width: 100, Height: 40})
	fm := finish(t, tm)
	if fm.width != 100 || fm.height != 40 {
		t.Errorf("size %dx%d", fm.width, fm.height)
	}
	v := plain(fm)
	for _, want := range []string{"Your hand", "(1 selected)", "Select exactly 2 cards"} {
		if !strings.Contains(v, want) {
			t.Errorf("final view lacks %q:\n%s", want, v)
		}
	}
}

func TestTeatestTinyStart(t *testing.T) {
	tm := teatest.NewTestModel(t, seeded(t, 3, false), teatest.WithInitialTermSize(40, 8))
	waitFor(t, tm, "Terminal too small (40x8)")
	fm := finish(t, tm)
	if fm.Observation().Phase != "discard" {
		t.Error("model should still be live")
	}
}

func TestTeatestASCII(t *testing.T) {
	tm := teatest.NewTestModel(t, seeded(t, 3, true), teatest.WithInitialTermSize(80, 30))
	var seen []byte
	teatest.WaitFor(t, tm.Output(), func(b []byte) bool {
		seen = append(seen[:0], b...)
		return strings.Contains(ansi.Strip(string(b)), "5H")
	}, teatest.WithDuration(5*time.Second))
	if !strings.Contains(ansi.Strip(string(seen)), "Your hand") {
		t.Fatalf("captured output is not a full frame: %q", seen)
	}
	for _, r := range ansi.Strip(string(seen)) {
		if r >= 0x80 {
			t.Fatalf("non-ASCII rune %q in program output", r)
		}
	}
	fm := finish(t, tm)
	if r, bad := nonASCII(fm.View().Content); bad {
		t.Errorf("non-ASCII rune %q in final view", r)
	}
}
