package tui

import (
	"fmt"
	"strings"

	"github.com/ericboehlke/cards/internal/cribbage"
)

// A beat is one scoring moment of an engine step ("opp played 5D: fifteen 2"), shown to the user
// one at a time because a single Env.Step plays out the whole opponent turn, the count and the
// next deal at once.
type beat struct {
	kind    string // "play", "last_card", "heels", "hand" or "crib"
	who     string // "you" or "opponent"
	points  int
	text    string   // one line description; card ids are prettified when drawn
	cards   []string // hand or crib counted (hand and crib beats)
	starter string
	detail  string // breakdown of a hand or crib: "fifteens 4 · pairs 2"
}

func whoIdx(who string) int {
	if who == "you" {
		return 0
	}
	return 1
}

func whoName(who string) string {
	if who == "you" {
		return "You"
	}
	return "Opp"
}

func possessive(who string) string {
	if who == "you" {
		return "Your"
	}
	return "Opp's"
}

type reasonPart struct {
	name string
	n    int
}

// joinReasons lists the non-zero parts: "fifteen 2, thirty-one 2".
func joinReasons(sep string, parts ...reasonPart) string {
	var out []string
	for _, p := range parts {
		if p.n != 0 {
			out = append(out, fmt.Sprintf("%s %d", p.name, p.n))
		}
	}
	return strings.Join(out, sep)
}

// buildBeats turns the events of one step into beats and reports whether they include the count
// at the end of a round (the show).
func buildBeats(evs []cribbage.Event) (beats []beat, roundEnd bool) {
	for _, e := range evs {
		switch e.Type {
		case "play":
			if e.Points == 0 {
				continue
			}
			why := joinReasons(", ", reasonPart{"fifteen", e.Fifteen}, reasonPart{"thirty-one", e.Thirtyone},
				reasonPart{"pair", e.Pair}, reasonPart{"run", e.Run})
			beats = append(beats, beat{kind: "play", who: e.Player, points: e.Points,
				text: fmt.Sprintf("%s played %s, count %d: %s (+%d)", whoName(e.Player), e.Card, e.Count, why, e.Points)})
		case "last_card":
			beats = append(beats, beat{kind: "last_card", who: e.Player, points: e.Points,
				text: fmt.Sprintf("%s scored 1 for the last card (+%d)", whoName(e.Player), e.Points)})
		case "his_heels":
			beats = append(beats, beat{kind: "heels", who: e.Player, points: e.Points,
				text: fmt.Sprintf("His heels: %s scored 2 for a jack starter (+%d)", whoName(e.Player), e.Points)})
		case "show":
			roundEnd = true
			kind := "hand"
			if e.What == "crib" {
				kind = "crib"
			}
			detail := joinReasons(" · ", reasonPart{"fifteens", e.Fifteens}, reasonPart{"pairs", e.Pairs},
				reasonPart{"runs", e.Runs}, reasonPart{"flush", e.Flush}, reasonPart{"nobs", e.HisNobs})
			if detail == "" {
				detail = "no points"
			}
			beats = append(beats, beat{kind: kind, who: e.Player, points: e.Points, cards: e.Cards,
				starter: e.Starter, detail: detail})
		}
	}
	return beats, roundEnd
}

// ledgerRow is one counted hand or crib in the round ledger.
type ledgerRow struct {
	label string
	pts   [2]int
}

// ledger is the per-round tally shown while counting, indexed [you, opponent].
type ledger struct {
	peg, last [2]int
	rows      [3]ledgerRow // two hands then the crib
	nhands    int
	closed    bool   // the round has been fully counted; the next scoring starts a new ledger
	carry     [2]int // his heels scored for the next round before this one was cleared
}

func (l *ledger) add(b beat) {
	i := whoIdx(b.who)
	if b.kind == "heels" {
		if l.closed {
			l.carry[i] += b.points
		} else {
			l.peg[i] += b.points
		}
		return
	}
	if l.closed {
		*l = ledger{peg: l.carry}
	}
	switch b.kind {
	case "play":
		l.peg[i] += b.points
	case "last_card":
		l.last[i] += b.points
	case "hand":
		if l.nhands < 2 {
			l.rows[l.nhands] = ledgerRow{label: possessive(b.who) + " hand"}
			l.rows[l.nhands].pts[i] = b.points
			l.nhands++
		}
	case "crib":
		l.rows[2] = ledgerRow{label: possessive(b.who) + " crib"}
		l.rows[2].pts[i] = b.points
		l.closed = true
	}
}

// total is the points each player scored this round so far.
func (l ledger) total() [2]int {
	t := [2]int{l.peg[0] + l.last[0], l.peg[1] + l.last[1]}
	for _, r := range l.rows {
		t[0] += r.pts[0]
		t[1] += r.pts[1]
	}
	return t
}
