package cribbage

import (
	"encoding/json"
	"os"
	"reflect"
	"strconv"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

// stripText removes the non-normative human oriented fields.
func stripText(v any) any {
	switch x := v.(type) {
	case map[string]any:
		for _, k := range []string{"text", "prompt", "message"} {
			delete(x, k)
		}
		for k, e := range x {
			x[k] = stripText(e)
		}
	case []any:
		for i, e := range x {
			x[i] = stripText(e)
		}
	}
	return v
}

func roundTrip(t *testing.T, v any) any {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func TestGamesGolden(t *testing.T) {
	data, err := os.ReadFile("../../testdata/golden/games.json")
	if err != nil {
		t.Fatal(err)
	}
	var fx struct {
		Games []struct {
			Opponent    string          `json:"opponent"`
			FirstDealer string          `json:"first_dealer"`
			Decks       [][]string      `json:"decks"`
			Initial     json.RawMessage `json:"initial"`
			Steps       []struct {
				Action ActionInput     `json:"action"`
				Result json.RawMessage `json:"result"`
			} `json:"steps"`
		} `json:"games"`
	}
	if err := json.Unmarshal(data, &fx); err != nil {
		t.Fatal(err)
	}
	if len(fx.Games) == 0 {
		t.Fatal("no games")
	}
	textMismatches := 0
	check := func(name string, got Result, want json.RawMessage) {
		var w any
		if err := json.Unmarshal(want, &w); err != nil {
			t.Fatal(err)
		}
		g := roundTrip(t, got)
		var wFull any
		_ = json.Unmarshal(want, &wFull)
		gFull := roundTrip(t, got)
		if !reflect.DeepEqual(stripText(g), stripText(w)) {
			gb, _ := json.MarshalIndent(g, "", " ")
			wb, _ := json.MarshalIndent(w, "", " ")
			t.Fatalf("%s mismatch\n got: %s\nwant: %s", name, gb, wb)
		}
		if !reflect.DeepEqual(gFull, wFull) {
			textMismatches++
		}
	}
	for gi, g := range fx.Games {
		if g.Opponent != "greedy" {
			t.Fatalf("game %d: unsupported opponent %q", gi, g.Opponent)
		}
		var decks []cards.Hand
		for _, d := range g.Decks {
			h, err := cards.ParseHand(d)
			if err != nil {
				t.Fatal(err)
			}
			decks = append(decks, h)
		}
		env, initial, err := NewEnv(decks, g.FirstDealer)
		if err != nil {
			t.Fatal(err)
		}
		check("game "+strconv.Itoa(gi)+" initial", initial, g.Initial)
		for si, s := range g.Steps {
			check("game "+strconv.Itoa(gi)+" step "+strconv.Itoa(si), env.Step(s.Action), s.Result)
		}
		if !env.Done() {
			t.Errorf("game %d not done after all steps", gi)
		}
	}
	if textMismatches > 0 {
		t.Logf("%d results differ from golden only in non-normative text", textMismatches)
	}
}

func TestDecksExhausted(t *testing.T) {
	env, r, err := NewEnv([]cards.Hand{cards.Deck()}, "you")
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; !r.Done && i < 100; i++ {
		r = env.Step(r.Observation.LegalActions[0])
		if !r.OK {
			t.Fatalf("step failed: %+v", r.Error)
		}
	}
	if !r.Done {
		t.Fatal("game never ended")
	}
	if r.Observation.Winner != nil || r.Observation.Phase != "complete" {
		t.Fatalf("expected no winner, got %+v", r.Observation)
	}
	if last := r.Events[len(r.Events)-1]; last.Type != "decks_exhausted" {
		t.Fatalf("last event %q, want decks_exhausted", last.Type)
	}
	if r := env.Step(ActionInput{Type: "play", Card: strPtr("AH")}); r.OK || r.Error.Code != "game_over" {
		t.Fatalf("step after exhaustion: %+v", r)
	}
}

func TestNewGameRejectsBadDeck(t *testing.T) {
	d := cards.Deck()
	d[1] = d[0]
	if _, err := NewGame([]cards.Hand{d}, Player1); err == nil {
		t.Fatal("expected error for duplicate card")
	}
	if _, _, err := NewEnv(nil, "you"); err == nil {
		t.Fatal("expected error for no decks")
	}
}

// rulesDeck deals P1 KS KH 5C 5D 2S 2H and P2 KD 5H AS AH 2D 2C, with a non-jack starter.
func rulesDeck() cards.Hand {
	top := cards.MustParseHand("KS", "KH", "5C", "5D", "2S", "2H", "KD", "5H", "AS", "AH", "2D", "2C", "9S")
	d := append(cards.Hand(nil), top...)
	for _, c := range cards.Deck() {
		if !top.Contains(c) {
			d = append(d, c)
		}
	}
	return d
}

func wantCode(t *testing.T, name string, err error, code string) {
	t.Helper()
	ia, ok := err.(*IllegalAction)
	if !ok || ia.Code != code {
		t.Errorf("%s: got %v, want IllegalAction %q", name, err, code)
	}
}

func TestGameErrorCodes(t *testing.T) {
	g, err := NewGame([]cards.Hand{rulesDeck()}, Player1)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := g.Deal(); err != nil {
		t.Fatal(err)
	}
	disc := func(ids ...string) Action { return Action{ActionDiscard, cards.MustParseHand(ids...)} }
	play := func(id string) Action { return Action{ActionPlay, cards.MustParseHand(id)} }

	_, err = g.Apply(Player1, disc("KD", "5H"))
	wantCode(t, "card_not_in_hand", err, "card_not_in_hand")
	if _, err = g.Apply(Player1, disc("2S", "2H")); err != nil {
		t.Fatal(err)
	}
	_, err = g.Apply(Player1, disc("KS", "KH"))
	wantCode(t, "already_discarded", err, "already_discarded")
	if _, err = g.Apply(Player2, disc("AS", "AH")); err != nil {
		t.Fatal(err)
	}
	if g.State() != StatePegging {
		t.Fatalf("state %v", g.State())
	}
	_, err = g.Apply(Player1, play("KS"))
	wantCode(t, "not_your_turn", err, "not_your_turn")
	for _, s := range []struct {
		p  Player
		id string
	}{{Player2, "KD"}, {Player1, "KS"}, {Player2, "5H"}} {
		if _, err = g.Apply(s.p, play(s.id)); err != nil {
			t.Fatalf("%v plays %s: %v", s.p, s.id, err)
		}
	}
	_, err = g.Apply(Player1, play("KH"))
	wantCode(t, "exceeds_31", err, "exceeds_31")
}

func TestEnvErrorCodesAndDone(t *testing.T) {
	env, _, err := NewEnv([]cards.Hand{rulesDeck()}, "you")
	if err != nil {
		t.Fatal(err)
	}
	// "you" deals, so the opponent leads after the discards; the agent discards first.
	r := env.Step(ActionInput{Type: "discard", Cards: []string{"KD", "5H"}})
	if r.OK || r.Error.Code != "card_not_in_hand" {
		t.Fatalf("got %+v", r.Error)
	}
	r = env.Step(ActionInput{Type: "play", Card: strPtr("KS")})
	if r.OK || r.Error.Code != "wrong_phase" {
		t.Fatalf("got %+v", r.Error)
	}
}

func TestNewEnvInvalidDeckReturnsNil(t *testing.T) {
	d := cards.Deck()
	d[1] = d[0]
	env, _, err := NewEnv([]cards.Hand{d}, "you")
	if err == nil || env != nil {
		t.Fatalf("want nil env and error, got %v %v", env, err)
	}
}

func TestNewEnvCopiesDecks(t *testing.T) {
	decks := []cards.Hand{rulesDeck()}
	env, first, err := NewEnv(decks, "you")
	if err != nil {
		t.Fatal(err)
	}
	decks[0][0], decks[0][1] = decks[0][1], decks[0][0]
	decks[0][2] = decks[0][3]
	again, err := env.Reset()
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first.Observation.YourHand, again.Observation.YourHand) {
		t.Fatalf("Reset changed after caller mutated decks: %v vs %v", first.Observation.YourHand, again.Observation.YourHand)
	}
}

func TestParseActionCardPresence(t *testing.T) {
	for _, in := range []ActionInput{
		{Type: "play", Card: strPtr(""), Cards: []string{"AH"}},
		{Type: "play", Card: strPtr("ZZ")},
		{Type: "play"},
		{Type: "discard"},
		{Type: "bogus"},
	} {
		_, err := ParseAction(in)
		wantCode(t, "bad_action", err, "bad_action")
	}
	if a, err := ParseAction(ActionInput{Type: "play", Cards: []string{"AH"}}); err != nil || len(a.Cards) != 1 {
		t.Errorf("cards-form play: %v %v", a, err)
	}
	if a, err := ParseAction(ActionInput{Type: "play", Card: strPtr("7D"), Cards: []string{"AH"}}); err != nil || a.Cards[0].ID() != "7D" {
		t.Errorf("card preferred over cards: %v %v", a, err)
	}
	var in ActionInput
	if err := json.Unmarshal([]byte(`{"type":"play","card":"","cards":["AH"]}`), &in); err != nil || in.Card == nil {
		t.Fatalf("empty-string card must decode as present: %+v %v", in, err)
	}
}
