#!/usr/bin/env python3
"""Showcase run: single-species exponential decay integrated by AMICI (CVODES).

Resolves the real registered composite
`pbg_amici.composites.exponential_decay.amici_exponential_decay`, builds it
against a process-bigraph core, and runs the genuine AMICI backend: AMICI
translates the Antimony model to C++, compiles a native extension on first run,
and CVODES integrates it. Emits the state A each tick.

Derived acceptance scalar:
  decay_rel_err = |A(T) - A0*exp(-k*T)| / (A0*exp(-k*T))   (expect < 0.01)
Also checks the trajectory is strictly monotone decreasing.

No fabricated values — everything printed is what AMICI returns. First run
triggers a C++ compile (needs a working C/C++ toolchain).

    python investigations/amici/studies/exponential-decay/sims/run.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from process_bigraph import Composite, allocate_core, gather_emitter_results
from process_bigraph.composite_spec import get as get_spec

import pbg_amici.composites.exponential_decay  # noqa: F401  (registers the generator)

COMPOSITE_ID = "pbg_amici.composites.exponential_decay.amici_exponential_decay"
TOTAL_TIME = 5.0


def main() -> int:
    core = allocate_core()
    spec = get_spec(COMPOSITE_ID)
    if spec is None:
        raise SystemExit(f"composite not registered: {COMPOSITE_ID}")
    doc = spec.to_document(core=core)
    k = float(doc["stores"]["parameters"]["k"])
    a0 = float(doc["stores"]["states"]["A"])

    sim = Composite({"state": doc}, core=core)
    sim.run(TOTAL_TIME)

    rows = gather_emitter_results(sim)[("emitter",)]
    series = [(float(r.get("time", i)), float(r["states"]["A"]))
              for i, r in enumerate(rows) if r.get("states")]
    times = [t for t, _ in series]
    a_vals = [a for _, a in series]

    t_final, a_final = series[-1]
    analytic = a0 * math.exp(-k * t_final)
    decay_rel_err = abs(a_final - analytic) / analytic if analytic else float("nan")
    monotone = all(a_vals[i] > a_vals[i + 1] for i in range(len(a_vals) - 1))

    out = {
        "composite": COMPOSITE_ID,
        "k": k,
        "A0": a0,
        "trajectory": [[round(t, 3), a] for t, a in series],
        "A_final": a_final,
        "analytic_A_final": analytic,
        "derived": {
            "decay_rel_err": decay_rel_err,
            "monotone_decreasing": monotone,
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    results_path = Path(__file__).with_name("results.json")
    results_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
