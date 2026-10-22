package cribbage

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

type pegFixtureScore struct {
	Fifteen   int `json:"fifteen"`
	Thirtyone int `json:"thirtyone"`
	Go        int `json:"go"`
	Pair      int `json:"pair"`
	Run       int `json:"run"`
	Total     int `json:"total"`
}

type pegFixture struct {
	Cases []struct {
		Name  string `json:"name"`
		Steps []struct {
			Player        string                     `json:"player"`
			Play          string                     `json:"play"`
			Scores        map[string]pegFixtureScore `json:"scores"`
			CountAfter    int                        `json:"count_after"`
			SequenceAfter []string                   `json:"sequence_after"`
		} `json:"steps"`
	} `json:"cases"`
}

func TestPeggingGolden(t *testing.T) {
	data, err := os.ReadFile("../../testdata/golden/pegging.json")
	if err != nil {
		t.Fatal(err)
	}
	var fx pegFixture
	if err := json.Unmarshal(data, &fx); err != nil {
		t.Fatal(err)
	}
	if len(fx.Cases) == 0 {
		t.Fatal("no cases")
	}
	names := map[string]Player{"PLAYER1": Player1, "PLAYER2": Player2}
	for _, tc := range fx.Cases {
		t.Run(tc.Name, func(t *testing.T) {
			cip := NewCardsInPlay()
			for i, st := range tc.Steps {
				p, ok := names[st.Player]
				if !ok {
					t.Fatalf("step %d: unknown player %q", i, st.Player)
				}
				var got PegScores
				if st.Play == "go" {
					got = cip.Go(p)
				} else {
					var err error
					got, err = cip.Play(p, cards.MustParseCard(st.Play))
					if err != nil {
						t.Fatalf("step %d: %v", i, err)
					}
				}
				for n, pl := range names {
					w := st.Scores[n]
					if got[pl] != (PeggingScore{w.Fifteen, w.Thirtyone, w.Go, w.Pair, w.Run, w.Total}) {
						t.Errorf("step %d %s: scores %+v want %+v", i, n, got[pl], w)
					}
				}
				if cip.Count() != st.CountAfter {
					t.Errorf("step %d: count %d want %d", i, cip.Count(), st.CountAfter)
				}
				ids := []string{}
				for _, pc := range cip.Sequence() {
					ids = append(ids, pc.Card.ID())
				}
				if !reflect.DeepEqual(ids, append([]string{}, st.SequenceAfter...)) {
					t.Errorf("step %d: sequence %v want %v", i, ids, st.SequenceAfter)
				}
			}
		})
	}
}

func TestPeggingExceeds31(t *testing.T) {
	cip := NewCardsInPlay()
	for _, id := range []string{"KH", "QH", "TH"} {
		if _, err := cip.Play(Player1, cards.MustParseCard(id)); err != nil && id != "TH" {
			t.Fatal(err)
		}
	}
	if _, err := cip.Play(Player2, cards.MustParseCard("5H")); err != ErrExceeds31 {
		t.Fatalf("want ErrExceeds31, got %v", err)
	}
}
