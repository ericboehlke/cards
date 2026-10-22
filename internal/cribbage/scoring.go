package cribbage

import (
	"sort"

	"github.com/ericboehlke/cards/internal/cards"
)

// HandScore is the points per category for a cribbage hand.
type HandScore struct {
	Fifteens int
	Pairs    int
	Runs     int
	Flush    int
	HisNobs  int
}

// Total is the sum of all categories.
func (s HandScore) Total() int {
	return s.Fifteens + s.Pairs + s.Runs + s.Flush + s.HisNobs
}

// ScoreHandBreakdown scores a four-card hand with the starter. If isCrib is
// true a flush needs all five cards to match; otherwise a four-card flush
// also scores.
func ScoreHandBreakdown(hand cards.Hand, starter cards.Card, isCrib bool) HandScore {
	all := make([]cards.Card, 0, len(hand)+1)
	all = append(all, hand...)
	all = append(all, starter)
	return HandScore{
		Fifteens: scoringFifteens(all),
		Pairs:    scoringPairs(all),
		Runs:     scoringRuns(all),
		Flush:    scoringFlush(hand, starter, isCrib),
		HisNobs:  scoringNobs(hand, starter),
	}
}

// ScoreHand returns the total score of the hand with the starter.
func ScoreHand(hand cards.Hand, starter cards.Card, isCrib bool) int {
	return ScoreHandBreakdown(hand, starter, isCrib).Total()
}

func scoringFifteens(all []cards.Card) int {
	n := 0
	for mask := 1; mask < 1<<len(all); mask++ {
		sum, cnt := 0, 0
		for i, c := range all {
			if mask&(1<<i) != 0 {
				sum += c.Value()
				cnt++
			}
		}
		if cnt >= 2 && sum == 15 {
			n++
		}
	}
	return 2 * n
}

func scoringPairs(all []cards.Card) int {
	n := 0
	for i := range all {
		for j := i + 1; j < len(all); j++ {
			if all[i].Rank == all[j].Rank {
				n++
			}
		}
	}
	return 2 * n
}

func scoringFlush(hand cards.Hand, starter cards.Card, isCrib bool) int {
	if len(hand) == 0 {
		return 0
	}
	same := true
	for _, c := range hand {
		if c.Suit != hand[0].Suit {
			same = false
		}
	}
	if !same {
		return 0
	}
	if hand[0].Suit == starter.Suit {
		return 5
	}
	if !isCrib {
		return 4
	}
	return 0
}

func scoringNobs(hand cards.Hand, starter cards.Card) int {
	for _, c := range hand {
		if c.Rank == cards.Jack && c.Suit == starter.Suit {
			return 1
		}
	}
	return 0
}

// scoringRuns mirrors the Python: sort by rank, take the first group of
// consecutive-or-equal ranks with 3+ distinct ranks; score length * product
// of rank multiplicities.
func scoringRuns(all []cards.Card) int {
	ranks := make([]int, len(all))
	for i, c := range all {
		ranks[i] = c.Rank
	}
	sort.Ints(ranks)
	score := func(run []int) int {
		distinct, mult := 0, 1
		for i := 0; i < len(run); {
			j := i
			for j < len(run) && run[j] == run[i] {
				j++
			}
			distinct++
			mult *= j - i
			i = j
		}
		if distinct < 3 {
			return 0
		}
		return distinct * mult
	}
	start := 0
	for i := 1; i < len(ranks); i++ {
		if ranks[i] != ranks[i-1] && ranks[i] != ranks[i-1]+1 {
			if s := score(ranks[start:i]); s > 0 {
				return s
			}
			start = i
		}
	}
	return score(ranks[start:])
}
