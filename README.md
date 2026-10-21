# Cards

A collection of terminal card games.

## Development

[StackOverflow Explaination](https://stackoverflow.com/questions/6323860/sibling-package-imports)

Run the following command from root of this repo using a virtual environment (.venv).

```
python3 -m pip install -e .
python3 -m pip freeze # to verify it is installed
```

## Tests

Run the tests with the following command from the test directory

```
python3 -m unittest
```

Fuzz whole cribbage games against an independent scoring oracle (from the test directory):

```
python3 fuzz_cribbage.py --games 2000 --random-only
```

## Cribbage API

`cribbage api` speaks JSON lines so an LLM can play against the computer; see
[docs/cribbage_api.md](docs/cribbage_api.md).

## Features to Add

### Cribbage

[ ] Add hail mary and min points option to discard scoring
[ ] Add pegging value to discard scoring: https://www.cribbage.org/NewSite/tips/colvert2.asp
[ ] Training with the add star method: http://www.cribbageforum.com/YourCrib.htm
