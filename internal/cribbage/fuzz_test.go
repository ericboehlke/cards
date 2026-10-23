package cribbage

// Full-game fuzzing, a port of cards/test/fuzz_cribbage.py. Seeded games are played through Game
// with random and greedy players while a ruleChecker compares every action with the rules of
// cribbage (using the independent oracle in oracle_test.go). Illegal actions must be rejected
// without changing anything. A second fuzzer drives the Env with junk actions. FuzzEnv is a native
// Go fuzz target: `go test -run=^$ -fuzz=FuzzEnv ./internal/cribbage`.

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"reflect"
	"strings"
	"testing"

	"github.com/ericboehlke/cards/internal/cards"
)

const fuzzDecks = 80 // far more deals than any game needs

func shuffledDecks(rng *rand.Rand, n int) []cards.Hand {
	decks := make([]cards.Hand, n)
	for i := range decks {
		decks[i] = shuffled(rng)
	}
	return decks
}

type ruleChecker struct {
	g          *Game
	sequence   []rawCard
	lastPlayer Player
	plays      int
	lastPoints [2]int
	dealer     Player
	dealt      bool
}

type snapshot struct {
	State  PlayState
	Points [2]int
	Hands  [2]string
	Crib   string
	Count  int
	Seq    int
	Turn   Player
	HasT   bool
	ToAct  []Player
}

func (rc *ruleChecker) snapshot() snapshot {
	g := rc.g
	turn, ok := g.Turn()
	return snapshot{g.State(), [2]int{g.Points(Player1), g.Points(Player2)},
		[2]string{fmt.Sprint(g.Hand(Player1)), fmt.Sprint(g.Hand(Player2))},
		fmt.Sprint(g.Crib()), g.CardsInPlay().Count(), len(g.CardsInPlay().Sequence()), turn, ok, g.ToAct()}
}

func (rc *ruleChecker) onDeal() error {
	g := rc.g
	if g.State() != StateDiscard {
		return fmt.Errorf("deal did not enter DISCARD")
	}
	if rc.dealt && g.Dealer() != rc.dealer.Other() {
		return fmt.Errorf("dealer did not alternate")
	}
	rc.dealer, rc.dealt = g.Dealer(), true
	for _, p := range []Player{Player1, Player2} {
		if len(g.Hand(p)) != 6 {
			return fmt.Errorf("each player must be dealt six cards")
		}
	}
	rc.sequence, rc.lastPlayer, rc.plays = nil, rc.dealer, 0
	return rc.checkCards()
}

// checkCards: no card is ever duplicated or lost.
func (rc *ruleChecker) checkCards() error {
	g := rc.g
	var all []cards.Card
	for _, p := range []Player{Player1, Player2} {
		all = append(all, g.Hand(p)...)
		all = append(all, g.CardsInPlay().ReturnCards(p)...)
	}
	all = append(all, g.Crib()...)
	st, _ := g.Starter()
	all = append(all, st)
	seen := map[cards.Card]bool{}
	for _, c := range all {
		if seen[c] {
			return fmt.Errorf("card %v appears twice", c)
		}
		seen[c] = true
	}
	if len(all) != 13 {
		return fmt.Errorf("%d cards in play, want 13 (state %s)", len(all), g.State().Name())
	}
	if s := g.State(); (s == StatePegging || s == StateShow) && len(g.Crib()) != 4 {
		return fmt.Errorf("crib must have four cards")
	}
	return nil
}

func (rc *ruleChecker) count() int {
	n := 0
	for _, c := range rc.sequence {
		n += oracleValue(c.rank)
	}
	return n
}

func (rc *ruleChecker) beforeAction(p Player, a Action) error {
	g := rc.g
	if g.State() == StatePegging && a.Type == ActionPlay {
		if len(rc.sequence) == 0 {
			last := rc.lastPlayer
			leader := last
			if len(g.Hand(last.Other())) > 0 {
				leader = last.Other()
			}
			if p != leader {
				return fmt.Errorf("%s led but %s should have", p.Name(), leader.Name())
			}
		}
		if turn, _ := g.Turn(); p != turn {
			return fmt.Errorf("turn mismatch")
		}
	}
	return nil
}

func playerOf(name string) Player {
	if name == "PLAYER2" {
		return Player2
	}
	return Player1
}

