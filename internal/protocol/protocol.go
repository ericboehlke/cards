// Package protocol implements the cribbage JSON-lines protocol (the Go equivalent of
// cards/cribbage/api_cli.py): one JSON object per input line, one JSON object per output line,
// the opening observation first. See docs/cribbage_api.md.
package protocol

import (
	"bufio"
	"bytes"
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	mrand "math/rand/v2"
	"strings"

	"github.com/ericboehlke/cards/internal/cards"
	"github.com/ericboehlke/cards/internal/cribbage"
)

// ShuffledDecks is how many shuffled decks a game gets; a game never needs anywhere near this many.
const ShuffledDecks = 100

// Options configures Serve.
type Options struct {
	// Seed makes shuffling and the first dealer reproducible. Every reset without its own seed
	// replays the same game, as in the Python CribbageEnv. Nil means a random seed per process.
	Seed *int64
}

// Server holds the state of one protocol session.
type Server struct {
	seed        *int64
	rng         *mrand.Rand
	fixedDecks  []cards.Hand // non-nil: replay these decks on every reset
	firstDealer string       // "" means random for shuffled games, "you" for fixed decks
	env         *cribbage.Env
}

// NewServer creates a Server and plays its opening deal. The first result is returned.
func NewServer(opts Options) (*Server, cribbage.Result, error) {
	s := &Server{seed: opts.Seed}
	if s.seed == nil {
		var b [8]byte
		if _, err := rand.Read(b[:]); err != nil {
			return nil, cribbage.Result{}, err
		}
		s.rng = newRand(int64(binary.LittleEndian.Uint64(b[:])))
	}
	r, err := s.reset(nil, s.fixedDecks, s.firstDealer)
	return s, r, err
}

func newRand(seed int64) *mrand.Rand {
	return mrand.New(mrand.NewPCG(uint64(seed), 0x9e3779b97f4a7c15))
}

func (s *Server) reset(seed *int64, decks []cards.Hand, dealer string) (cribbage.Result, error) {
	if seed != nil {
		s.seed = seed
	}
	if s.seed != nil {
		s.rng = newRand(*s.seed)
	}
	shuffled := decks == nil
	if shuffled {
		decks = make([]cards.Hand, ShuffledDecks)
		for i := range decks {
			d := cards.Deck()
			s.rng.Shuffle(len(d), func(a, b int) { d[a], d[b] = d[b], d[a] })
			decks[i] = d
		}
	}
	first := dealer
	if first == "" {
		switch {
		case !shuffled:
			first = "you"
		case s.rng.IntN(2) == 0:
			first = "you"
		default:
			first = "opponent"
		}
	}
	env, r, err := cribbage.NewEnv(decks, first)
	if err != nil {
		return cribbage.Result{}, err
	}
	s.env = env
	return r, nil
}

func (s *Server) errorResult(code, message string) cribbage.Result {
	return cribbage.Result{
		OK:          false,
		Error:       &cribbage.ErrorInfo{Code: code, Message: message},
		Events:      []cribbage.Event{},
		Observation: s.env.Observation(),
		Done:        s.env.Done(),
	}
}

func isNull(b json.RawMessage) bool { return bytes.Equal(bytes.TrimSpace(b), []byte("null")) }

// Handle processes one non-blank input line and returns the result to send.
func (s *Server) Handle(line string) cribbage.Result {
	var raw any
	dec := json.NewDecoder(strings.NewReader(line))
	if err := dec.Decode(&raw); err != nil {
		return s.errorResult("bad_json", fmt.Sprintf("Not valid JSON: %v", err))
	}
	if dec.More() {
		return s.errorResult("bad_json", "Not valid JSON: extra data after the first value")
	}
	if _, ok := raw.(map[string]any); !ok {
		return s.errorResult("bad_request", `Send a JSON object like {"action": {...}}`)
	}
	var msg map[string]json.RawMessage
	if err := json.Unmarshal([]byte(line), &msg); err != nil {
		return s.errorResult("bad_json", fmt.Sprintf("Not valid JSON: %v", err))
	}
	if a, ok := msg["action"]; ok {
		return s.step(a)
	}
	var command string
	if c, ok := msg["command"]; ok {
		_ = json.Unmarshal(c, &command) // non-strings fall through to bad_request
	}
	switch command {
	case "observe":
		return cribbage.Result{
			OK: true, Events: []cribbage.Event{}, Observation: s.env.Observation(), Done: s.env.Done(),
		}
	case "reset":
		return s.resetCommand(msg)
	}
	return s.errorResult("bad_request",
		`Send {"action": {...}}, {"command": "observe"} or {"command": "reset"}`)
}

