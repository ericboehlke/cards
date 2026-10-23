package protocol

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

type reply struct {
	OK    bool `json:"ok"`
	Error *struct {
		Code string `json:"code"`
	} `json:"error"`
	Events      []json.RawMessage `json:"events"`
	Observation struct {
		Phase        string            `json:"phase"`
		Dealer       string            `json:"dealer"`
		YourHand     []string          `json:"your_hand"`
		LegalActions []json.RawMessage `json:"legal_actions"`
	} `json:"observation"`
	Done bool `json:"done"`
}

func serve(t *testing.T, input string, seed int64) []reply {
	t.Helper()
	var out bytes.Buffer
	if err := Serve(strings.NewReader(input), &out, Options{Seed: &seed}); err != nil {
		t.Fatal(err)
	}
	var replies []reply
	for _, line := range strings.Split(strings.TrimSuffix(out.String(), "\n"), "\n") {
		var r reply
		if err := json.Unmarshal([]byte(line), &r); err != nil {
			t.Fatalf("bad output line %q: %v", line, err)
		}
		replies = append(replies, r)
	}
	return replies
}

func TestFramingAndErrors(t *testing.T) {
	input := strings.Join([]string{
		"not json", "[1, 2]", `{"command": "observe"}`, "", "   ",
		`{"action": {"type": "play", "card": "AS"}}`, `{"action": 5}`, `{"command": "x"}`,
		`{"command": "observe"} {"command": "observe"}`,
		`{"command": "reset", "seed": "x"}`, `{"command": "reset", "decks": [["AS"]]}`,
		`{"command": "reset", "first_dealer": "me"}`,
	}, "\n") // no trailing newline
	got := serve(t, input, 1)
	want := []string{"bad_json", "bad_request", "", "wrong_phase", "bad_action", "bad_request", "bad_json",
		"bad_request", "bad_request", "bad_request"}
	if len(got) != 1+len(want) {
		t.Fatalf("got %d replies, want %d", len(got), 1+len(want))
	}
	if !got[0].OK || got[0].Observation.Phase != "discard" {
		t.Fatalf("bad opening: %+v", got[0])
	}
	for i, code := range want {
		r := got[i+1]
		if code == "" {
			if !r.OK || r.Error != nil {
				t.Errorf("reply %d: want ok, got %+v", i+1, r)
			}
		} else if r.OK || r.Error == nil || r.Error.Code != code {
			t.Errorf("reply %d: want error %s, got %+v", i+1, code, r.Error)
		}
		if r.Events == nil || len(r.Events) != 0 {
			t.Errorf("reply %d: events must be []", i+1)
		}
		if r.Observation.Phase != "discard" {
			t.Errorf("reply %d: observation lost", i+1)
		}
	}
}

func TestSeedIsReproducibleAndResetReplays(t *testing.T) {
	var a, b bytes.Buffer
	for _, buf := range []*bytes.Buffer{&a, &b} {
		seed := int64(42)
		if err := Serve(strings.NewReader(`{"command":"reset"}`+"\n"), buf, Options{Seed: &seed}); err != nil {
			t.Fatal(err)
		}
	}
	if !bytes.Equal(a.Bytes(), b.Bytes()) {
		t.Error("same seed gave different output")
	}
	lines := strings.Split(strings.TrimSpace(a.String()), "\n")
	if lines[0] != lines[1] {
		t.Error("reset without a seed should replay the seeded game")
	}
}

func TestDecksAndFirstDealerReplay(t *testing.T) {
	deck := cards.Deck().IDs()
	msg, _ := json.Marshal(map[string]any{"command": "reset", "decks": [][]string{deck}, "first_dealer": "opponent"})
	got := serve(t, string(msg)+"\n"+`{"command":"reset"}`+"\n"+`{"command":"reset","decks":null,"first_dealer":null}`, 3)
	if got[1].Observation.Dealer != "opponent" || got[2].Observation.Dealer != "opponent" {
		t.Errorf("fixed first_dealer not honoured: %q %q", got[1].Observation.Dealer, got[2].Observation.Dealer)
	}
	if len(got[1].Observation.YourHand) != 6 || got[1].Observation.YourHand[0] != "AH" {
		t.Errorf("decks not used as given: %v", got[1].Observation.YourHand)
	}
	if !got[3].OK {
		t.Error("clearing decks failed")
	}
}

func TestShuffledGamePlaysToTheEnd(t *testing.T) {
	for seed := int64(0); seed < 20; seed++ {
		s, r, err := NewServer(Options{Seed: &seed})
		if err != nil {
			t.Fatal(err)
		}
		for steps := 0; !r.Done; steps++ {
			if steps > 2000 {
				t.Fatalf("seed %d: game did not end", seed)
			}
			acts := r.Observation.LegalActions
			b, _ := json.Marshal(map[string]any{"action": acts[steps%len(acts)]})
			r = s.Handle(string(b))
			if !r.OK {
				t.Fatalf("seed %d: legal action rejected: %+v", seed, r.Error)
			}
		}
		if r.Observation.Winner == nil {
			t.Errorf("seed %d: no winner (decks exhausted?)", seed)
		}
	}
}

func TestBadCardMessageIsClean(t *testing.T) {
	var out bytes.Buffer
	seed := int64(1)
	in := `{"action": {"type": "play", "card": "X"}}` + "\n"
	if err := Serve(strings.NewReader(in), &out, Options{Seed: &seed}); err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(out.String()), "\n")
	var r struct {
		Error struct{ Code, Message string }
	}
	if err := json.Unmarshal([]byte(lines[1]), &r); err != nil {
		t.Fatal(err)
	}
	if r.Error.Code != "bad_action" || strings.Contains(r.Error.Message, "0x") || strings.Contains(r.Error.Message, "{Type") ||
		!strings.HasPrefix(r.Error.Message, `Malformed action: not a card id: "X"`) {
		t.Fatalf("unclean message: %+v", r.Error)
	}
}