func (rc *ruleChecker) afterAction(p Player, a Action, events []Event, before snapshot, beforeHands [2]cards.Hand) error {
	g := rc.g
	if before.State == StateComplete {
		return fmt.Errorf("action accepted after game over")
	}
	over := false
	for _, e := range events {
		if over {
			return fmt.Errorf("event %s after game_over", e.Type)
		}
		switch e.Type {
		case "play":
			card := cards.MustParseCard(e.Card)
			want := oraclePegPlayScore(rc.sequence, raw(card))
			got := e.Fifteen + e.Thirtyone + e.Pair + e.Run
			if got != e.Points {
				return fmt.Errorf("play points do not add up")
			}
			if got != want {
				return fmt.Errorf("%v then %v: engine %d, oracle %d", rc.sequence, card, got, want)
			}
			rc.sequence = append(rc.sequence, raw(card))
			rc.lastPlayer = playerOf(e.Player)
			rc.plays++
			count := rc.count()
			if count > 31 {
				return fmt.Errorf("count over 31")
			}
			if count != e.Count {
				return fmt.Errorf("event count %d, want %d", e.Count, count)
			}
			if count == 31 {
				rc.sequence = nil
			}
		case "go":
			stuck := playerOf(e.Player)
			if len(rc.sequence) == 0 {
				return fmt.Errorf("go with nothing played")
			}
			count := rc.count()
			held := 0
			for _, c := range beforeHands[stuck] {
				if stuck == p && a.Type == ActionPlay && c == a.Cards[0] {
					continue
				}
				held++
				if oracleValue(c.Rank)+count <= 31 {
					return fmt.Errorf("go said while holding playable %v", c)
				}
			}
			if e.NoCards != (held == 0) {
				return fmt.Errorf("go no_cards flag wrong")
			}
		case "last_card":
			if playerOf(e.Player) != rc.lastPlayer {
				return fmt.Errorf("last card to wrong player")
			}
			if e.Points != 1 {
				return fmt.Errorf("last card must be one point")
			}
			if len(rc.sequence) == 0 {
				return fmt.Errorf("last card with empty sequence")
			}
			rc.sequence = nil
		case "his_heels":
			if playerOf(e.Player) != rc.dealer {
				return fmt.Errorf("his heels to non-dealer")
			}
			if st, _ := g.Starter(); st.Rank != cards.Jack || e.Points != 2 {
				return fmt.Errorf("his heels without a jack")
			}
		case "show":
			st, _ := g.Starter()
			hand := cards.MustParseHand(e.Cards...)
			if len(hand) != 4 {
				return fmt.Errorf("shown hand must have four cards")
			}
			want := oracleHandScore(raws(hand), raw(st), e.What == "crib")
			if e.Points != want {
				return fmt.Errorf("show %v+%v: engine %d, oracle %d", hand.IDs(), st, e.Points, want)
			}
		case "game_over":
			over = true
		}
	}
	if over {
		return rc.checkGameOver()
	}
	for _, q := range []Player{Player1, Player2} {
		if g.Points(q) < rc.lastPoints[q] {
			return fmt.Errorf("points went down")
		}
		rc.lastPoints[q] = g.Points(q)
		if g.Points(q) >= WinningScore {
			return fmt.Errorf("someone reached 121 without the game ending")
		}
	}
	switch g.State() {
	case StatePegging:
		turn, ok := g.Turn()
		if !ok {
			return fmt.Errorf("pegging with nobody to play")
		}
		if !reflect.DeepEqual(g.ToAct(), []Player{turn}) {
			return fmt.Errorf("exactly the player on turn may act")
		}
		for _, q := range []Player{Player1, Player2} {
			if len(g.Hand(q))+len(g.CardsInPlay().ReturnCards(q)) != 4 {
				return fmt.Errorf("four cards each")
			}
		}
	case StateShow:
		if rc.plays != 8 {
			return fmt.Errorf("the show began after %d plays, not 8", rc.plays)
		}
		if len(rc.sequence) != 0 {
			return fmt.Errorf("show began mid-sequence (missing last card point)")
		}
	}
	return rc.checkCards()
}

func (rc *ruleChecker) checkGameOver() error {
	g := rc.g
	if g.State() != StateComplete {
		return fmt.Errorf("game_over without COMPLETE")
	}
	w, ok := g.Winner()
	if !ok || g.Points(w) < WinningScore {
		return fmt.Errorf("winner has fewer than 121")
	}
	if g.Points(w.Other()) >= WinningScore {
		return fmt.Errorf("both players at 121 or more")
	}
	if len(g.ToAct()) != 0 {
		return fmt.Errorf("players can still act after the game")
	}
	for _, q := range []Player{Player1, Player2} {
		if len(g.LegalActions(q)) != 0 {
			return fmt.Errorf("legal actions after game over")
		}
		if g.Points(q) < rc.lastPoints[q] {
			return fmt.Errorf("points went down")
		}
	}
	return nil
}

