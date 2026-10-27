package tui

import (
	"fmt"
	"strings"
	"time"

	"charm.land/bubbles/v2/help"
	"charm.land/bubbles/v2/viewport"
	tea "charm.land/bubbletea/v2"

	"github.com/ericboehlke/cards/internal/cards"
	"github.com/ericboehlke/cards/internal/cribbage"
)

// beatDelay is how long a pegging beat stays up before the next one.
const beatDelay = 500 * time.Millisecond

type beatTickMsg struct{ gen int }

// Minimum terminal size for the full layout.
const (
	MinWidth  = 64
	MinHeight = 25
	maxWidth  = 110
)

// Model is the Bubble Tea model.
type Model struct {
	newGame            NewGameFunc
	env                *cribbage.Env
	obs                cribbage.Observation
	done               bool
	prevYou, prevOpp   int    // scores before the latest change: the back pegs
	gainYou, gainOpp   int    // points scored by the latest beat
	shownYou, shownOpp int    // scores on the board; they trail the engine while beats play out
	shownDealer        string // dealer of the round on the board (the count happens before the next deal shows)

	beats    []beat // scoring moments of the latest step, shown one at a time
	bi       int    // index of the beat on screen; len(beats) when finished
	roundEnd bool   // the beats include the count: wait for a key between them
	gen      int    // invalidates stale beat ticks
	ledger   ledger
	lastPlay string // text of the latest pegging beat

	cursor int
	sel    [6]bool // selected hand positions
	log    []string
	status string // last error / hint, cleared by the next key
	games  int    // games started in this session

	ascii    bool
	showHelp bool
	quitting bool
	width    int
	height   int
	vp       viewport.Model
	help     help.Model
}

// New creates the model and plays the opening deal.
func New(cfg Config) (Model, error) {
	ng := cfg.NewGame
	if ng == nil {
		var err error
		if ng, err = ShuffledGame(cfg.Seed); err != nil {
			return Model{}, err
		}
	}
	m := Model{newGame: ng, ascii: cfg.ASCII, width: 80, height: 30, vp: newViewport(), help: help.New()}
	if err := m.startGame(); err != nil {
		return Model{}, err
	}
	m.layout()
	return m, nil
}

func (m *Model) startGame() error {
	env, r, err := m.newGame()
	if err != nil {
		return err
	}
	m.env, m.obs, m.done = env, r.Observation, r.Done
	m.prevYou, m.prevOpp = r.Observation.YouScore, r.Observation.OpponentScore
	m.gainYou, m.gainOpp = 0, 0
	m.shownYou, m.shownOpp = 0, 0
	m.ledger, m.lastPlay = ledger{}, ""
	m.games++
	m.cursor, m.sel, m.status = 0, [6]bool{}, ""
	m.log = nil
	if m.games > 1 {
		m.addLog("--- new game ---")
	}
	m.logEvents(r.Events)
	m.queueBeats(r.Events)
	m.skipBeats() // an opening his heels is on the board straight away
	return nil
}

func (m *Model) addLog(lines ...string) {
	m.log = append(m.log, lines...)
}

func (m *Model) logEvents(evs []cribbage.Event) {
	for _, e := range evs {
		m.addLog(pretty(e.Text, m.ascii, true))
	}
	m.syncLog()
}

// syncLog pushes the log into the viewport and scrolls to the newest line.
func (m *Model) syncLog() {
	m.vp.SetContent(strings.Join(m.log, "\n"))
	m.vp.GotoBottom()
}

// Init implements tea.Model.
func (m Model) Init() tea.Cmd { return nil }

// Update implements tea.Model.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		m.layout()
		return m, nil
	case tea.KeyPressMsg:
		return m.handleKey(msg.String())
	case beatTickMsg:
		if msg.gen == m.gen && m.playing() && !m.roundEnd {
			cmd := m.advance()
			return m, cmd
		}
		return m, nil
	}
	return m, nil
}

