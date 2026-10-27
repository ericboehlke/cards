package tui

import (
	"fmt"
	"image/color"
	"regexp"
	"strings"

	"charm.land/bubbles/v2/key"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"github.com/charmbracelet/x/ansi"

	"github.com/ericboehlke/cards/internal/cribbage"
)

var (
	colRed    color.Color = lipgloss.Color("#e5484d")
	colAccent color.Color = lipgloss.Color("#f5c542")
	colGood   color.Color = lipgloss.Color("#46c46f")
	colDim    color.Color = lipgloss.Color("#7a7a7a")
	colBlue   color.Color = lipgloss.Color("#5b8def")
)

var cardRe = regexp.MustCompile(`\b(10|[A2-9TJQK])([HDCS])\b`)

// glyph returns the display form of a suit char.
func glyph(suit byte, ascii bool) string {
	if ascii {
		return string(suit)
	}
	switch suit {
	case 'H':
		return "♥"
	case 'D':
		return "♦"
	case 'C':
		return "♣"
	}
	return "♠"
}

// rankText turns a card id rank char into its label ("T" is "10").
func rankText(r byte) string {
	if r == 'T' {
		return "10"
	}
	return string(r)
}

// cardLabel is the plain text of a card id such as "TH": "10♥" (or "10H" in ASCII mode).
func cardLabel(id string, ascii bool) string {
	if len(id) != 2 {
		return id
	}
	return rankText(id[0]) + glyph(id[1], ascii)
}

func isRedID(id string) bool { return len(id) == 2 && (id[1] == 'H' || id[1] == 'D') }

// styledCard is cardLabel, red for hearts and diamonds when styled is set.
func styledCard(id string, ascii, styled bool) string {
	s := cardLabel(id, ascii)
	if styled && isRedID(id) {
		return lipgloss.NewStyle().Foreground(colRed).Render(s)
	}
	return s
}

// pretty replaces card ids in engine text ("7D", "TS") with display labels.
func pretty(text string, ascii, styled bool) string {
	return cardRe.ReplaceAllStringFunc(text, func(id string) string {
		if id[0] == '1' { // already "10x"
			id = "T" + id[2:]
		}
		return styledCard(id, ascii, styled)
	})
}

func (m Model) border() lipgloss.Border {
	if m.ascii {
		return lipgloss.ASCIIBorder()
	}
	return lipgloss.RoundedBorder()
}

func (m Model) boxWidth() int { return min(m.width, maxWidth) }

// layout sizes the viewport and help for the current terminal.
func (m *Model) layout() {
	w := m.boxWidth()
	m.help.SetWidth(w)
	m.vp.SetWidth(max(w-4, 1))
	h := m.height - fixedRows - lipgloss.Height(m.footer()) - 2
	m.vp.SetHeight(max(h, 1))
	m.syncLog()
}

// fixedRows is the height of everything except the log box and the footer: scores panel (5),
// opponent's cards (3), pegging panel (5), hand (5) and the status line (1).
const fixedRows = 19

type keyMap struct {
	done, pegging, ascii, counting bool
}

// ShortHelp is kept under 64 columns (MinWidth) in both modes.
func (k keyMap) ShortHelp() []key.Binding {
	if k.counting {
		return []key.Binding{bind("enter", "next"), bind("esc", "skip"), bind("?", "help"), bind("q", "quit")}
	}
	if k.done {
		return []key.Binding{bind("n", "new game"), bind("?", "help"), bind("q", "quit")}
	}
	move := bind("←/→", "move")
	if k.ascii {
		move = bind("arrows", "move")
	}
	if k.pegging {
		return []key.Binding{move, bind("enter", "play"), bind("?", "help"), bind("q", "quit")}
	}
	return []key.Binding{move, bind("space", "select"), bind("enter", "confirm"), bind("?", "help"), bind("q", "quit")}
}

func (k keyMap) FullHelp() [][]key.Binding {
	left, right := bind("←/h", "move left"), bind("→/l", "move right")
	if k.ascii {
		left, right = bind("left/h", "move left"), bind("right/l", "move right")
	}
	return [][]key.Binding{
		{left, right, bind("1-6", "jump")},
		{bind("space", "select 2"), bind("enter", "discard/play"), bind("n", "new game")},
		{bind("pgup/pgdn", "scroll"), bind("esc", "skip"), bind("q", "quit")},
	}
}