// badAction returns an action that must be rejected right now, or false.
func badAction(rng *rand.Rand, g *Game, p Player, legal []Action) (Action, bool) {
	var choices []Action
	hand := g.Hand(p)
	otherHand := g.Hand(p.Other())
	other := func(c cards.Card) cards.Card { // a card that is not in hand
		for _, d := range cards.Deck() {
			if !hand.Contains(d) {
				return d
			}
		}
		return c
	}
	switch g.State() {
	case StateDiscard:
		if len(hand) >= 3 {
			choices = append(choices,
				Action{ActionPlay, []cards.Card{hand[0]}},
				Action{ActionDiscard, []cards.Card{hand[0]}},
				Action{ActionDiscard, []cards.Card{hand[0], hand[0]}},
				Action{ActionDiscard, []cards.Card{hand[0], hand[1], hand[2]}},
				Action{ActionDiscard, []cards.Card{hand[0], other(hand[0])}},
				Action{ActionDiscard, nil},
				Action{"bogus", []cards.Card{hand[0]}})
		}
	case StatePegging:
		if len(hand) >= 2 {
			choices = append(choices, Action{ActionDiscard, []cards.Card{hand[0], hand[1]}},
				Action{ActionPlay, []cards.Card{hand[0], hand[1]}})
		}
		choices = append(choices, Action{ActionPlay, nil}, Action{ActionPlay, []cards.Card{other(cards.Card{})}})
		if len(otherHand) > 0 {
			choices = append(choices, Action{ActionPlay, []cards.Card{otherHand[0]}})
		}
		for _, c := range hand {
			if !g.CardsInPlay().CanPlay(c) {
				choices = append(choices, Action{ActionPlay, []cards.Card{c}})
				break
			}
		}
		if turn, _ := g.Turn(); p.Other() == turn && len(hand) > 0 {
			choices = append(choices, Action{ActionPlay, []cards.Card{hand[0]}})
		}
	default:
		choices = append(choices, Action{ActionPlay, []cards.Card{cards.Deck()[0]}})
	}
	var ok []Action
	for _, c := range choices {
		if !containsAction(legal, c) {
			ok = append(ok, c)
		}
	}
	if len(ok) == 0 {
		return Action{}, false
	}
	return ok[rng.Intn(len(ok))], true
}

func containsAction(as []Action, a Action) bool {
	for _, x := range as {
		if x.Type == a.Type && sameCards(x.Cards, a.Cards) {
			return true
		}
	}
	return false
}

// sameCards compares two card lists ignoring order (a discard of KS,AH equals AH,KS).
func sameCards(a, b []cards.Card) bool {
	return reflect.DeepEqual(cards.Hand(a).Sorted(), cards.Hand(b).Sorted()) && len(a) == len(b)
}

func greedyAction(g *Game, p Player) Action {
	hand := g.Hand(p)
	if g.State() == StateDiscard {
		d := ChooseDiscards(hand, g.Dealer() == p)
		return Action{ActionDiscard, []cards.Card{d[0], d[1]}}
	}
	c, _ := PlayAI(hand, g.CardsInPlay())
	return Action{ActionPlay, []cards.Card{c}}
}

