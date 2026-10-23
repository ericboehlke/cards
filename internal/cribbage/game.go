package cribbage

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/ericboehlke/cards/internal/cards"
)

// WinningScore is the score that ends the game.
const WinningScore = 121

// PlayState is the phase of a game (Python PlayState).
type PlayState int

const (
	StateReady PlayState = iota - 1
	StateDiscard
	StatePegging
	StateShow
	StateComplete
)

// Name returns the Python enum name, which appears in some error messages.
func (s PlayState) Name() string {
	switch s {
	case StateReady:
		return "READY"
	case StateDiscard:
		return "DISCARD"
	case StatePegging:
		return "PEGGING"
	case StateShow:
		return "SHOW"
	}
	return "COMPLETE"
}

// Name returns the Python enum name ("PLAYER1"/"PLAYER2").
func (p Player) Name() string {
	if p == Player2 {
		return "PLAYER2"
	}
	return "PLAYER1"
}

// IllegalAction is an action that is not allowed right now. Code is a stable machine readable reason.
type IllegalAction struct {
	Code    string
	Message string
}

func (e *IllegalAction) Error() string { return e.Message }

func illegal(code, format string, args ...any) *IllegalAction {
	return &IllegalAction{Code: code, Message: fmt.Sprintf(format, args...)}
}

// ActionType is "discard" (2 cards) or "play" (1 card).
const (
	ActionDiscard = "discard"
	ActionPlay    = "play"
)

// Action is a move: a discard of two cards or the play of one.
type Action struct {
	Type  string
	Cards []cards.Card
}

// Event is a plain description of something that happened. Which fields are meaningful depends on
// Type; MarshalJSON emits exactly the keys the Python events carry. Player, Dealer and Winner hold
// "PLAYER1"/"PLAYER2" from Game and "you"/"opponent" from Env.
type Event struct {
	Type   string
	Player string
	Dealer string
	Winner string
	Card   string // play, starter
	Count  int
	// play
	Fifteen, Thirtyone, Pair, Run int
	Points                        int
	NoCards                       bool // go
	// show
	What                                  string
	Cards                                 []string
	Starter                               string
	Fifteens, Pairs, Runs, Flush, HisNobs int
	Text                                  string // set by Env; omitted from JSON when empty
}

// MarshalJSON emits the Python event shape for the event's type.
func (e Event) MarshalJSON() ([]byte, error) {
	m := map[string]any{"type": e.Type}
	switch e.Type {
	case "deal":
		m["dealer"] = e.Dealer
	case "discard":
		m["player"] = e.Player
	case "starter":
		m["card"] = e.Card
	case "his_heels", "last_card":
		m["player"] = e.Player
		m["points"] = e.Points
	case "play":
		m["player"], m["card"], m["count"] = e.Player, e.Card, e.Count
		m["fifteen"], m["thirtyone"], m["pair"], m["run"] = e.Fifteen, e.Thirtyone, e.Pair, e.Run
		m["points"] = e.Points
	case "go":
		m["player"], m["no_cards"] = e.Player, e.NoCards
	case "show":
		m["player"], m["what"], m["cards"], m["starter"] = e.Player, e.What, e.Cards, e.Starter
		m["fifteens"], m["pairs"], m["runs"], m["flush"], m["his_nobs"] = e.Fifteens, e.Pairs, e.Runs, e.Flush, e.HisNobs
		m["points"] = e.Points
	case "game_over":
		m["winner"] = e.Winner
	}
	if e.Text != "" {
		m["text"] = e.Text
	}
	return json.Marshal(m)
}

