# Paid run (local estimate, not a billing cap)

This is not a second experiment. `controlled_ai.live` still owns cells,
reachability, honest-pay, transcripts, and checkpoints. The reservation
ledger is a single-use spend permit in front of each HTTP request.

## Why this exists

A paid cell can issue several model calls across the episode horizon.
Checking `cap_usd` after the cell overshoots. A response with no usage
field can also be treated as free unless the reservation is retained.

The control thesis already requires a current permit before a consequential
action leaves the machine. Money is one of those actions.

## What the ledger does

1. Before `transport.post`, reserve a conservative estimate from the pinned
   Luna/Haiku rate card. Input tokens are padded. Cache discounts are never
   assumed.
2. After a 200 with token usage, settle to the actual estimate and release
   unused reserve.
3. If usage is missing, the HTTP call fails, or the served model is rejected,
   keep the reservation and block later requests.
4. `cap_usd <= 0` is a hard stop: no actor is built and no transport is used.
5. A local `fcntl` lock and a fresh output path stop two processes from
   writing the same paid report.

These numbers are not the provider invoice.

## Commands

Dry rehearsal, no keys:

```sh
python3 -m controlled_ai.live --dry-run --episodes 16 --cap-usd 1.00
```

Fake transport through the real client (still needs the two live flags):

```sh
export CONTROLLED_AI_ENABLE_NETWORK=1
export CONTROLLED_AI_VALIDATE_PROVIDER_WIRE=1
python3 -m controlled_ai.live --provider anthropic --fake-transport --episodes 4 --cap-usd 0.50
```

Bounded paid wrapper (default cap $0.50, refuses to overwrite):

```sh
python3 -m controlled_ai.pilot --provider anthropic --episodes 4 --cap-usd 0.50
```

`--force` overwrites an existing `--out`. `--lock` defaults to
`reports/live-run.lock`. `--max-requests` bounds HTTP tickets separately
from the dollar cap.

## What this is not

- Not a measurement of a frontier model outside this finite environment.
- Not a claim that the local estimate matches the bill.
- Not enabled in ordinary CI. The optional paid workflow is manual and starts
  with the offline suite.
- Not a replacement for the finite solver, certificates, or rule monitor.