// playFuzzGame plays one full game and returns the number of actions, or an error on a rule violation.
func playFuzzGame(seed int64, greedy [2]bool) (int, error) {
	rng := rand.New(rand.NewSource(seed))
	g, err := NewGame(shuffledDecks(rng, fuzzDecks), Player(rng.Intn(2)))
	if err != nil {
		return 0, err
	}
	rc := &ruleChecker{g: g}
	actions := 0
	for step := 0; step < 100000; step++ {
		if g.State() == StateComplete {
			if _, ok := g.Winner(); !ok {
				return actions, fmt.Errorf("complete without a winner")
			}
			return actions, nil
		}
		if g.State() == StateReady || g.State() == StateShow {
			if _, err := g.Deal(); err != nil {
				return actions, fmt.Errorf("deal: %v", err)
			}
			if err := rc.onDeal(); err != nil {
				return actions, err
			}
			continue
		}
		actors := g.ToAct()
		if len(actors) == 0 {
			return actions, fmt.Errorf("deadlock in %s", g.State().Name())
		}
		p := actors[rng.Intn(len(actors))]
		legal := g.LegalActions(p)
		var a Action
		if greedy[p] {
			a = greedyAction(g, p)
		} else {
			a = legal[rng.Intn(len(legal))]
		}
		if !containsAction(legal, a) {
			return actions, fmt.Errorf("chosen action %v is not legal", a)
		}
		before := rc.snapshot()
		if probe, ok := badAction(rng, g, p, legal); ok {
			_, err := g.Apply(p, probe)
			if _, isIllegal := err.(*IllegalAction); !isIllegal {
				return actions, fmt.Errorf("illegal action accepted or wrong error: %v (err %v)", probe, err)
			}
			if !reflect.DeepEqual(rc.snapshot(), before) {
				return actions, fmt.Errorf("an illegal action %v changed the game", probe)
			}
		}
		if err := rc.beforeAction(p, a); err != nil {
			return actions, err
		}
		beforeHands := [2]cards.Hand{g.Hand(Player1), g.Hand(Player2)}
		events, err := g.Apply(p, a)
		if err != nil {
			return actions, fmt.Errorf("legal action rejected: %v", err)
		}
		if err := rc.afterAction(p, a, events, before, beforeHands); err != nil {
			return actions, err
		}
		actions++
	}
	return actions, fmt.Errorf("game did not finish")
}

func TestFuzzGames(t *testing.T) {
	games := 600
	if testing.Short() {
		games = 60
	}
	mixes := [][2]bool{{false, false}, {true, false}, {true, true}}
	total := 0
	for i := 0; i < games; i++ {
		mix := mixes[i%len(mixes)]
		n, err := playFuzzGame(int64(i), mix)
		if err != nil {
			t.Fatalf("seed %d greedy=%v: %v", i, mix, err)
		}
		total += n
	}
	t.Logf("%d games, %d actions", games, total)
}

// ---- Env fuzzing with junk actions ---------------------------------------------------------------

var knownCodes = map[string]bool{
	"bad_action": true, "wrong_phase": true, "already_discarded": true, "bad_discard": true,
	"not_your_turn": true, "bad_play": true, "card_not_in_hand": true, "exceeds_31": true,
	"game_over": true, "unknown_action": true,
}

// junkAction builds a random, mostly invalid action input.
func junkAction(rng *rand.Rand, legal []ActionInput) ActionInput {
	ids := []string{"AH", "5D", "TC", "KS", "ZZ", "", "1H", "5", "5X", "10H", "ah", "JS"}
	pick := func() string { return ids[rng.Intn(len(ids))] }
	sp := func(s string) *string { return &s }
	switch rng.Intn(10) {
	case 0:
		return ActionInput{Type: "bogus"}
	case 1:
		return ActionInput{}
	case 2:
		return ActionInput{Type: ActionPlay}
	case 3:
		return ActionInput{Type: ActionDiscard}
	case 4:
		return ActionInput{Type: ActionPlay, Card: sp(pick())}
	case 5:
		return ActionInput{Type: ActionPlay, Cards: []string{pick(), pick()}}
	case 6:
		return ActionInput{Type: ActionDiscard, Cards: []string{pick()}}
	case 7:
		return ActionInput{Type: ActionDiscard, Cards: []string{pick(), pick()}}
	case 8:
		if len(legal) > 0 {
			a := legal[rng.Intn(len(legal))]
			if a.Type == ActionPlay {
				return ActionInput{Type: ActionDiscard, Cards: []string{*a.Card, *a.Card}}
			}
			return ActionInput{Type: ActionPlay, Cards: a.Cards}
		}
	}
	return ActionInput{Type: ActionDiscard, Cards: []string{pick(), pick(), pick()}}
}