// Describe is a one line plain-text description of an event; names relabels PLAYER1/PLAYER2.
func Describe(e Event, names map[string]string) string {
	nm := func(s string) string {
		if v, ok := names[s]; ok {
			return v
		}
		return s
	}
	who := nm(e.Player)
	switch e.Type {
	case "deal":
		return fmt.Sprintf("New round. Dealer (owns the crib): %s.", nm(e.Dealer))
	case "discard":
		return who + " put two cards in the crib."
	case "starter":
		return fmt.Sprintf("Starter card turned up: %s.", e.Card)
	case "his_heels":
		return fmt.Sprintf("His heels: %s scored 2 for a jack starter.", who)
	case "play":
		var parts []string
		for _, p := range []struct {
			name string
			n    int
		}{{"fifteen", e.Fifteen}, {"thirty-one", e.Thirtyone}, {"pair", e.Pair}, {"run", e.Run}} {
			if p.n != 0 {
				parts = append(parts, fmt.Sprintf("%s %d", p.name, p.n))
			}
		}
		scored := ""
		if e.Points != 0 {
			scored = fmt.Sprintf(", scored %d (%s)", e.Points, strings.Join(parts, ", "))
		}
		return fmt.Sprintf("%s played %s, count %d%s.", who, e.Card, e.Count, scored)
	case "go":
		if e.NoCards {
			return who + " has no cards left (go)."
		}
		return who + " said go (cannot play without going over 31)."
	case "last_card":
		return who + " scored 1 for the last card."
	case "show":
		var parts []string
		for _, p := range []struct {
			name string
			n    int
		}{{"fifteens", e.Fifteens}, {"pairs", e.Pairs}, {"runs", e.Runs}, {"flush", e.Flush}, {"his nobs", e.HisNobs}} {
			if p.n != 0 {
				parts = append(parts, fmt.Sprintf("%s %d", p.name, p.n))
			}
		}
		detail := ""
		if len(parts) > 0 {
			detail = " (" + strings.Join(parts, ", ") + ")"
		}
		return fmt.Sprintf("Show: %s %s %s with starter %s scored %d%s.",
			who, e.What, strings.Join(e.Cards, " "), e.Starter, e.Points, detail)
	case "decks_exhausted":
		return "The supplied decks ran out; the game is over with no winner."
	case "game_over":
		return fmt.Sprintf("Game over: %s won.", nm(e.Winner))
	}
	return e.Type
}

// Game is the cribbage state machine. Ask ToAct/LegalActions who may do what, then Apply an action.
// It is driven entirely by the injected decks, so it is deterministic.
type Game struct {
	decks     []cards.Hand
	hands     [2]cards.Hand
	played    *CardsInPlay
	points    [2]int
	crib      cards.Hand
	starter   cards.Card
	hasStart  bool
	dealer    Player
	deals     int
	discarded [2]bool
	turn      Player
	winner    Player
	hasWinner bool
	state     PlayState
}

// NewGame creates a game. decks holds one full 52-card order per deal (deal N uses decks[N]:
// indexes 0-5 go to Player1, 6-11 to Player2, 12 is the starter). Dealing past the last deck
// fails with IllegalAction code "decks_exhausted". firstDealer deals the first round; the deal
// then alternates.
func NewGame(decks []cards.Hand, firstDealer Player) (*Game, error) {
	for i, d := range decks {
		seen := map[cards.Card]bool{}
		for _, c := range d {
			seen[c] = true
		}
		if len(d) != 52 || len(seen) != 52 {
			return nil, fmt.Errorf("deck %d must be a permutation of all 52 cards", i)
		}
	}
	g := &Game{dealer: firstDealer, state: StateReady, played: NewCardsInPlay()}
	for _, d := range decks {
		g.decks = append(g.decks, append(cards.Hand(nil), d...))
	}
	return g, nil
}

func (g *Game) State() PlayState            { return g.state }
func (g *Game) Points(p Player) int         { return g.points[p] }
func (g *Game) Hand(p Player) cards.Hand    { return append(cards.Hand(nil), g.hands[p]...) }
func (g *Game) Dealer() Player              { return g.dealer }
func (g *Game) CardsInPlay() *CardsInPlay   { return g.played }
func (g *Game) Crib() cards.Hand            { return append(cards.Hand(nil), g.crib...) }
func (g *Game) Winner() (Player, bool)      { return g.winner, g.hasWinner }
func (g *Game) Starter() (cards.Card, bool) { return g.starter, g.hasStart }

// Turn is the player who must play a card, during pegging.
func (g *Game) Turn() (Player, bool) { return g.turn, g.state == StatePegging }

// ToAct lists the players who currently have a legal action.
func (g *Game) ToAct() []Player {
	var out []Player
	for _, p := range []Player{Player1, Player2} {
		if len(g.LegalActions(p)) > 0 {
			out = append(out, p)
		}
	}
	return out
}

// LegalActions lists every action the player may take right now (discards in hand-order combinations).
func (g *Game) LegalActions(p Player) []Action {
	var out []Action
	switch {
	case g.state == StateDiscard && !g.discarded[p]:
		h := g.hands[p]
		for i := 0; i < len(h); i++ {
			for j := i + 1; j < len(h); j++ {
				out = append(out, Action{ActionDiscard, []cards.Card{h[i], h[j]}})
			}
		}
	case g.state == StatePegging && p == g.turn:
		for _, c := range g.hands[p] {
			if g.played.CanPlay(c) {
				out = append(out, Action{ActionPlay, []cards.Card{c}})
			}
		}
	}
	return out
}