func bind(k, desc string) key.Binding {
	return key.NewBinding(key.WithKeys(k), key.WithHelp(k, desc))
}

func (m Model) footer() string {
	h := m.help
	h.ShowAll = m.showHelp
	if m.ascii {
		h.ShortSeparator, h.FullSeparator, h.Ellipsis = " | ", "    ", "..."
	}
	return h.View(keyMap{done: m.done, pegging: m.obs.Phase == "pegging", ascii: m.ascii, counting: m.counting()})
}

func (m Model) panel(width int, lines ...string) string {
	return lipgloss.NewStyle().Border(m.border()).BorderForeground(colDim).Padding(0, 1).Width(width).Render(strings.Join(lines, "\n"))
}

// bar draws the score as two pegs: the part up to the back peg (prev) in green and the latest
// gain up to the front peg (score) in yellow. ASCII mode also uses a different fill character.
func (m Model) bar(prev, score, w int) string {
	full, last, empty := "█", "█", "░"
	if m.ascii {
		full, last, empty = "#", "=", "-"
	}
	// Round the front peg up so any score shows at least one cell, and keep the latest gain visible.
	score = min(max(score, 0), 121)
	p := min(max(prev, 0), score) * w / 121
	n := (score*w + 120) / 121
	if score > prev {
		n = min(max(n, p+1), w)
	}
	return "[" + lipgloss.NewStyle().Foreground(colGood).Render(strings.Repeat(full, p)) +
		lipgloss.NewStyle().Foreground(colAccent).Render(strings.Repeat(last, n-p)) +
		strings.Repeat(empty, w-n) + "]"
}

// dealerMark is the fixed-width (3 column) marker shown beside the dealer's score.
func (m Model) dealerMark(on bool) string {
	switch {
	case !on:
		return "   "
	case m.ascii:
		return "D  "
	}
	return "🦆 "
}

// gainText is the fixed-width (4 column) "+N" shown beside a name for points just scored.
func gainText(n int) string {
	if n <= 0 {
		return "    "
	}
	return lipgloss.NewStyle().Foreground(colAccent).Bold(true).Render(fmt.Sprintf("%-4s", fmt.Sprintf("+%d", n)))
}

func bold(s string) string { return lipgloss.NewStyle().Bold(true).Render(s) }

func dim(s string) string { return lipgloss.NewStyle().Foreground(colDim).Render(s) }

// View implements tea.Model.
func (m Model) View() tea.View {
	v := tea.NewView(m.render())
	v.AltScreen = true
	return v
}

func (m Model) render() string {
	if m.quitting {
		return ""
	}
	if m.tooSmall() {
		return m.tooSmallView()
	}
	w := m.boxWidth()
	o := m.obs
	// scores panel across the top
	bw := max(w-22, 6)
	scores := m.panel(w,
		bold(fmt.Sprintf("Cribbage - first to %d", o.TargetScore)),
		fmt.Sprintf("%sYou %s %3d %s", m.dealerMark(m.shownDealer == "you"), gainText(m.gainYou), m.shownYou, m.bar(m.prevYou, m.shownYou, bw)),
		fmt.Sprintf("%sOpp %s %3d %s", m.dealerMark(m.shownDealer != "you"), gainText(m.gainOpp), m.shownOpp, m.bar(m.prevOpp, m.shownOpp, bw)))
	crib := "opp's"
	if o.Dealer == "you" {
		crib = "yours"
	}

	// pegging
	var l1, l2, l3 string
	switch o.Phase {
	case "pegging":
		l1 = bold("Pegging") + fmt.Sprintf("  Count: %d / 31", o.Count)
		l2 = "Sequence: " + m.seqText(o.Sequence)
		l3 = "Played:   " + m.seqText(o.PlayedThisRound)
		if m.lastPlay != "" {
			l3 = pretty(m.lastPlay, m.ascii, true)
		}
	case "discard":
		l1 = bold("Discard")
		l2 = fmt.Sprintf("Choose two cards for %s crib.", map[string]string{"yours": "your", "opp's": "the opponent's"}[crib])
		l3 = ""
		if m.lastPlay != "" {
			l3 = pretty(m.lastPlay, m.ascii, true)
		}
	default:
		l1 = bold("Game over")
		l2 = o.Prompt
	}
	peg := lipgloss.JoinHorizontal(lipgloss.Top, m.starterView(), " ", m.panel(w-8, l1, l2, l3))

	// status line
	st := dim(m.hint())
	if m.status != "" {
		st = lipgloss.NewStyle().Foreground(colRed).Bold(true).Render(m.status)
	}

	logBox := lipgloss.NewStyle().Border(m.border()).BorderForeground(colDim).Padding(0, 1).Width(w).Render(m.vp.View())
	middle := lipgloss.JoinVertical(lipgloss.Left, m.oppHandView(), peg, m.handView())
	if m.counting() {
		middle = m.countingView(w)
	}
	out := lipgloss.JoinVertical(lipgloss.Left, scores, middle, lipgloss.NewStyle().MaxWidth(w).Render(st), logBox, m.footer())
	return lipgloss.Place(m.width, m.height, lipgloss.Center, lipgloss.Center, out)
}

