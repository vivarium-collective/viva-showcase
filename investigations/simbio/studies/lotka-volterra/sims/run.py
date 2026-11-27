#!/usr/bin/env python3
"""Showcase run: a Lotka-Volterra predator-prey oscillator integrated by simbio.

Resolves the real registered composite
`pbg_simbio.composites.crn.simbio_lotka_volterra`, builds it against a
process-bigraph core, and runs the genuine simbio ODE engine over an Antimony
predator-prey reaction network. Emits prey and predator concentrations each tick.

Derived acceptance scalars over t in [0, 40]:
  prey_min, pred_min  = minimum concentration reached (expect >= 0: bounded, no blow-down)
  prey_peaks          = number of prey local maxima above 5.0 (expect >= 2: sustained oscillation)

No fabricated values — everything printed is what simbio returns.

NOTE: simbio/poincare 1.3.0 removed the solve() kwargs this bridge uses; the
showcase pins simbio==1.1.* / poincare==1.1.* so the engine integrates.

    python investigations/simbio/studies/lotka-volterra/sims/run.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, allocate_core, gather_emitter_results
from process_bigraph.composite_spec import get as get_spec

import pbg_simbio.composites.crn  # noqa: F401  (registers the generators)

COMPOSITE_ID = "pbg_simbio.composites.crn.simbio_lotka_volterra"
TOTAL_TIME = 40.0


def _count_peaks(series, threshold):
    n = 0
    for i in range(1, len(series) - 1):
        if series[i] > threshold and series[i] >= series[i - 1] and series[i] > series[i + 1]:
            n += 1
    return n


def main() -> int:
    core = allocate_core()
    spec = get_spec(COMPOSITE_ID)
    if spec is None:
        raise SystemExit(f"composite not registered: {COMPOSITE_ID}")
    doc = spec.to_document(core=core)
    sim = Composite({"state": doc}, core=core)
    sim.run(TOTAL_TIME)

    rows = gather_emitter_results(sim)[("emitter",)]
    conc = [r.get("concentrations", {}) for r in rows if r.get("concentrations")]
    prey = [float(c["prey"]) for c in conc if "prey" in c]
    pred = [float(c["pred"]) for c in conc if "pred" in c]

    out = {
        "composite": COMPOSITE_ID,
        "total_time": TOTAL_TIME,
        "emitted_rows": len(rows),
        "prey_range": [min(prey), max(prey)] if prey else [],
        "pred_range": [min(pred), max(pred)] if pred else [],
        "derived": {
            "prey_min": min(prey) if prey else float("nan"),
            "pred_min": min(pred) if pred else float("nan"),
            "prey_peaks": _count_peaks(prey, 5.0),
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    results_path = Path(__file__).with_name("results.json")
    results_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