// Deal starts a new round; the deal passes to the other player after the first round.
func (g *Game) Deal() ([]Event, error) {
	if g.state != StateReady && g.state != StateShow {
		return nil, illegal("wrong_phase", "Cannot deal during %s", g.state.Name())
	}
	if g.deals >= len(g.decks) {
		return nil, illegal("decks_exhausted", "Only %d decks were supplied.", len(g.decks))
	}
	if g.deals > 0 {
		g.dealer = g.dealer.Other()
	}
	deck := g.decks[g.deals]
	g.deals++
	g.hands[Player1] = cards.Hand(deck[:6]).Sorted()
	g.hands[Player2] = cards.Hand(deck[6:12]).Sorted()
	g.played = NewCardsInPlay()
	g.crib = nil
	g.starter, g.hasStart = deck[12], true
	g.discarded = [2]bool{}
	g.state = StateDiscard
	return []Event{{Type: "deal", Dealer: g.dealer.Name()}}, nil
}

// Apply applies an action, returning the events it caused, or an *IllegalAction (changing nothing).
func (g *Game) Apply(p Player, a Action) ([]Event, error) {
	if err := g.validate(p, a); err != nil {
		return nil, err
	}
	var events []Event
	var over bool
	if a.Type == ActionDiscard {
		over = g.discard(p, a.Cards, &events)
	} else {
		over = g.play(p, a.Cards[0], &events)
	}
	if over {
		g.state = StateComplete
		events = append(events, Event{Type: "game_over", Winner: g.winner.Name()})
	}
	return events, nil
}

func (g *Game) validate(p Player, a Action) error {
	if g.state == StateComplete {
		return illegal("game_over", "The game is over.")
	}
	if a.Type != ActionDiscard && a.Type != ActionPlay {
		return illegal("unknown_action", "Unknown action type %q", a.Type)
	}
	if a.Type == ActionDiscard {
		if g.state != StateDiscard {
			return illegal("wrong_phase", "Cannot discard during %s", g.state.Name())
		}
		if g.discarded[p] {
			return illegal("already_discarded", "You already discarded to the crib.")
		}
		if len(a.Cards) != 2 || a.Cards[0] == a.Cards[1] {
			return illegal("bad_discard", "Discard exactly two different cards.")
		}
	} else {
		if g.state != StatePegging {
			return illegal("wrong_phase", "Cannot play a card during %s", g.state.Name())
		}
		if p != g.turn {
			return illegal("not_your_turn", "It is %s's turn.", g.turn.Name())
		}
		if len(a.Cards) != 1 {
			return illegal("bad_play", "Play exactly one card.")
		}
	}
	for _, c := range a.Cards {
		if !g.hands[p].Contains(c) {
			return illegal("card_not_in_hand", "%s is not in your hand.", c.ID())
		}
	}
	if a.Type == ActionPlay && !g.played.CanPlay(a.Cards[0]) {
		return illegal("exceeds_31", "Playing %s would take the count over 31 (count is %d).",
			a.Cards[0].ID(), g.played.Count())
	}
	return nil
}

// addPoints appends the event with its points and scores them; it reports whether the player
// reached the winning score (the game is then over).
func (g *Game) addPoints(p Player, points int, e Event, events *[]Event) bool {
	e.Points = points
	*events = append(*events, e)
	g.points[p] += points
	if g.points[p] >= WinningScore {
		g.winner, g.hasWinner = p, true
		return true
	}
	return false
}

func (g *Game) discard(p Player, cs []cards.Card, events *[]Event) bool {
	for _, c := range cs {
		g.hands[p], _ = g.hands[p].Remove(c)
		g.crib = append(g.crib, c)
	}
	g.crib = g.crib.Sorted()
	g.discarded[p] = true
	*events = append(*events, Event{Type: "discard", Player: p.Name()})
	if !(g.discarded[Player1] && g.discarded[Player2]) {
		return false
	}
	g.state = StatePegging
	*events = append(*events, Event{Type: "starter", Card: g.starter.ID()})
	if g.starter.Rank == cards.Jack {
		if g.addPoints(g.dealer, 2, Event{Type: "his_heels", Player: g.dealer.Name()}, events) {
			return true
		}
	}
	return g.settle(events)
}

