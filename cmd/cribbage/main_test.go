package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestRunFlags(t *testing.T) {
	cases := []struct {
		args []string
		code int
	}{
		{nil, 2},
		{[]string{"serve"}, 2},
		{[]string{"serve", "--json", "--opponent", "random"}, 2},
		{[]string{"serve", "--json", "--bogus"}, 2},
		{[]string{"serve", "--json", "extra"}, 2},
		{[]string{"serve", "--json", "--seed", "5", "x", "y"}, 2},
		{[]string{"serve", "--json", "--seed", "5", "--opponent", "greedy"}, 0},
		{[]string{"play", "--bogus"}, 2},
		{[]string{"play", "extra"}, 2},
	}
	for _, c := range cases {
		var out, errb bytes.Buffer
		if got := run(c.args, strings.NewReader(""), &out, &errb); got != c.code {
			t.Errorf("%v: exit %d, want %d (%s)", c.args, got, c.code, errb.String())
		}
		if c.code == 0 && strings.Count(out.String(), "\n") != 1 {
			t.Errorf("want exactly the opening line, got %q", out.String())
		}
		if c.code != 0 && out.Len() != 0 {
			t.Errorf("%v: stdout must stay empty", c.args)
		}
	}
}
