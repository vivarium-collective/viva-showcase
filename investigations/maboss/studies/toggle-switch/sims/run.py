#!/usr/bin/env python3
"""Showcase run: a two-node stochastic MaBoSS Boolean network (cmaboss).

Resolves the real registered composite
`viva_maboss.composites.toggle.maboss_toggle_switch`, builds it against the
viva-maboss core, and runs the genuine MaBoSS engine (cmaboss) a fixed number of
coupling intervals. Node A is activated by B; node B is repressed by A. The
composite re-samples the joint state each interval and emits each node's Boolean
state and its ensemble on-probability.

Derived acceptance scalars (time-averaged over the last 10 intervals):
  settle_A, settle_B  = mean ensemble on-probability of A, B
Expected: both settle in [0.3, 0.7] — neither node locks to 0 or 1. (This network
is a 4-state limit cycle, so the signature is bounded ~0.5 marginals, not
bistability or anti-correlation.)

No fabricated values — everything printed is what MaBoSS returns (seed-set, so
reproducible).

    python investigations/maboss/studies/toggle-switch/sims/run.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results
from process_bigraph.composite_spec import get as get_spec

from viva_maboss.core import build_core
import viva_maboss.composites.toggle  # noqa: F401  (registers the generator)

COMPOSITE_ID = "viva_maboss.composites.toggle.maboss_toggle_switch"
N_INTERVALS = 30
TAIL = 10


def main() -> int:
    core = build_core()
    spec = get_spec(COMPOSITE_ID)
    if spec is None:
        raise SystemExit(f"composite not registered: {COMPOSITE_ID}")
    doc = spec.to_document(core=core)
    sim = Composite({"state": doc}, core=core)
    sim.run(N_INTERVALS)

    rows = gather_emitter_results(sim)[("emitter",)]
    probs = [r.get("node_probabilities", {}) for r in rows if r.get("node_probabilities")]
    tail = probs[-TAIL:] if len(probs) >= TAIL else probs

    def _mean(node):
        vals = [float(p[node]) for p in tail if node in p]
        return sum(vals) / len(vals) if vals else float("nan")

    settle_a, settle_b = _mean("A"), _mean("B")

    out = {
        "composite": COMPOSITE_ID,
        "n_intervals": N_INTERVALS,
        "emitted_rows": len(rows),
        "final_on_probability": probs[-1] if probs else {},
        "derived": {
            "settle_A": settle_a,
            "settle_B": settle_b,
            "tail_intervals_averaged": len(tail),
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    results_path = Path(__file__).with_name("results.json")
    results_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
