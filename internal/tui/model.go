package tui

import (
	"fmt"
	"strings"

	"charm.land/bubbles/v2/help"
	"charm.land/bubbles/v2/viewport"
	tea "charm.land/bubbletea/v2"

	"github.com/ericboehlke/cards/internal/cards"
	"github.com/ericboehlke/cards/internal/cribbage"
)

// Minimum terminal size for the full layout.
const (
	MinWidth  = 64
	MinHeight = 24
	maxWidth  = 110
)

// Model is the Bubble Tea model.
type Model struct {
	newGame NewGameFunc
	env     *cribbage.Env
	obs     cribbage.Observation
	done    bool

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
	m.games++
	m.cursor, m.sel, m.status = 0, [6]bool{}, ""
	m.log = nil
	if m.games > 1 {
		m.addLog("--- new game ---")
	}
	m.logEvents(r.Events)
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
