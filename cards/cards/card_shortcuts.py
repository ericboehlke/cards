"""
Shortcuts for creating cards
"""

from cards.cards.card import Suit, Card, ACE, JACK, QUEEN, KING

CA = ACE_OF_CLUBS = Card(Suit.CLUBS, ACE)
C2 = TWO_OF_CLUBS = Card(Suit.CLUBS, 2)
C3 = THREE_OF_CLUBS = Card(Suit.CLUBS, 3)
C4 = FOUR_OF_CLUBS = Card(Suit.CLUBS, 4)
C5 = FIVE_OF_CLUBS = Card(Suit.CLUBS, 5)
C6 = SIX_OF_CLUBS = Card(Suit.CLUBS, 6)
C7 = SEVEN_OF_CLUBS = Card(Suit.CLUBS, 7)
C8 = EIGHT_OF_CLUBS = Card(Suit.CLUBS, 8)
C9 = NINE_OF_CLUBS = Card(Suit.CLUBS, 9)
CT = C10 = TEN_OF_CLUBS = Card(Suit.CLUBS, 10)
CJ = JACK_OF_CLUBS = Card(Suit.CLUBS, JACK)
CQ = QUEEN_OF_CLUBS = Card(Suit.CLUBS, QUEEN)
CK = KING_OF_CLUBS = Card(Suit.CLUBS, KING)

DA = ACE_OF_DIAMONDS = Card(Suit.DIAMONDS, ACE)
D2 = TWO_OF_DIAMONDS = Card(Suit.DIAMONDS, 2)
D3 = THREE_OF_DIAMONDS = Card(Suit.DIAMONDS, 3)
D4 = FOUR_OF_DIAMONDS = Card(Suit.DIAMONDS, 4)
D5 = FIVE_OF_DIAMONDS = Card(Suit.DIAMONDS, 5)
D6 = SIX_OF_DIAMONDS = Card(Suit.DIAMONDS, 6)
D7 = SEVEN_OF_DIAMONDS = Card(Suit.DIAMONDS, 7)
D8 = EIGHT_OF_DIAMONDS = Card(Suit.DIAMONDS, 8)
D9 = NINE_OF_DIAMONDS = Card(Suit.DIAMONDS, 9)
DT = D10 = TEN_OF_DIAMONDS = Card(Suit.DIAMONDS, 10)
DJ = JACK_OF_DIAMONDS = Card(Suit.DIAMONDS, JACK)
DQ = QUEEN_OF_DIAMONDS = Card(Suit.DIAMONDS, QUEEN)
DK = KING_OF_DIAMONDS = Card(Suit.DIAMONDS, KING)

SA = ACE_OF_SPADES = Card(Suit.SPADES, ACE)
S2 = TWO_OF_SPADES = Card(Suit.SPADES, 2)
S3 = THREE_OF_SPADES = Card(Suit.SPADES, 3)
S4 = FOUR_OF_SPADES = Card(Suit.SPADES, 4)
S5 = FIVE_OF_SPADES = Card(Suit.SPADES, 5)
S6 = SIX_OF_SPADES = Card(Suit.SPADES, 6)
S7 = SEVEN_OF_SPADES = Card(Suit.SPADES, 7)
S8 = EIGHT_OF_SPADES = Card(Suit.SPADES, 8)
S9 = NINE_OF_SPADES = Card(Suit.SPADES, 9)
ST = S10 = TEN_OF_SPADES = Card(Suit.SPADES, 10)
SJ = JACK_OF_SPADES = Card(Suit.SPADES, JACK)
SQ = QUEEN_OF_SPADES = Card(Suit.SPADES, QUEEN)
SK = KING_OF_SPADES = Card(Suit.SPADES, KING)

HA = ACE_OF_HEARTS = Card(Suit.HEARTS, ACE)
H2 = TWO_OF_HEARTS = Card(Suit.HEARTS, 2)
H3 = THREE_OF_HEARTS = Card(Suit.HEARTS, 3)
H4 = FOUR_OF_HEARTS = Card(Suit.HEARTS, 4)
H5 = FIVE_OF_HEARTS = Card(Suit.HEARTS, 5)
H6 = SIX_OF_HEARTS = Card(Suit.HEARTS, 6)
H7 = SEVEN_OF_HEARTS = Card(Suit.HEARTS, 7)
H8 = EIGHT_OF_HEARTS = Card(Suit.HEARTS, 8)
H9 = NINE_OF_HEARTS = Card(Suit.HEARTS, 9)
HT = H10 = TEN_OF_HEARTS = Card(Suit.HEARTS, 10)
HJ = JACK_OF_HEARTS = Card(Suit.HEARTS, JACK)
HQ = QUEEN_OF_HEARTS = Card(Suit.HEARTS, QUEEN)
HK = KING_OF_HEARTS = Card(Suit.HEARTS, KING)

card_shortcut_dict = {
    "10C": C10,
    "10D": D10,
    "10S": S10,
    "10H": H10,
    "AC": CA,
    "2C": C2,
    "3C": C3,
    "4C": C4,
    "5C": C5,
    "6C": C6,
    "7C": C7,
    "8C": C8,
    "9C": C9,
    "TC": CT,
    "JC": CJ,
    "QC": CQ,
    "KC": CK,
    "AD": DA,
    "2D": D2,
    "3D": D3,
    "4D": D4,
    "5D": D5,
    "6D": D6,
    "7D": D7,
    "8D": D8,
    "9D": D9,
    "TD": DT,
    "JD": DJ,
    "QD": DQ,
    "KD": DK,
    "AS": SA,
    "2S": S2,
    "3S": S3,
    "4S": S4,
    "5S": S5,
    "6S": S6,
    "7S": S7,
    "8S": S8,
    "9S": S9,
    "TS": ST,
    "JS": SJ,
    "QS": SQ,
    "KS": SK,
    "AH": HA,
    "2H": H2,
    "3H": H3,
    "4H": H4,
    "5H": H5,
    "6H": H6,
    "7H": H7,
    "8H": H8,
    "9H": H9,
    "TH": HT,
    "JH": HJ,
    "QH": HQ,
    "KH": HK,
}
