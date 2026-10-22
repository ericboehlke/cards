package cribbage

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math"
	"testing"
)

func TestDiscardTableCounts(t *testing.T) {
	if n := len(playerCribDiscardTable); n != 169 {
		t.Errorf("player table has %d entries, want 169", n)
	}
	if n := len(opponentCribDiscardTable); n != 169 {
		t.Errorf("opponent table has %d entries, want 169", n)
	}
}

func TestCribDiscardValue(t *testing.T) {
	tests := []struct {
		dealer bool
		a, b   int
		want   float64
	}{
		{true, 1, 1, 5.38},
		{true, 2, 3, 7.0},
		{true, 5, 5, 8.79},
		{true, 13, 1, 3.41},
		{true, 6, 10, 3.17},
		{true, 13, 13, 4.58},
		{false, 1, 1, -6.02},
		{false, 2, 3, -7.33},
		{false, 5, 5, -9.37},
		{false, 13, 1, -4.3},
		{false, 6, 10, -4.31},
		{false, 13, 13, -5.65},
	}
	for _, tc := range tests {
		got := CribDiscardValue(tc.dealer, tc.a, tc.b)
		if math.Float64bits(got) != math.Float64bits(tc.want) {
			t.Errorf("CribDiscardValue(%v,%d,%d)=%v want %v", tc.dealer, tc.a, tc.b, got, tc.want)
		}
	}
}

// TestDiscardTableChecksum recomputes the checksum the generator derived from the Python tables.
func TestDiscardTableChecksum(t *testing.T) {
	h := sha256.New()
	for _, tb := range []struct {
		name string
		m    map[discardKey]float64
	}{{"player", playerCribDiscardTable}, {"opponent", opponentCribDiscardTable}} {
		for a := 1; a <= 13; a++ {
			for b := 1; b <= 13; b++ {
				v, ok := tb.m[discardKey{a, b}]
				if !ok {
					t.Fatalf("%s table missing {%d,%d}", tb.name, a, b)
				}
				fmt.Fprintf(h, "%s %d %d %016x\n", tb.name, a, b, math.Float64bits(v))
			}
		}
	}
	if got := hex.EncodeToString(h.Sum(nil)); got != discardTableChecksum {
		t.Errorf("table checksum %s, generator recorded %s", got, discardTableChecksum)
	}
}
