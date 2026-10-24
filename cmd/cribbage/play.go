package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	tea "charm.land/bubbletea/v2"

	"github.com/ericboehlke/cards/internal/tui"
)

// runPlay runs the terminal UI: `cribbage play [--seed N] [--ascii]`.
func runPlay(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("play", flag.ContinueOnError)
	fs.SetOutput(stderr)
	seed := fs.Int64("seed", 0, "seed for shuffling and the first dealer (default: random)")
	ascii := fs.Bool("ascii", false, "use H/D/C/S and ASCII borders (also automatic with CARDS_ASCII=1, TERM=dumb or a non-UTF-8 locale)")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if fs.NArg() > 0 {
		fmt.Fprintf(stderr, "cribbage play: unexpected arguments %q\n", fs.Args())
		return 2
	}
	cfg := tui.Config{ASCII: *ascii || tui.DetectASCII(os.Getenv)}
	fs.Visit(func(f *flag.Flag) {
		if f.Name == "seed" {
			cfg.Seed = seed
		}
	})
	m, err := tui.New(cfg)
	if err != nil {
		fmt.Fprintln(stderr, "cribbage play:", err)
		return 1
	}
	if _, err := tea.NewProgram(m, tea.WithInput(stdin), tea.WithOutput(stdout)).Run(); err != nil {
		fmt.Fprintln(stderr, "cribbage play:", err)
		return 1
	}
	return 0
}
