package cribbage

import (
	"errors"
	"sort"

	"github.com/ericboehlke/cards/internal/cards"
)

// Player identifies one of the two players.
type Player int

// The two players.
const (
	Player1 Player = iota
	Player2
)

// Other returns the other player.
func (p Player) Other() Player {
	if p == Player2 {
		return Player1
	}
	return Player2
}

// MaxCount is the pegging count limit.
const MaxCount = 31

// ErrExceeds31 is returned when a play would take the count over 31.
var ErrExceeds31 = errors.New("cannot play card that would exceed 31")

// PlayedCard is a card together with the player who played it.
type PlayedCard struct {
	Player Player
	Card   cards.Card
}

// PeggingScore is the points earned by one pegging action.
type PeggingScore struct {
	Fifteen, Thirtyone, Go, Pair, Run, Total int
}

// PegScores holds the score of each player for one action, indexed by Player.
type PegScores [2]PeggingScore

// CardsInPlay tracks the pegging sequence and every card played this round.
type CardsInPlay struct {
	played   []PlayedCard
	sequence []PlayedCard
	points   [2]int
	gos      [2]bool
}

// NewCardsInPlay returns an empty table.
func NewCardsInPlay() *CardsInPlay { return &CardsInPlay{} }

// Count is the current play count.
func (c *CardsInPlay) Count() int {
	n := 0
	for _, p := range c.sequence {
		n += p.Card.Value()
	}
	return n
}

// Sequence returns the cards played since the count last reset.
func (c *CardsInPlay) Sequence() []PlayedCard { return append([]PlayedCard(nil), c.sequence...) }

// PlayedCards returns every card played this round.
func (c *CardsInPlay) PlayedCards() []PlayedCard { return append([]PlayedCard(nil), c.played...) }

// LastPlayer returns the player of the most recent card this round, if any.
func (c *CardsInPlay) LastPlayer() (Player, bool) {
	if len(c.played) == 0 {
		return Player1, false
	}
	return c.played[len(c.played)-1].Player, true
}

// Points returns the pegging points a player has earned this round.
func (c *CardsInPlay) Points(p Player) int { return c.points[p] }

// CanPlay reports whether card can be played without exceeding 31.
func (c *CardsInPlay) CanPlay(card cards.Card) bool {
	return c.Count()+card.Value() <= MaxCount
}

// HasSaidGo reports whether p has said go in the current sequence.
func (c *CardsInPlay) HasSaidGo(p Player) bool { return c.gos[p] }

// EndSequence resets the count and go flags.
func (c *CardsInPlay) EndSequence() {
	c.sequence = nil
	c.gos = [2]bool{}
}

// Play plays a card and returns the points scored by each player.
func (c *CardsInPlay) Play(p Player, card cards.Card) (PegScores, error) {
	score, ok := c.ScorePlay(card)
	if !ok {
		return PegScores{}, ErrExceeds31
	}
	pc := PlayedCard{p, card}
	c.played = append(c.played, pc)
	c.sequence = append(c.sequence, pc)
	c.points[p] += score.Total
	if c.Count() == MaxCount {
		c.EndSequence()
	}
	var out PegScores
	out[p] = score
	return out, nil
}

// Go says go for p. The first go scores nothing; when the opponent has also
// said go, the player of the last card scores one and the sequence resets.
func (c *CardsInPlay) Go(p Player) PegScores {
	var out PegScores
	if len(c.sequence) == 0 {
		return out
	}
	if c.gos[p.Other()] {
		last := c.sequence[len(c.sequence)-1].Player
		out[last] = PeggingScore{Go: 1, Total: 1}
		c.points[last]++
		c.EndSequence()
	} else {
		c.gos[p] = true
	}
	return out
}

// ReturnCards returns the cards played by p this round.
func (c *CardsInPlay) ReturnCards(p Player) cards.Hand {
	var out cards.Hand
	for _, pc := range c.played {
		if pc.Player == p {
			out = append(out, pc.Card)
		}
	}
	return out
}

// ScorePlay scores playing card on the current sequence. ok is false if the
// play would exceed 31.
func (c *CardsInPlay) ScorePlay(card cards.Card) (score PeggingScore, ok bool) {
	newCount := c.Count() + card.Value()
	if newCount > MaxCount {
		return PeggingScore{}, false
	}
	seq := make([]cards.Card, 0, len(c.sequence)+1)
	for _, pc := range c.sequence {
		seq = append(seq, pc.Card)
	}
	seq = append(seq, card)
	if newCount == 15 {
		score.Fifteen = 2
	}
	if newCount == MaxCount {
		score.Thirtyone = 2
	}
	same := 1
	for same < len(seq) && seq[len(seq)-1-same].Rank == card.Rank {
		same++
	}
	score.Pair = [...]int{0, 0, 2, 6, 12}[same]
	for length := len(seq); length >= 3; length-- {
		nums := make([]int, length)
		for i, x := range seq[len(seq)-length:] {
			nums[i] = x.Rank
		}
		sort.Ints(nums)
		consecutive := true
		for i := range nums {
			if nums[i] != nums[0]+i {
				consecutive = false
				break
			}
		}
		if consecutive {
			score.Run = length
			break
		}
	}
	score.Total = score.Fifteen + score.Thirtyone + score.Pair + score.Run
	return score, true
}

// PlayAI is the greedy pegging AI: the playable card with the highest score,
// earliest in hand on ties. ok is false if no card can be played.
func PlayAI(hand cards.Hand, c *CardsInPlay) (card cards.Card, ok bool) {
	best := -1
	for _, h := range hand {
		if !c.CanPlay(h) {
			continue
		}
		s, _ := c.ScorePlay(h)
		if s.Total > best {
			best, card, ok = s.Total, h, true
		}
	}
	return card, ok
}