// handleKey maps a key string (as tea.KeyPressMsg.String) to a state transition.
func (m Model) handleKey(k string) (tea.Model, tea.Cmd) {
	m.status = ""
	switch k {
	case "ctrl+c", "q":
		m.quitting = true
		return m, tea.Quit
	case "?":
		m.showHelp = !m.showHelp
		m.layout()
		return m, nil
	case "pgup":
		m.vp.PageUp()
		return m, nil
	case "pgdown":
		m.vp.PageDown()
		return m, nil
	case "home":
		m.vp.GotoTop()
		return m, nil
	case "end":
		m.vp.GotoBottom()
		return m, nil
	}
	if m.playing() {
		return m.beatKey(k)
	}
	if m.done {
		if k == "n" {
			if err := m.startGame(); err != nil {
				m.status = "Could not start a new game: " + err.Error()
			}
			m.layout()
		} else {
			m.status = "The game is over. Press n for a new game or q to quit."
		}
		return m, nil
	}
	n := len(m.obs.YourHand)
	switch k {
	case "left", "h":
		if m.cursor > 0 {
			m.cursor--
		}
	case "right", "l":
		if m.cursor < n-1 {
			m.cursor++
		}
	case "1", "2", "3", "4", "5", "6":
		if i := int(k[0] - '1'); i < n {
			m.cursor = i
		}
	case "space", " ":
		m.toggle()
	case "enter":
		m.confirm()
		return m, m.beatCmd()
	}
	return m, nil
}

func (m Model) selectedCount() int {
	c := 0
	for i := 0; i < len(m.obs.YourHand) && i < len(m.sel); i++ {
		if m.sel[i] {
			c++
		}
	}
	return c
}

func (m *Model) toggle() {
	if m.cursor >= len(m.obs.YourHand) {
		return
	}
	switch m.obs.Phase {
	case "discard":
		if !m.sel[m.cursor] && m.selectedCount() >= 2 {
			m.status = "Two cards are already selected; space on one of them to unselect it."
			return
		}
		m.sel[m.cursor] = !m.sel[m.cursor]
	}
	// pegging: nothing to select; enter plays the card under the cursor
}

// confirm submits the discard (two selected cards) or plays the card under the cursor.
func (m *Model) confirm() {
	hand := m.obs.YourHand
	switch m.obs.Phase {
	case "discard":
		if c := m.selectedCount(); c != 2 {
			m.status = fmt.Sprintf("Select exactly 2 cards for the crib with space (%d selected).", c)
			return
		}
		var ids []string
		for i, id := range hand {
			if m.sel[i] {
				ids = append(ids, id)
			}
		}
		m.step(cribbage.ActionInput{Type: cribbage.ActionDiscard, Cards: ids})
	case "pegging":
		i := m.cursor
		if i >= len(hand) {
			return
		}
		id := hand[i]
		m.step(cribbage.ActionInput{Type: cribbage.ActionPlay, Card: &id})
	}
}

// step sends the action to the engine; an illegal action is shown in the status line.
func (m *Model) step(in cribbage.ActionInput) {
	r := m.env.Step(in)
	if !r.OK {
		m.status = r.Error.Message
		return
	}
	m.gainYou = r.Observation.YouScore - m.obs.YouScore
	m.gainOpp = r.Observation.OpponentScore - m.obs.OpponentScore
	m.gainYou, m.gainOpp, m.lastPlay = 0, 0, ""
	m.obs, m.done = r.Observation, r.Done
	m.sel = [6]bool{}
	if n := len(m.obs.YourHand); m.cursor >= n {
		m.cursor = max(n-1, 0)
	}
	m.logEvents(r.Events)
	if m.done {
		m.addLog(m.obs.Prompt)
		m.syncLog()
	}
	m.queueBeats(r.Events)
}

