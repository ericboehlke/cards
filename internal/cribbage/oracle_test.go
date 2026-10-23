package cribbage

// A deliberately naive, independent reference implementation of cribbage scoring (a port of
// cards/test/oracle_cribbage.py). It shares nothing with scoring.go or pegging.go: cards are plain
// (rank, suit) pairs and everything is brute force. It exists to cross-check the engine.

import (
	"math/rand"
	"sort"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

type rawCard struct {
	rank int
	suit int
}

func raw(c cards.Card) rawCard { return rawCard{c.Rank, int(c.Suit)} }

func raws(cs []cards.Card) []rawCard {
	out := make([]rawCard, len(cs))
	for i, c := range cs {
		out[i] = raw(c)
	}
	return out
}

func oracleValue(rank int) int {
	if rank > 10 {
		return 10
	}
	return rank
}

// combinations calls f with every subset of cs of the given size.
func combinations(cs []rawCard, size int, f func([]rawCard)) {
	var rec func(start int, cur []rawCard)
	rec = func(start int, cur []rawCard) {
		if len(cur) == size {
			f(cur)
			return
		}
		for i := start; i < len(cs); i++ {
			rec(i+1, append(cur, cs[i]))
		}
	}
	rec(0, nil)
}

// consecutive reports whether the ranks, in any order, form a run of consecutive ranks.
func consecutive(ranks []int) bool {
	s := append([]int(nil), ranks...)
	sort.Ints(s)
	for i := range s {
		if s[i] != s[0]+i {
			return false
		}
	}
	return true
}

func oracleHandScore(hand []rawCard, starter rawCard, isCrib bool) int {
	all := append(append([]rawCard(nil), hand...), starter)
	total := 0
	for size := 2; size <= 5; size++ {
		combinations(all, size, func(c []rawCard) {
			sum := 0
			for _, x := range c {
				sum += oracleValue(x.rank)
			}
			if sum == 15 {
				total += 2
			}
		})
	}
	combinations(all, 2, func(c []rawCard) {
		if c[0].rank == c[1].rank {
			total += 2
		}
	})
	for _, length := range []int{5, 4, 3} {
		runs := 0
		combinations(all, length, func(c []rawCard) {
			ranks := make([]int, len(c))
			for i, x := range c {
				ranks[i] = x.rank
			}
			if consecutive(ranks) {
				runs++
			}
		})
		if runs > 0 {
			total += length * runs
			break
		}
	}
	flush := true
	for _, c := range hand {
		if c.suit != hand[0].suit {
			flush = false
		}
	}
	if flush {
		if starter.suit == hand[0].suit {
			total += 5
		} else if !isCrib {
			total += 4
		}
	}
	for _, c := range hand {
		if c.rank == 11 && c.suit == starter.suit {
			total++
			break
		}
	}
	return total
}

// oraclePegPlayScore is the points for playing next onto the sequence (no go / last card points).
func oraclePegPlayScore(sequence []rawCard, next rawCard) int {
	seq := append(append([]rawCard(nil), sequence...), next)
	total := 0
	count := 0
	for _, c := range seq {
		count += oracleValue(c.rank)
	}
	if count == 15 {
		total += 2
	}
	if count == 31 {
		total += 2
	}
	same := 1
	for same < len(seq) && seq[len(seq)-1-same].rank == next.rank {
		same++
	}
	total += map[int]int{1: 0, 2: 2, 3: 6, 4: 12}[same]
	for length := len(seq); length >= 3; length-- {
		ranks := make([]int, length)
		for i, c := range seq[len(seq)-length:] {
			ranks[i] = c.rank
		}
		if consecutive(ranks) {
			total += length
			break
		}
	}
	return total
}

func shuffled(rng *rand.Rand) cards.Hand {
	d := cards.Deck()
	rng.Shuffle(len(d), func(i, j int) { d[i], d[j] = d[j], d[i] })
	return d
}

func TestOracleKnownHands(t *testing.T) {
	perfect := []rawCard{raw(cards.MustParseCard("5H")), raw(cards.MustParseCard("5S")),
		raw(cards.MustParseCard("5C")), raw(cards.MustParseCard("JD"))}
	if got := oracleHandScore(perfect, raw(cards.MustParseCard("5D")), false); got != 29 {
		t.Fatalf("oracle perfect hand = %d, want 29", got)
	}
}

func TestHandScoringAgainstOracle(t *testing.T) {
	check := func(hand cards.Hand, starter cards.Card, isCrib bool) {
		t.Helper()
		want := oracleHandScore(raws(hand), raw(starter), isCrib)
		if got := ScoreHand(hand, starter, isCrib); got != want {
			t.Fatalf("%v + %v crib=%v: engine %d, oracle %d", hand.IDs(), starter, isCrib, got, want)
		}
		if got := ScoreHandBreakdown(hand, starter, isCrib).Total(); got != want {
			t.Fatalf("%v + %v crib=%v: breakdown total %d, oracle %d", hand.IDs(), starter, isCrib, got, want)
		}
	}
	rng := rand.New(rand.NewSource(1))
	for i := 0; i < 20000; i++ {
		d := shuffled(rng)
		check(d[:4], d[4], i%2 == 0)
	}
	// Bias toward flush and run edge cases: all-one-suit hands and hands made of 3-6.
	for i := 0; i < 20000; i++ {
		d := shuffled(rng)
		var pool cards.Hand
		for _, c := range d {
			if (i%2 == 0 && c.Suit == cards.Suit(rng.Intn(4))) || (i%2 == 1 && c.Rank >= 3 && c.Rank <= 6) {
				pool = append(pool, c)
			}
		}
		if len(pool) < 4 {
			continue
		}
		hand := append(cards.Hand(nil), pool[:4]...)
		var starter cards.Card
		for _, c := range d {
			if !hand.Contains(c) {
				starter = c
				break
			}
		}
		check(hand, starter, i%3 == 0)
	}
}

func TestPeggingScoringAgainstOracle(t *testing.T) {
	rng := rand.New(rand.NewSource(3))
	for i := 0; i < 5000; i++ {
		d := shuffled(rng)[:16]
		cip := NewCardsInPlay()
		var seq []rawCard
		count := 0
		for _, c := range d {
			if count+c.Value() > 31 {
				continue
			}
			want := oraclePegPlayScore(seq, raw(c))
			p := Player(len(seq) % 2)
			scores, err := cip.Play(p, c)
			if err != nil {
				t.Fatal(err)
			}
			if got := scores[p]; got.Total != want ||
				got.Total != got.Fifteen+got.Thirtyone+got.Pair+got.Run {
				t.Fatalf("%v then %v: engine %+v, oracle %d", seq, raw(c), got, want)
			}
			seq = append(seq, raw(c))
			count += c.Value()
			if count == 31 {
				break
			}
		}
	}
}