func (s *Server) step(raw json.RawMessage) cribbage.Result {
	bad := func(format string, args ...any) cribbage.Result {
		return s.errorResult("bad_action", fmt.Sprintf(format, args...))
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil || fields == nil {
		return bad("Malformed action %s: expected an object with a type", raw)
	}
	var in cribbage.ActionInput
	if err := json.Unmarshal(raw, &in); err != nil {
		return bad("Malformed action %s: %v", raw, err)
	}
	if c, ok := fields["card"]; ok && isNull(c) {
		return bad("Malformed action %s: card must be a card id", raw)
	}
	if _, ok := fields["type"]; !ok {
		return bad("Malformed action %s: missing type", raw)
	}
	return s.env.Step(in)
}

func (s *Server) resetCommand(msg map[string]json.RawMessage) cribbage.Result {
	bad := func(format string, args ...any) cribbage.Result {
		return s.errorResult("bad_request", fmt.Sprintf(format, args...))
	}
	var seed *int64
	if b, ok := msg["seed"]; ok && !isNull(b) {
		var v int64
		if err := json.Unmarshal(b, &v); err != nil {
			return bad("seed must be an integer")
		}
		seed = &v
	}
	decks, dealer := s.fixedDecks, s.firstDealer
	if b, ok := msg["decks"]; ok {
		decks = nil
		if !isNull(b) {
			var ids [][]string
			if err := json.Unmarshal(b, &ids); err != nil || len(ids) == 0 {
				return bad("decks must be a non-empty list of 52 card id lists")
			}
			for i, one := range ids {
				h, err := cards.ParseHand(one)
				if err != nil {
					return bad("deck %d: %v", i, err)
				}
				decks = append(decks, h)
			}
			if _, _, err := cribbage.NewEnv(decks, "you"); err != nil {
				return bad("%v", err)
			}
		}
	}
	if b, ok := msg["first_dealer"]; ok {
		dealer = ""
		if !isNull(b) {
			if err := json.Unmarshal(b, &dealer); err != nil || (dealer != "you" && dealer != "opponent") {
				return bad(`first_dealer must be "you" or "opponent"`)
			}
		}
	}
	r, err := s.reset(seed, decks, dealer)
	if err != nil {
		return bad("%v", err)
	}
	s.fixedDecks, s.firstDealer = decks, dealer
	return r
}

// Serve writes the opening result, then answers each non-blank line of in with one line on out,
// flushing after every line. It returns at end of input.
func Serve(in io.Reader, out io.Writer, opts Options) error {
	w := bufio.NewWriter(out)
	send := func(v any) error {
		enc := json.NewEncoder(w)
		enc.SetEscapeHTML(false)
		if err := enc.Encode(v); err != nil {
			return err
		}
		return w.Flush()
	}
	s, first, err := NewServer(opts)
	if err != nil {
		return err
	}
	if err := send(first); err != nil {
		return err
	}
	r := bufio.NewReader(in)
	for {
		line, rerr := r.ReadString('\n')
		if line = strings.TrimSpace(line); line != "" {
			if err := send(s.Handle(line)); err != nil {
				return err
			}
		}
		if rerr == io.EOF {
			return nil
		}
		if rerr != nil {
			return rerr
		}
	}
}
