package cribbage

import (
	"sort"

	"github.com/ericboehlke/cards/internal/cards"
)

// Discard is one candidate two-card discard from a six-card hand.
type Discard struct {
	Kept      cards.Hand // the four cards kept
	Discarded [2]cards.Card
	HandScore float64 // average score of Kept over all possible starters
	CribScore float64 // Schell table value (negated when the opponent owns the crib)
}

// Total is the ranking key: HandScore + CribScore.
func (d Discard) Total() float64 { return d.HandScore + d.CribScore }

// RankDiscards ranks all 15 two-card discards of a six-card hand, best first.
// The discards are enumerated in hand-position order and sorted stably, so
// ties keep that order of the hand sorted by rank then suit (as Python does); the caller's slice is
// not modified.
func RankDiscards(hand cards.Hand, aiIsDealer bool) []Discard {
	if len(hand) != 6 {
		panic("cribbage: RankDiscards needs a six-card hand")
	}
	hand = hand.Sorted()
	starters := cards.RestOfDeck(hand)
	var out []Discard
	for i := 0; i < 6; i++ {
		for j := i + 1; j < 6; j++ {
			kept := make(cards.Hand, 0, 4)
			for k, c := range hand {
				if k != i && k != j {
					kept = append(kept, c)
				}
			}
			sum := 0
			for _, s := range starters {
				sum += ScoreHand(kept, s, false)
			}
			out = append(out, Discard{
				Kept:      kept,
				Discarded: [2]cards.Card{hand[i], hand[j]},
				HandScore: float64(sum) / float64(len(starters)),
				CribScore: CribDiscardValue(aiIsDealer, hand[i].Rank, hand[j].Rank),
			})
		}
	}
	sort.SliceStable(out, func(a, b int) bool { return out[a].Total() > out[b].Total() })
	return out
}

// ChooseDiscards returns the two cards the greedy AI discards.
func ChooseDiscards(hand cards.Hand, aiIsDealer bool) [2]cards.Card {
	return RankDiscards(hand, aiIsDealer)[0].Discarded
}
