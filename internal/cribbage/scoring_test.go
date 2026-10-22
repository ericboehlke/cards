package cribbage

import (
	"encoding/json"
	"os"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

func TestScoringGolden(t *testing.T) {
	data, err := os.ReadFile("../../testdata/golden/scoring.json")
	if err != nil {
		t.Fatal(err)
	}
	var fx struct {
		Cases []struct {
			Name      string   `json:"name"`
			Hand      []string `json:"hand"`
			Starter   string   `json:"starter"`
			IsCrib    bool     `json:"is_crib"`
			Total     int      `json:"total"`
			Breakdown struct {
				Fifteens int `json:"fifteens"`
				Pairs    int `json:"pairs"`
				Runs     int `json:"runs"`
				Flush    int `json:"flush"`
				HisNobs  int `json:"his_nobs"`
			} `json:"breakdown"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(data, &fx); err != nil {
		t.Fatal(err)
	}
	if len(fx.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range fx.Cases {
		hand := cards.MustParseHand(c.Hand...)
		got := ScoreHandBreakdown(hand, cards.MustParseCard(c.Starter), c.IsCrib)
		want := HandScore{c.Breakdown.Fifteens, c.Breakdown.Pairs, c.Breakdown.Runs, c.Breakdown.Flush, c.Breakdown.HisNobs}
		if got != want || got.Total() != c.Total {
			t.Errorf("%s: got %+v (total %d), want %+v (total %d)", c.Name, got, got.Total(), want, c.Total)
		}
	}
}
