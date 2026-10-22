package cards

import "testing"

func TestDeck(t *testing.T) {
	d := Deck()
	if len(d) != 52 || d[0].ID() != "AH" || d[13].ID() != "AD" || d[51].ID() != "KS" {
		t.Fatalf("bad deck %v", d)
	}
	seen := map[Card]bool{}
	for _, c := range d {
		seen[c] = true
	}
	if len(seen) != 52 {
		t.Fatal("duplicates")
	}
}

func TestIDRoundTrip(t *testing.T) {
	for _, c := range Deck() {
		got, err := ParseCard(c.ID())
		if err != nil || got != c {
			t.Fatalf("%v: %v %v", c, got, err)
		}
	}
	if MustParseCard("5H").ID() != "5H" || MustParseCard("TS").ID() != "TS" {
		t.Fatal("ids")
	}
}

func TestParse(t *testing.T) {
	for in, want := range map[string]string{" 5h ": "5H", "10d": "TD", "10S": "TS", "ac": "AC", "\tkc\n": "KC"} {
		c, err := ParseCard(in)
		if err != nil || c.ID() != want {
			t.Errorf("%q: got %v %v want %s", in, c, err, want)
		}
	}
	for _, in := range []string{"", "1H", "0H", "11H", "5X", "5", "55H", "10", "T", "HH", "5HH", "AA"} {
		if _, err := ParseCard(in); err == nil {
			t.Errorf("%q should fail", in)
		}
	}
}

func TestValue(t *testing.T) {
	want := map[string]int{"AH": 1, "5H": 5, "TH": 10, "JH": 10, "QH": 10, "KH": 10}
	for id, v := range want {
		if got := MustParseCard(id).Value(); got != v {
			t.Errorf("%s: %d", id, got)
		}
	}
}

func TestHandSortedAndRest(t *testing.T) {
	h := MustParseHand("KS", "5C", "5H", "AD", "5S", "5D")
	got := h.Sorted().IDs()
	want := []string{"AD", "5H", "5D", "5C", "5S", "KS"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("got %v want %v", got, want)
		}
	}
	if h[0].ID() != "KS" {
		t.Fatal("Sorted mutated receiver")
	}
	if r := RestOfDeck(h); len(r) != 46 || r[0].ID() != "AH" || r.Contains(h[0]) {
		t.Fatal("rest of deck")
	}
	if h.Total() != 10+5+5+1+5+5 {
		t.Fatal("total")
	}
	h2, ok := h.Remove(MustParseCard("5H"))
	if !ok || len(h2) != 5 || h2.Contains(MustParseCard("5H")) || len(h) != 6 {
		t.Fatal("remove")
	}
	if _, ok := h2.Remove(MustParseCard("5H")); ok {
		t.Fatal("remove missing")
	}
}

func TestParseHandError(t *testing.T) {
	if _, err := ParseHand([]string{"5H", "zz"}); err == nil {
		t.Fatal("want error")
	}
}