func (g *Game) play(p Player, c cards.Card, events *[]Event) bool {
	g.hands[p], _ = g.hands[p].Remove(c)
	before := g.played.Count()
	scores, _ := g.played.Play(p, c)
	s := scores[p]
	e := Event{Type: "play", Player: p.Name(), Card: c.ID(), Count: before + c.Value(),
		Fifteen: s.Fifteen, Thirtyone: s.Thirtyone, Pair: s.Pair, Run: s.Run}
	if g.addPoints(p, s.Total, e, events) {
		return true
	}
	return g.settle(events)
}

func (g *Game) canPlayAny(p Player) bool {
	for _, c := range g.hands[p] {
		if g.played.CanPlay(c) {
			return true
		}
	}
	return false
}

// settle decides who plays next, saying go for anyone who cannot, awarding the last card, and
// moving to the show once every card has been played. It reports whether the game ended.
func (g *Game) settle(events *[]Event) bool {
	cip := g.played
	for {
		last, ok := cip.LastPlayer()
		if !ok {
			last = g.dealer
		}
		for _, p := range []Player{last.Other(), last} {
			if g.canPlayAny(p) {
				g.turn = p
				return false
			}
			if len(cip.sequence) > 0 && !cip.HasSaidGo(p) {
				*events = append(*events, Event{Type: "go", Player: p.Name(), NoCards: len(g.hands[p]) == 0})
			}
			result := cip.Go(p)
			for _, scorer := range []Player{p, p.Other()} {
				if t := result[scorer].Total; t != 0 {
					if g.addPoints(scorer, t, Event{Type: "last_card", Player: scorer.Name()}, events) {
						return true
					}
				}
			}
		}
		if len(g.hands[Player1]) == 0 && len(g.hands[Player2]) == 0 {
			return g.show(events)
		}
	}
}

// show counts the hands (non-dealer first) and the crib.
func (g *Game) show(events *[]Event) bool {
	g.state = StateShow
	nd := g.dealer.Other()
	for _, p := range []Player{nd, g.dealer} {
		g.hands[p] = g.played.ReturnCards(p).Sorted()
	}
	g.played = NewCardsInPlay()
	for _, s := range []struct {
		p    Player
		what string
		h    cards.Hand
		crib bool
	}{{nd, "hand", g.hands[nd], false}, {g.dealer, "hand", g.hands[g.dealer], false}, {g.dealer, "crib", g.crib, true}} {
		b := ScoreHandBreakdown(s.h, g.starter, s.crib)
		e := Event{Type: "show", Player: s.p.Name(), What: s.what, Cards: s.h.IDs(), Starter: g.starter.ID(),
			Fifteens: b.Fifteens, Pairs: b.Pairs, Runs: b.Runs, Flush: b.Flush, HisNobs: b.HisNobs}
		if g.addPoints(s.p, b.Total(), e, events) {
			return true
		}
	}
	return false
}

// ---- Env: the JSON friendly API against the greedy opponent --------------------------------------

// Agent and Opponent are the two seats in an Env; the agent is "you".
const (
	Agent    = Player1
	Opponent = Player2
)

// Names relabels PLAYER1/PLAYER2 for Env events.
var Names = map[string]string{"PLAYER1": "you", "PLAYER2": "opponent"}

// ActionInput is the JSON form of an action: {"type":"discard","cards":["5H","KS"]} or
// {"type":"play","card":"7D"} ("cards":["7D"] also works for a play).
type ActionInput struct {
	Type  string   `json:"type"`
	Card  *string  `json:"card,omitempty"` // nil when absent; "" is present but invalid
	Cards []string `json:"cards,omitempty"`
}

// ParseAction converts an ActionInput to an Action; failures are IllegalAction "bad_action".
func ParseAction(in ActionInput) (Action, error) {
	ids := in.Cards
	switch in.Type {
	case ActionDiscard:
		if in.Cards == nil {
			return Action{}, illegal("bad_action", "Malformed action: missing cards")
		}
	case ActionPlay:
		if in.Card != nil {
			ids = []string{*in.Card}
		} else if in.Cards == nil {
			return Action{}, illegal("bad_action", "Malformed action: missing card")
		}
	default:
		return Action{}, illegal("bad_action", "Unknown action type %q; use 'discard' or 'play'.", in.Type)
	}
	h, err := cards.ParseHand(ids)
	if err != nil {
		return Action{}, illegal("bad_action", "Malformed action: %v", err)
	}
	return Action{in.Type, h}, nil
}

