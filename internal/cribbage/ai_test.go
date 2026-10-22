package cribbage

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

func TestAIGolden(t *testing.T) {
	data, err := os.ReadFile("../../testdata/golden/ai.json")
	if err != nil {
		t.Fatal(err)
	}
	var fx struct {
		Discards []struct {
			Name       string   `json:"name"`
			Hand       []string `json:"hand"`
			AIIsDealer bool     `json:"ai_is_dealer"`
			Chosen     []string `json:"chosen"`
			Ranking    []struct {
				Discard   []string `json:"discard"`
				HandScore float64  `json:"hand_score"`
				CribScore float64  `json:"crib_score"`
			} `json:"ranking"`
		} `json:"discards"`
		Plays []struct {
			Name     string   `json:"name"`
			Hand     []string `json:"hand"`
			Sequence []string `json:"sequence"`
			Chosen   *string  `json:"chosen"`
		} `json:"plays"`
	}
	if err := json.Unmarshal(data, &fx); err != nil {
		t.Fatal(err)
	}
	if len(fx.Discards) == 0 || len(fx.Plays) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range fx.Discards {
		hand := cards.MustParseHand(c.Hand...)
		got := RankDiscards(hand, c.AIIsDealer)
		if len(got) != len(c.Ranking) {
			t.Fatalf("%s: %d rankings, want %d", c.Name, len(got), len(c.Ranking))
		}
		for i, w := range c.Ranking {
			g := got[i]
			if g.Discarded[0].ID() != w.Discard[0] || g.Discarded[1].ID() != w.Discard[1] ||
				g.HandScore != w.HandScore || g.CribScore != w.CribScore {
				t.Fatalf("%s: rank %d got %v %v %v, want %v %v %v", c.Name, i,
					g.Discarded, g.HandScore, g.CribScore, w.Discard, w.HandScore, w.CribScore)
			}
		}
		ch := ChooseDiscards(hand, c.AIIsDealer)
		if ch[0].ID() != c.Chosen[0] || ch[1].ID() != c.Chosen[1] {
			t.Errorf("%s: chose %v, want %v", c.Name, ch, c.Chosen)
		}
	}
	for _, c := range fx.Plays {
		play := NewCardsInPlay()
		p := Player1
		for _, id := range c.Sequence {
			if _, err := play.Play(p, cards.MustParseCard(id)); err != nil {
				t.Fatalf("%s: %v", c.Name, err)
			}
			p = p.Other()
		}
		card, ok := PlayAI(cards.MustParseHand(c.Hand...), play)
		switch {
		case c.Chosen == nil && ok:
			t.Errorf("%s: played %v, want none", c.Name, card)
		case c.Chosen != nil && (!ok || card.ID() != *c.Chosen):
			t.Errorf("%s: got %v ok=%v, want %s", c.Name, card, ok, *c.Chosen)
		}
	}
}

// Unsorted input must tie-break as Python does (it ranks the hand sorted by rank then suit).
func TestRankDiscardsSortsHand(t *testing.T) {
	hand := cards.MustParseHand("KC", "AC", "5S", "KS", "AD", "TD")
	orig := append(cards.Hand(nil), hand...)
	got := ChooseDiscards(hand, true)
	if got[0].ID() != "AD" || got[1].ID() != "AC" {
		t.Errorf("chose %v, want [AD AC]", got)
	}
	if !reflect.DeepEqual(hand, orig) {
		t.Errorf("hand modified: %v", hand)
	}
	if want := ChooseDiscards(hand.Sorted(), true); got != want {
		t.Errorf("unsorted %v != sorted %v", got, want)
	}
}