// queueBeats starts showing the scoring of an engine step.
func (m *Model) queueBeats(evs []cribbage.Event) {
	m.beats, m.roundEnd = buildBeats(evs)
	m.gen++
	m.bi = 0
	if m.roundEnd {
		l := m.ledger // replay on a copy for the log's one-line round result
		for _, b := range m.beats {
			l.add(b)
		}
		t := l.total()
		m.addLog(fmt.Sprintf("Round result: You +%d, Opp +%d.", t[0], t[1]))
		m.syncLog()
	}
	if len(m.beats) == 0 {
		m.syncShown()
		return
	}
	m.apply(m.beats[0])
}

// playing reports whether beats are still being shown (game input is ignored meanwhile).
func (m Model) playing() bool { return m.bi < len(m.beats) }

// counting reports whether the round-end counting panel is on screen.
func (m Model) counting() bool { return m.playing() && m.roundEnd }

// syncShown makes the board show the engine's scores.
func (m *Model) syncShown() {
	m.shownYou, m.shownOpp, m.shownDealer = m.obs.YouScore, m.obs.OpponentScore, m.obs.Dealer
}

// apply puts one beat on the board: the score moves and the ledger and play line update.
func (m *Model) apply(b beat) {
	m.gainYou, m.gainOpp = 0, 0
	if b.points > 0 {
		if b.who == "you" {
			m.prevYou, m.shownYou, m.gainYou = m.shownYou, m.shownYou+b.points, b.points
		} else {
			m.prevOpp, m.shownOpp, m.gainOpp = m.shownOpp, m.shownOpp+b.points, b.points
		}
	}
	m.ledger.add(b)
	if b.kind == "play" || b.kind == "heels" || b.kind == "last_card" {
		m.lastPlay = b.text
	}
}

// advance moves to the next beat (or finishes) and returns the command that times it.
func (m *Model) advance() tea.Cmd {
	m.gen++
	m.bi++
	if m.playing() {
		m.apply(m.beats[m.bi])
	} else {
		m.syncShown()
	}
	return m.beatCmd()
}

// skipBeats applies every remaining beat at once.
func (m *Model) skipBeats() {
	for m.playing() {
		m.advance()
	}
	m.gen++
}

// beatCmd times the next pegging beat; counting beats wait for a key instead.
func (m Model) beatCmd() tea.Cmd {
	if !m.playing() || m.roundEnd {
		return nil
	}
	gen := m.gen
	return tea.Tick(beatDelay, func(time.Time) tea.Msg { return beatTickMsg{gen} })
}

// beatKey handles a key while beats are playing.
func (m Model) beatKey(k string) (tea.Model, tea.Cmd) {
	switch {
	case k == "esc":
		m.skipBeats()
	case !m.roundEnd, k == "enter", k == "space", k == " ", k == "right", k == "l":
		// pegging beats: any key skips ahead; counting beats: a next-step key
		cmd := m.advance()
		return m, cmd
	}
	return m, nil
}

// tooSmall reports whether the terminal is below the minimum size.
func (m Model) tooSmall() bool { return m.width < MinWidth || m.height < MinHeight }

// Done reports whether the current game is over.
func (m Model) Done() bool { return m.done }

// Observation returns the current engine observation.
func (m Model) Observation() cribbage.Observation { return m.obs }

// Cursor returns the hand cursor position.
func (m Model) Cursor() int { return m.cursor }

// Selected returns the ids of the selected hand cards.
func (m Model) Selected() []string {
	var out []string
	for i, id := range m.obs.YourHand {
		if i < len(m.sel) && m.sel[i] {
			out = append(out, id)
		}
	}
	return out
}

// Status returns the last hint or error message.
func (m Model) Status() string { return m.status }

// Log returns the event log lines (with styling).
func (m Model) Log() []string { return append([]string(nil), m.log...) }

func parseCard(id string) (cards.Card, bool) {
	c, err := cards.ParseCard(id)
	return c, err == nil
}

func newViewport() viewport.Model {
	vp := viewport.New()
	vp.SoftWrap = true
	return vp
}
