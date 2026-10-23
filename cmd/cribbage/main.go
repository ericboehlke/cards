// Command cribbage is the Go cribbage program. Currently it only provides `serve --json`, the
// JSON-lines protocol of docs/cribbage_api.md.
package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/ericboehlke/cards/internal/protocol"
)

func main() { os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr)) }

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 || args[0] != "serve" {
		fmt.Fprintln(stderr, "usage: cribbage serve --json [--seed N] [--opponent greedy]")
		return 2
	}
	fs := flag.NewFlagSet("serve", flag.ContinueOnError)
	fs.SetOutput(stderr)
	jsonMode := fs.Bool("json", false, "speak the JSON-lines protocol on stdin/stdout (required)")
	seed := fs.Int64("seed", 0, "seed for shuffling and the first dealer (default: random)")
	opponent := fs.String("opponent", "greedy", "opponent: only greedy is supported")
	if err := fs.Parse(args[1:]); err != nil {
		return 2
	}
	if fs.NArg() > 0 {
		fmt.Fprintf(stderr, "cribbage serve: unexpected arguments %q\nusage: cribbage serve --json [--seed N] [--opponent greedy]\n", fs.Args())
		return 2
	}
	if !*jsonMode {
		fmt.Fprintln(stderr, "cribbage serve: --json is required")
		return 2
	}
	if *opponent != "greedy" {
		fmt.Fprintf(stderr, "cribbage serve: unsupported --opponent %q (only greedy)\n", *opponent)
		return 2
	}
	opts := protocol.Options{}
	fs.Visit(func(f *flag.Flag) {
		if f.Name == "seed" {
			opts.Seed = seed
		}
	})
	if err := protocol.Serve(stdin, stdout, opts); err != nil {
		fmt.Fprintln(stderr, "cribbage serve:", err)
		return 1
	}
	return 0
}
