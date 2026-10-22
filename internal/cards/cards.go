// Package cards provides playing cards, hands and plain-text card ids
// (e.g. "5H", "TS", "AC") matching the Python cards package.
package cards

import (
	"fmt"
	"sort"
	"strings"
)

// Suit is a card suit. The order H D C S is the canonical deck/sort order.
type Suit int

const (
	Hearts Suit = iota
	Diamonds
	Clubs
	Spades
)

// Rank values: ace is low (1) and king is 13.
const (
	Ace   = 1
	Jack  = 11
	Queen = 12
	King  = 13
)

const (
	rankChars = "A23456789TJQK"
	suitChars = "HDCS"
)

// Suits lists all suits in canonical order.
var Suits = [4]Suit{Hearts, Diamonds, Clubs, Spades}

// Char returns the id character of the suit (H, D, C or S).
func (s Suit) Char() byte { return suitChars[s] }

// String returns the suit name, e.g. "hearts".
func (s Suit) String() string {
	return [...]string{"hearts", "diamonds", "clubs", "spades"}[s]
}

// IsRed reports whether the suit is hearts or diamonds.
func (s Suit) IsRed() bool { return s == Hearts || s == Diamonds }

// Card is a playing card. Rank is 1 (ace) to 13 (king). Cards are comparable
// and may be used as map keys.
type Card struct {
	Rank int
	Suit Suit
}

// New returns a card; it panics if rank or suit is out of range.
func New(suit Suit, rank int) Card {
	if rank < 1 || rank > 13 || suit < Hearts || suit > Spades {
		panic(fmt.Sprintf("cards: invalid card rank=%d suit=%d", rank, suit))
	}
	return Card{Rank: rank, Suit: suit}
}

// Value is the counting value: ace 1, 2-10 face value, J/Q/K 10.
func (c Card) Value() int {
	if c.Rank > 10 {
		return 10
	}
	return c.Rank
}

// ID returns the plain-text id: rank char then suit char, e.g. "5H", "TS".
func (c Card) ID() string {
	return string([]byte{rankChars[c.Rank-1], c.Suit.Char()})
}

// String is the same as ID.
func (c Card) String() string { return c.ID() }

// IsRed reports whether the card is a heart or diamond.
func (c Card) IsRed() bool { return c.Suit.IsRed() }

// Less orders cards by rank, then suit (H D C S).
func (c Card) Less(o Card) bool {
	if c.Rank != o.Rank {
		return c.Rank < o.Rank
	}
	return c.Suit < o.Suit
}

// ParseCard parses a card id. It trims whitespace, uppercases, and accepts a
// leading "10" as T ("10h" -> "TH"). It returns an error if invalid.
func ParseCard(s string) (Card, error) {
	t := strings.ToUpper(strings.TrimSpace(s))
	if strings.HasPrefix(t, "10") {
		t = "T" + t[2:]
	}
	if len(t) == 2 {
		r := strings.IndexByte(rankChars, t[0])
		su := strings.IndexByte(suitChars, t[1])
		if r >= 0 && su >= 0 {
			return Card{Rank: r + 1, Suit: Suit(su)}, nil
		}
	}
	return Card{}, fmt.Errorf("not a card id: %q (expected like '5H', 'TS', 'AC')", s)
}

// MustParseCard is ParseCard that panics on error (for tests and constants).
func MustParseCard(s string) Card {
	c, err := ParseCard(s)
	if err != nil {
		panic(err)
	}
	return c
}

// Hand is an ordered list of cards.
type Hand []Card

// ParseHand parses a list of card ids, preserving order.
func ParseHand(ids []string) (Hand, error) {
	h := make(Hand, 0, len(ids))
	for _, id := range ids {
		c, err := ParseCard(id)
		if err != nil {
			return nil, err
		}
		h = append(h, c)
	}
	return h, nil
}

// MustParseHand is ParseHand that panics on error.
func MustParseHand(ids ...string) Hand {
	h, err := ParseHand(ids)
	if err != nil {
		panic(err)
	}
	return h
}

// IDs returns the card ids in order.
func (h Hand) IDs() []string {
	out := make([]string, len(h))
	for i, c := range h {
		out[i] = c.ID()
	}
	return out
}

// Sorted returns a copy sorted by rank, then suit (H D C S).
func (h Hand) Sorted() Hand {
	out := append(Hand(nil), h...)
	sort.SliceStable(out, func(i, j int) bool { return out[i].Less(out[j]) })
	return out
}

// Contains reports whether the hand holds c.
func (h Hand) Contains(c Card) bool { return h.Index(c) >= 0 }

// Index returns the position of c in the hand, or -1.
func (h Hand) Index(c Card) int {
	for i, x := range h {
		if x == c {
			return i
		}
	}
	return -1
}

// Remove returns a copy without the first occurrence of c, and whether it was found.
func (h Hand) Remove(c Card) (Hand, bool) {
	i := h.Index(c)
	if i < 0 {
		return h, false
	}
	out := make(Hand, 0, len(h)-1)
	out = append(out, h[:i]...)
	return append(out, h[i+1:]...), true
}

// Total is the sum of counting values.
func (h Hand) Total() int {
	n := 0
	for _, c := range h {
		n += c.Value()
	}
	return n
}

// Deck returns a new 52-card deck in canonical order (suits H D C S, ranks A..K).
func Deck() Hand {
	d := make(Hand, 0, 52)
	for _, s := range Suits {
		for r := 1; r <= 13; r++ {
			d = append(d, Card{Rank: r, Suit: s})
		}
	}
	return d
}

// RestOfDeck returns the deck cards not in h, in canonical deck order.
func RestOfDeck(h Hand) Hand {
	var out Hand
	for _, c := range Deck() {
		if !h.Contains(c) {
			out = append(out, c)
		}
	}
	return out
}
