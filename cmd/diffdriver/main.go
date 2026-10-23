// Command diffdriver replays games on the Go cribbage Env for scripts/diff_python_go.py.
//
// Input (stdin): {"games": [{"first_dealer": "you", "decks": [[card ids]], "actions": [action objects]}]}
// Output (stdout): {"games": [{"results": [...]}]} where results[0] is the reset result and
// results[i] the result of actions[i-1], in the CribbageEnv result shape.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/ericboehlke/cards/internal/cards"
	"github.com/ericboehlke/cards/internal/cribbage"
)

type game struct {
	FirstDealer string                 `json:"first_dealer"`
	Decks       [][]string             `json:"decks"`
	Actions     []cribbage.ActionInput `json:"actions"`
}

type gameOut struct {
	Results []cribbage.Result `json:"results"`
}

func run(g game) (gameOut, error) {
	var decks []cards.Hand
	for _, ids := range g.Decks {
		h, err := cards.ParseHand(ids)
		if err != nil {
			return gameOut{}, err
		}
		decks = append(decks, h)
	}
	env, first, err := cribbage.NewEnv(decks, g.FirstDealer)
	if err != nil {
		return gameOut{}, err
	}
	out := gameOut{Results: []cribbage.Result{first}}
	for _, a := range g.Actions {
		out.Results = append(out.Results, env.Step(a))
	}
	return out, nil
}

func main() {
	var in struct {
		Games []game `json:"games"`
	}
	if err := json.NewDecoder(os.Stdin).Decode(&in); err != nil {
		fmt.Fprintln(os.Stderr, "bad input:", err)
		os.Exit(2)
	}
	var out struct {
		Games []gameOut `json:"games"`
	}
	for i, g := range in.Games {
		o, err := run(g)
		if err != nil {
			fmt.Fprintf(os.Stderr, "game %d: %v\n", i, err)
			os.Exit(1)
		}
		out.Games = append(out.Games, o)
	}
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