func canonical(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

// playFuzzEnv plays an Env game. Each decision byte of choices picks junk (when >= 128) or a legal
// action; when the bytes run out, legal actions are chosen from rng.
func playFuzzEnv(seed int64, choices []byte) error {
	rng := rand.New(rand.NewSource(seed))
	dealer := "you"
	if rng.Intn(2) == 1 {
		dealer = "opponent"
	}
	env, res, err := NewEnv(shuffledDecks(rng, fuzzDecks), dealer)
	if err != nil {
		return err
	}
	if !res.OK {
		return fmt.Errorf("reset not ok")
	}
	lastScores := [2]int{}
	for step := 0; step < 5000; step++ {
		obs := env.Observation()
		if env.Done() {
			if obs.Phase != "complete" || len(obs.LegalActions) != 0 {
				return fmt.Errorf("done but phase %q with %d legal actions", obs.Phase, len(obs.LegalActions))
			}
			if obs.Winner == nil && !strings.Contains(obs.Prompt, "decks ran out") {
				return fmt.Errorf("done without a winner")
			}
			after := env.Step(ActionInput{Type: ActionPlay, Cards: []string{"AH"}})
			if after.OK || after.Error == nil || after.Error.Code != "game_over" {
				return fmt.Errorf("step after game over: %+v", after.Error)
			}
			return nil
		}
		if len(obs.LegalActions) == 0 {
			return fmt.Errorf("not done but the agent has no legal action (phase %s)", obs.Phase)
		}
		if obs.Phase != "discard" && obs.Phase != "pegging" {
			return fmt.Errorf("agent to move in phase %q", obs.Phase)
		}
		var b byte
		if step < len(choices) {
			b = choices[step]
		} else {
			b = byte(rng.Intn(256))
		}
		var in ActionInput
		if b >= 160 {
			in = junkAction(rng, obs.LegalActions)
		} else {
			in = obs.LegalActions[int(b)%len(obs.LegalActions)]
		}
		legal := false
		for _, l := range obs.LegalActions {
			if canonical(l) == canonical(in) {
				legal = true
			}
		}
		// The agent's own representation may differ (play with "cards"), so only trust exact matches.
		before := canonical(obs)
		r := env.Step(in)
		if !legal && r.OK {
			// a junk action may coincide with a legal one in another spelling; verify it was legal
			a, perr := ParseAction(in)
			if perr != nil {
				return fmt.Errorf("malformed action accepted: %+v", in)
			}
			ok := false
			for _, la := range obs.LegalActions {
				pa, _ := ParseAction(la)
				if containsAction([]Action{pa}, a) {
					ok = true
				}
			}
			if !ok {
				return fmt.Errorf("illegal action accepted: %+v", in)
			}
		}
		if !r.OK {
			if legal {
				return fmt.Errorf("legal action %+v rejected: %+v", in, r.Error)
			}
			if r.Error == nil || !knownCodes[r.Error.Code] || len(r.Events) != 0 {
				return fmt.Errorf("bad rejection of %+v: %+v", in, r.Error)
			}
			if canonical(env.Observation()) != before {
				return fmt.Errorf("rejected action %+v changed the observation", in)
			}
			continue
		}
		if r.Error != nil {
			return fmt.Errorf("ok result with an error")
		}
		over := false
		for _, e := range r.Events {
			if over {
				return fmt.Errorf("event %s after game_over", e.Type)
			}
			if e.Type == "game_over" {
				over = true
			}
			if e.Text == "" {
				return fmt.Errorf("event %s has no text", e.Type)
			}
			if e.Player != "" && e.Player != "you" && e.Player != "opponent" {
				return fmt.Errorf("event player %q not relabelled", e.Player)
			}
		}
		scores := [2]int{r.Observation.YouScore, r.Observation.OpponentScore}
		for i := range scores {
			if scores[i] < lastScores[i] {
				return fmt.Errorf("score went down")
			}
			if scores[i] > WinningScore+30 {
				return fmt.Errorf("absurd score %d", scores[i])
			}
		}
		lastScores = scores
		if r.Done != env.Done() || (r.Done && r.Observation.Phase != "complete") {
			return fmt.Errorf("done flag inconsistent")
		}
		if over && r.Observation.Winner == nil {
			return fmt.Errorf("game_over without a winner in the observation")
		}
		if r.Observation.Winner != nil && scores[0] < WinningScore && scores[1] < WinningScore {
			return fmt.Errorf("winner declared below 121")
		}
	}
	return fmt.Errorf("env game did not finish")
}

func TestFuzzEnvJunk(t *testing.T) {
	games := 600
	if testing.Short() {
		games = 60
	}
	for i := 0; i < games; i++ {
		if err := playFuzzEnv(int64(1000+i), nil); err != nil {
			t.Fatalf("seed %d: %v", 1000+i, err)
		}
	}
}

func FuzzEnv(f *testing.F) {
	f.Add(int64(1), []byte{0, 0, 0, 200, 0, 170})
	f.Add(int64(2), []byte{255, 255, 3, 4, 5})
	f.Fuzz(func(t *testing.T, seed int64, choices []byte) {
		if err := playFuzzEnv(seed, choices); err != nil {
			t.Fatalf("seed %d choices %v: %v", seed, choices, err)
		}
	})
}