func strPtr(s string) *string { return &s }

func actionToInput(a Action) ActionInput {
	if a.Type == ActionPlay {
		return ActionInput{Type: ActionPlay, Card: strPtr(a.Cards[0].ID())}
	}
	return ActionInput{Type: ActionDiscard, Cards: cards.Hand(a.Cards).IDs()}
}

// SeqCard is a card in the pegging sequence with who played it.
type SeqCard struct {
	Player string `json:"player"`
	Card   string `json:"card"`
}

// Observation is what the agent sees.
type Observation struct {
	Phase               string        `json:"phase"`
	YouScore            int           `json:"you_score"`
	OpponentScore       int           `json:"opponent_score"`
	TargetScore         int           `json:"target_score"`
	Dealer              string        `json:"dealer"`
	YourHand            []string      `json:"your_hand"`
	OpponentCardsInHand int           `json:"opponent_cards_in_hand"`
	CribSize            int           `json:"crib_size"`
	Starter             *string       `json:"starter"`
	Count               int           `json:"count"`
	Sequence            []SeqCard     `json:"sequence"`
	PlayedThisRound     []SeqCard     `json:"played_this_round"`
	LegalActions        []ActionInput `json:"legal_actions"`
	Winner              *string       `json:"winner"`
	Prompt              string        `json:"prompt"`
}

// ErrorInfo is the error of a rejected step.
type ErrorInfo struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// Result is what Reset and Step return.
type Result struct {
	OK          bool        `json:"ok"`
	Error       *ErrorInfo  `json:"error"`
	Events      []Event     `json:"events"`
	Observation Observation `json:"observation"`
	Done        bool        `json:"done"`
}

// Env plays cribbage as "you" against the deterministic greedy opponent (CribbageEnv with
// opponent="greedy"). Opponent turns, the show and dealing the next round happen automatically,
// so after every call it is the agent's move or the game is over.
type Env struct {
	decks       []cards.Hand
	firstDealer Player
	game        *Game
	exhausted   bool
}

// NewEnv creates an Env and resets it. firstDealer is "you" or "opponent".
func NewEnv(decks []cards.Hand, firstDealer string) (*Env, Result, error) {
	if len(decks) == 0 {
		return nil, Result{}, fmt.Errorf("decks must contain at least one deck")
	}
	e := &Env{}
	for _, d := range decks {
		e.decks = append(e.decks, append(cards.Hand(nil), d...))
	}
	switch firstDealer {
	case "you":
		e.firstDealer = Agent
	case "opponent":
		e.firstDealer = Opponent
	default:
		return nil, Result{}, fmt.Errorf(`first_dealer must be "you" or "opponent"`)
	}
	r, err := e.Reset()
	if err != nil {
		return nil, Result{}, err
	}
	return e, r, nil
}

// Reset starts a new game with the same decks.
func (e *Env) Reset() (Result, error) {
	g, err := NewGame(e.decks, e.firstDealer)
	if err != nil {
		return Result{}, err
	}
	e.game, e.exhausted = g, false
	events, err := g.Deal()
	if err != nil {
		return Result{}, err
	}
	adv, err := e.advance()
	if err != nil {
		return Result{}, err
	}
	return e.result(true, append(events, adv...), nil), nil
}

// Step applies the agent's action. An illegal or malformed action returns OK=false with an error
// and changes nothing.
func (e *Env) Step(in ActionInput) Result {
	if e.exhausted {
		return e.result(false, nil, &ErrorInfo{"game_over", "The game is over."})
	}
	a, err := ParseAction(in)
	var events []Event
	if err == nil {
		events, err = e.game.Apply(Agent, a)
	}
	if err != nil {
		ia := err.(*IllegalAction)
		return e.result(false, nil, &ErrorInfo{ia.Code, ia.Message})
	}
	adv, err := e.advance()
	if err != nil {
		panic(err) // unreachable: advance only fails on internal inconsistencies
	}
	return e.result(true, append(events, adv...), nil)
}

// Done reports whether the game is over.
func (e *Env) Done() bool { return e.game.State() == StateComplete || e.exhausted }

