#!/usr/bin/env python3
"""Showcase run: eQuilibrator ΔG' feasibility gate at alkaline-vent conditions.

Resolves the real registered composite
`viva_equilibrator.composites.feasibility.equilibrator_feasibility_gate`, builds
it against a process-bigraph core, and runs the genuine eQuilibrator
(component-contribution) engine to compute the transformed Gibbs free energy ΔG'
of three H2-driven reductive CO2-fixation reactions (to formate, acetate,
pyruvate) at a fixed hydrothermal-vent condition, plus a per-reaction feasibility
flag.

Derived acceptance scalars:
  max_dg          = max(dg_formate, dg_acetate, dg_pyruvate)   (expect < 0: all exergonic)
  min_feasibility = min(feasible_formate, _acetate, _pyruvate) (expect >= 0.99: gate open)

No fabricated values — everything printed is what eQuilibrator returns. The
offline cache ships with equilibrator-cache-data, so no network is required.

    python investigations/equilibrator/studies/vent-feasibility-gate/sims/run.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, allocate_core, gather_emitter_results
from process_bigraph.composite_spec import get as get_spec

import viva_equilibrator.composites.feasibility  # noqa: F401  (registers the generator)

COMPOSITE_ID = "viva_equilibrator.composites.feasibility.equilibrator_feasibility_gate"


def main() -> int:
    core = allocate_core()
    spec = get_spec(COMPOSITE_ID)
    if spec is None:
        raise SystemExit(f"composite not registered: {COMPOSITE_ID}")
    doc = spec.to_document(core=core)
    sim = Composite({"state": doc}, core=core)
    sim.run(3.0)

    last = gather_emitter_results(sim)[("emitter",)][-1]
    names = ("formate", "acetate", "pyruvate")
    dg = {n: float(last[f"dg_{n}"]) for n in names}
    feasible = {n: float(last[f"feasible_{n}"]) for n in names}

    out = {
        "composite": COMPOSITE_ID,
        "condition": "vent: pH 9.5, T 333.15 K, H2 5e-3 M, CO2 2e-3 M",
        "dg_prime_kJ_per_mol": dg,
        "feasibility": feasible,
        "derived": {
            "max_dg": max(dg.values()),
            "min_feasibility": min(feasible.values()),
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    results_path = Path(__file__).with_name("results.json")
    results_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