func (m Model) hint() string {
	switch {
	case m.counting():
		return "Counting the round: enter for the next step, esc to skip."
	case m.playing():
		return "Any key skips ahead."
	case m.done:
		return m.obs.Prompt + " Press n for a new game."
	case m.obs.Phase == "discard":
		return fmt.Sprintf("Select 2 cards with space (%d selected), then enter.", m.selectedCount())
	}
	return "Your play: move to a card and press enter (x = can't play)."
}

// seqText lists cards tagged by player: y:7♥ o:8♣.
func (m Model) seqText(sc []cribbage.SeqCard) string {
	if len(sc) == 0 {
		return dim("(none)")
	}
	parts := make([]string, len(sc))
	for i, c := range sc {
		tag := "o:"
		if c.Player == "you" {
			tag = "y:"
		}
		parts[i] = tag + styledCard(c.Card, m.ascii, true)
	}
	return strings.Join(parts, " ")
}

// starterView is the starter card beside the pegging panel, face down (xXx) until it is turned up
// when pegging starts. It is 5 rows tall like the panel.
func (m Model) starterView() string {
	st := lipgloss.NewStyle().Border(m.border()).BorderForeground(colDim).Width(7).Align(lipgloss.Center)
	card := st.Foreground(colBlue).BorderForeground(colBlue).Render("xXx")
	if m.obs.Starter != nil {
		card = st.Render(styledCard(*m.obs.Starter, m.ascii, true))
	}
	return lipgloss.PlaceVertical(5, lipgloss.Center, card)
}

// oppHandView draws the opponent's cards face down as xXx, always 3 rows tall.
func (m Model) oppHandView() string {
	n := m.obs.OpponentCardsInHand
	if n <= 0 {
		return "\n\n"
	}
	st := lipgloss.NewStyle().Border(m.border()).BorderForeground(colBlue).Foreground(colBlue).Width(7).Align(lipgloss.Center)
	var parts []string
	for range n {
		parts = append(parts, st.Render("xXx"), " ")
	}
	return lipgloss.JoinHorizontal(lipgloss.Top, parts...)
}

// handView draws the player's hand as small bordered cards with cursor and selection markers.
func (m Model) handView() string {
	o := m.obs
	title := bold("Your hand")
	if len(o.YourHand) == 0 {
		return lipgloss.JoinVertical(lipgloss.Left, title, dim("(no cards)"), "", "", "")
	}
	legal := map[string]bool{}
	for _, a := range o.LegalActions {
		if a.Card != nil {
			legal[*a.Card] = true
		}
	}
	var cardsOut, marks []string
	for i, id := range o.YourHand {
		st := lipgloss.NewStyle().Border(m.border()).BorderForeground(colDim).Width(7).Align(lipgloss.Center)
		if isRedID(id) {
			st = st.Foreground(colRed)
		}
		mark := " "
		unplayable := o.Phase == "pegging" && !legal[id]
		if unplayable {
			st = st.Faint(true)
			mark = "x"
		}
		if m.sel[i] {
			st = st.BorderForeground(colGood).Bold(true)
			mark = "+"
		}
		if i == m.cursor {
			st = st.BorderForeground(colAccent).Bold(true)
			mark = "^" + strings.TrimSpace(mark)
		}
		cardsOut = append(cardsOut, st.Render(cardLabel(id, m.ascii)), " ")
		marks = append(marks, lipgloss.PlaceHorizontal(7, lipgloss.Center, mark), " ")
	}
	row := lipgloss.JoinHorizontal(lipgloss.Top, cardsOut...)
	return lipgloss.JoinVertical(lipgloss.Left, title, row, strings.Join(marks, ""))
}