func (e *Env) advance() ([]Event, error) {
	var events []Event
	g := e.game
	for g.State() != StateComplete {
		if g.State() == StateShow {
			ev, err := g.Deal()
			if err != nil {
				if ia, ok := err.(*IllegalAction); ok && ia.Code == "decks_exhausted" {
					e.exhausted = true
					events = append(events, Event{Type: "decks_exhausted"})
					break
				}
				return nil, err
			}
			events = append(events, ev...)
		} else if toAct := g.ToAct(); containsPlayer(toAct, Opponent) {
			ev, err := g.Apply(Opponent, e.greedy())
			if err != nil {
				return nil, err
			}
			events = append(events, ev...)
		} else {
			break
		}
	}
	return events, nil
}

func containsPlayer(ps []Player, p Player) bool {
	for _, x := range ps {
		if x == p {
			return true
		}
	}
	return false
}

// greedy chooses the opponent's action: best-ranked discard, then the highest scoring legal play.
func (e *Env) greedy() Action {
	g := e.game
	hand := g.Hand(Opponent)
	if g.State() == StateDiscard {
		d := ChooseDiscards(hand, g.Dealer() == Opponent)
		return Action{ActionDiscard, []cards.Card{d[0], d[1]}}
	}
	c, _ := PlayAI(hand, g.CardsInPlay())
	return Action{ActionPlay, []cards.Card{c}}
}

func (e *Env) result(ok bool, events []Event, errInfo *ErrorInfo) Result {
	labelled := make([]Event, len(events))
	for i, ev := range events {
		l := ev
		l.Text = Describe(ev, Names)
		l.Player, l.Dealer, l.Winner = relabel(ev.Player), relabel(ev.Dealer), relabel(ev.Winner)
		labelled[i] = l
	}
	return Result{OK: ok, Error: errInfo, Events: labelled, Observation: e.Observation(), Done: e.Done()}
}

func relabel(s string) string {
	if v, ok := Names[s]; ok {
		return v
	}
	return s
}

// Observation is the current observation.
func (e *Env) Observation() Observation {
	g := e.game
	state := g.State()
	if e.exhausted {
		state = StateComplete
	}
	phase := map[PlayState]string{StateDiscard: "discard", StatePegging: "pegging", StateComplete: "complete", StateShow: "show", StateReady: "ready"}[state]
	cip := g.CardsInPlay()
	seq := func(pcs []PlayedCard) []SeqCard {
		out := []SeqCard{}
		for _, p := range pcs {
			out = append(out, SeqCard{relabel(p.Player.Name()), p.Card.ID()})
		}
		return out
	}
	actions := []ActionInput{}
	for _, a := range g.LegalActions(Agent) {
		actions = append(actions, actionToInput(a))
	}
	obs := Observation{
		Phase:               phase,
		YouScore:            g.Points(Agent),
		OpponentScore:       g.Points(Opponent),
		TargetScore:         WinningScore,
		Dealer:              relabel(g.Dealer().Name()),
		YourHand:            g.Hand(Agent).IDs(),
		OpponentCardsInHand: len(g.Hand(Opponent)),
		CribSize:            len(g.Crib()),
		Count:               cip.Count(),
		Sequence:            seq(cip.Sequence()),
		PlayedThisRound:     seq(cip.PlayedCards()),
		LegalActions:        actions,
	}
	if st, ok := g.Starter(); ok && (state == StatePegging || state == StateShow || state == StateComplete) {
		id := st.ID()
		obs.Starter = &id
	}
	if w, ok := g.Winner(); ok {
		name := relabel(w.Name())
		obs.Winner = &name
	}
	obs.Prompt = prompt(obs)
	return obs
}

func prompt(o Observation) string {
	switch o.Phase {
	case "complete":
		if o.Winner == nil {
			return fmt.Sprintf("Game over: the decks ran out at %d to %d.", o.YouScore, o.OpponentScore)
		}
		return fmt.Sprintf("Game over: %s won, %d to %d.", *o.Winner, o.YouScore, o.OpponentScore)
	case "discard":
		return fmt.Sprintf("Choose two cards from your hand to put in the crib (the crib belongs to the dealer: %s). "+
			`Action: {"type": "discard", "cards": ["5H", "KS"]}`, o.Dealer)
	}
	return fmt.Sprintf("Pegging: the count is %d. Play one card that keeps the count at 31 or less. "+
		`Action: {"type": "play", "card": "7D"}. If you cannot play, go is said for you.`, o.Count)
}
