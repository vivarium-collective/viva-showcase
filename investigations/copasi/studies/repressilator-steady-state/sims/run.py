#!/usr/bin/env python3
"""Showcase run: COPASI steady-state solve of the bundled Elowitz repressilator.

Builds `viva_copasi.composites.steady-state` (CopasiSteadyStateStep wired to the
bundled repressilator, BioModels BIOMD0000000012), runs the real COPASI solver
through basico, and reports the emitted species concentrations + reaction fluxes
and the two derived acceptance scalars:

  protein_mrna_ratio_abs_err  = max over genes |protein/mRNA - 100|   (expect < 1e-6)
  species_symmetry_abs_err    = max spread among {X,Y,Z} and {PX,PY,PZ} (expect < 1e-6)

Reproduces the numbers cited in study.yaml. No fabricated values: everything
printed is what COPASI returns.

    python investigations/copasi/studies/repressilator-steady-state/sims/run.py
"""
from __future__ import annotations

import json
from pathlib import Path

from viva_copasi.composites import build_composite


def _scalar(v):
    """COPASI emits each value as a single-element list; coerce to float."""
    if isinstance(v, (list, tuple)):
        return float(v[-1]) if v else float("nan")
    return float(v)


def _results(sim) -> dict:
    """Pull the steady-state results dict out of the composite state."""
    ss = sim.state.get("ss_stores", {}) or {}
    res = ss.get("results", {}) or {}
    if not res:
        # Fall back to the emitter if the store was consumed.
        try:
            from process_bigraph import gather_emitter_results
            rows = gather_emitter_results(sim).get(("emitter",), [])
            if rows:
                res = rows[-1].get("results", rows[-1]) or {}
        except Exception:
            pass
    return res


def main() -> int:
    sim = build_composite("steady-state")
    sim.run(1.0)
    res = _results(sim)

    species = {k: _scalar(v) for k, v in (res.get("species_concentrations", {}) or {}).items()}
    fluxes = {k: _scalar(v) for k, v in (res.get("fluxes", {}) or {}).items()}

    # Split mRNA (X,Y,Z) from protein (PX,PY,PZ): a protein is an mRNA key with a
    # "P" prefix. This matches the bundled repressilator's SBML species IDs.
    proteins = {k: v for k, v in species.items() if k.startswith("P") and k[1:] in species}
    ratio_errs = [abs(proteins[p] / species[p[1:]] - 100.0)
                  for p in proteins if species.get(p[1:], 0.0)]
    protein_mrna_ratio_abs_err = max(ratio_errs) if ratio_errs else float("nan")

    mrna_vals = [species[k] for k in species if not k.startswith("P")]
    prot_vals = list(proteins.values())
    spreads = []
    if mrna_vals:
        spreads.append(max(mrna_vals) - min(mrna_vals))
    if prot_vals:
        spreads.append(max(prot_vals) - min(prot_vals))
    species_symmetry_abs_err = max(spreads) if spreads else float("nan")

    out = {
        "composite": "viva_copasi.composites.steady-state",
        "species_concentrations": species,
        "fluxes": fluxes,
        "derived": {
            "protein_mrna_ratio_abs_err": protein_mrna_ratio_abs_err,
            "species_symmetry_abs_err": species_symmetry_abs_err,
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    results_path = Path(__file__).with_name("results.json")
    results_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