// tooSmallView is the message for terminals below the minimum size, clamped so that no line is
// wider and the whole is never taller than the terminal.
func (m Model) tooSmallView() string {
	if m.width <= 0 || m.height <= 0 {
		return ""
	}
	lines := []string{
		fmt.Sprintf("Terminal too small (%dx%d).", m.width, m.height),
		fmt.Sprintf("Cribbage needs at least %dx%d.", MinWidth, MinHeight),
		"(q quits)",
	}
	if len(lines) > m.height {
		lines = lines[:m.height]
	}
	for i, l := range lines {
		lines[i] = ansi.Truncate(l, m.width, "")
	}
	return lipgloss.Place(m.width, m.height, lipgloss.Center, lipgloss.Center, strings.Join(lines, "\n"))
}

// cardBox is a small bordered card like the ones in the hand.
func (m Model) cardBox(id string) string {
	st := lipgloss.NewStyle().Border(m.border()).BorderForeground(colDim).Width(7).Align(lipgloss.Center)
	if isRedID(id) {
		st = st.Foreground(colRed)
	}
	return st.Render(cardLabel(id, m.ascii))
}

// cell formats ledger points for a column.
func cell(n int) string {
	if n == 0 {
		return fmt.Sprintf("%5s", ".")
	}
	return fmt.Sprintf("%5s", fmt.Sprintf("+%d", n))
}

// countingView replaces the opponent's cards, the pegging panel and your hand while the round is
// counted: the hand being scored with the starter and its breakdown, and the round's ledger. It
// is as tall as those three blocks (13 rows).
func (m Model) countingView(w int) string {
	b := m.beats[m.bi]
	var top, info string
	switch b.kind {
	case "hand", "crib":
		var parts []string
		for _, id := range b.cards {
			parts = append(parts, m.cardBox(id), " ")
		}
		parts = append(parts, bold(" + "), m.cardBox(b.starter))
		top = lipgloss.JoinHorizontal(lipgloss.Center, parts...)
		info = bold(possessive(b.who)+" "+b.kind) + ": " + b.detail + fmt.Sprintf(" = %d -> %s +%d", b.points, whoName(b.who), b.points)
	default:
		top = "\n" + pretty(b.text, m.ascii, true) + "\n"
	}

	l := m.ledger
	cur := ""
	switch b.kind {
	case "play", "heels":
		cur = "Pegging"
	case "last_card":
		cur = "Last card"
	case "hand":
		cur = l.rows[max(l.nhands-1, 0)].label
	case "crib":
		cur = l.rows[2].label
	}
	row := func(label string, you, opp int) string {
		s := fmt.Sprintf("%-12s %s %s", label, cell(you), cell(opp))
		if label == cur {
			return lipgloss.NewStyle().Foreground(colAccent).Bold(true).Render(s)
		}
		return s
	}
	lines := []string{top, info, bold(fmt.Sprintf("%-12s %5s %5s", "This round", "You", "Opp"))}
	lines = append(lines, row("Pegging", l.peg[0], l.peg[1]), row("Last card", l.last[0], l.last[1]))
	labels := [3]string{"Hand", "Hand", "Crib"}
	for i, r := range l.rows {
		if r.label != "" {
			labels[i] = r.label
		}
		lines = append(lines, row(labels[i], r.pts[0], r.pts[1]))
	}
	t := l.total()
	lines = append(lines, row("Round total", t[0], t[1]))
	return m.panel(w, lines...)
}
