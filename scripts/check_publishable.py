#!/usr/bin/env python3
"""Pre-publish lint for the read-only workbench snapshot.

The showcase publishes a *framework-only* read-only workbench (see
``.github/workflows/publish-dashboard.yml``): it installs the render framework
but NOT the pinned simulator engines (several aren't pip-buildable in CI —
pymem3dg CMake, lammps/cc3d conda). Two classes of breakage slip past that build
because it *renders committed data* and never runs a sim:

  1. **Missing viz assets.** A study's ``embed_visualizations`` (and report-card /
     comparison-plotly) URLs are iframed by the published study page. The
     publisher stages the file at ``<out>/<url>`` by copying ``<ws>/<url>`` — so
     a URL whose path doesn't match where the file actually lives (e.g. the
     ``/workspace/studies/...`` or bare ``/studies/...`` prefix instead of the
     nested ``/investigations/<inv>/studies/<slug>/viz/...`` this workspace uses)
     is silently skipped at stage time and 404s at view time. This is a pure
     file-existence check against the publisher's staging precondition, so it is
     ALWAYS doable here, with no sim installed.

  2. **Composite refs that aren't honestly simulation-deferred.** The
     framework-only render cannot resolve a sim's composite (the sim isn't
     importable), so a *resolution* check can't run here — but a *well-formedness*
     check can: every declared composite ref must be a well-formed dotted
     identifier, the study must carry a ``simulator:`` pin (the marker that an
     unresolved ref is deferred to where the sim IS installed, not broken), and a
     composite must not be referenced both bare and fully-qualified in the same
     study (that inconsistency renders as two "composite not found" banners —
     exactly the reactive-system regression this lint was added for).

Run modes (both pure-source; no build, no sim needed):

    python scripts/check_publishable.py --workspace .

Exit 0 when clean, 1 (printing every failure) otherwise. Wired into
``workspace-ci.yml`` (PR gate) and ``scripts/publish_dashboard.sh`` (publish
gate), so a broken release is caught before it goes live.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# Local, root-absolute iframe-asset URL fields a study can declare. Each names a
# file the publisher stages by copying ``<ws>/<url>`` → ``<out>/<url>``.
_EMBED_LIST_FIELDS = ("embed_visualizations", "report_card_urls")
_SCALAR_URL_FIELDS = ("comparison_plotly_url",)

# A well-formed composite ref is a dotted identifier whose segments may contain
# hyphens (registry ids derived from a ``<name>.composite.yaml`` filename legally
# do, e.g. ``pbg_caspule.composites.bond-network-demo``): ``mapk_brs`` or
# ``pbg_reactive_system.composites.mapk_brs``. No spaces, slashes or path-like
# junk — those are the malformed refs a resolution banner can't help with.
# NOTE: whether a well-formed ref actually RESOLVES to a registered composite is a
# resolution check that needs the sim installed; it runs in each sim's own CI, not
# in this framework-only, sim-absent context (see module docstring).
_REF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)*$")


def _iter_studies(ws_root: Path):
    """Yield ``(study_yaml_path, inv_slug, study_slug, spec)`` for every study."""
    for sy in sorted((ws_root / "investigations").glob("*/studies/*/study.yaml")):
        rel = sy.relative_to(ws_root / "investigations")
        inv, study = rel.parts[0], sy.parent.name
        try:
            spec = yaml.safe_load(sy.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            yield sy, inv, study, {"__yaml_error__": str(e)}
            continue
        yield sy, inv, study, spec


def _asset_urls(spec: dict):
    """Collect every local, root-absolute iframe-asset URL a study declares."""
    urls: list[str] = []
    for field in _EMBED_LIST_FIELDS:
        v = spec.get(field)
        items = v.values() if isinstance(v, dict) else (v if isinstance(v, list) else [])
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                urls.append(item["url"])
    for field in _SCALAR_URL_FIELDS:
        if isinstance(spec.get(field), str):
            urls.append(spec[field])
    return urls


def _composite_refs(spec: dict):
    """Composite refs a study DECLARES — the sites the dashboard's resolution
    lint collects: ``baseline[].composite``, ``conditions.baseline/variants[]
    .composite`` and ``simulation_set[].composite`` / ``.base_model``.

    ``conditions.variants[].base_composite`` names a *baseline by name*, not a
    registered composite, so (like the dashboard linter) it is NOT collected.
    """
    refs: list[str] = []

    def add(v):
        if isinstance(v, str) and v.strip():
            refs.append(v.strip())

    baseline = spec.get("baseline")
    for b in (baseline if isinstance(baseline, list) else [baseline]):
        if isinstance(b, dict):
            add(b.get("composite"))
    conds = spec.get("conditions")
    if isinstance(conds, dict):
        cb = conds.get("baseline")
        for b in (cb if isinstance(cb, list) else [cb]):
            if isinstance(b, dict):
                add(b.get("composite"))
        for v in conds.get("variants") or []:
            if isinstance(v, dict):
                add(v.get("composite"))
    for s in spec.get("simulation_set") or []:
        if isinstance(s, dict):
            add(s.get("composite"))
            add(s.get("base_model"))
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def check_workspace(ws_root: Path) -> list[str]:
    """Return a list of human-readable failures (empty == publishable)."""
    ws_root = Path(ws_root)
    fails: list[str] = []
    n_studies = 0

    for sy, inv, study, spec in _iter_studies(ws_root):
        where = sy.relative_to(ws_root)
        if "__yaml_error__" in spec:
            fails.append(f"{where}: YAML parse error: {spec['__yaml_error__']}")
            continue
        n_studies += 1

        # (1) viz-asset existence — the publisher's staging precondition.
        for url in _asset_urls(spec):
            if not url.startswith("/") or url.startswith(("/api/", "//")):
                # Non-local / external refs are not staged from the workspace.
                continue
            staged_src = ws_root / url.lstrip("/")
            if not staged_src.is_file():
                fails.append(
                    f"{where}: viz asset not found at the publisher staging path: "
                    f"url={url!r} -> expected file {url.lstrip('/')!r}. The embed "
                    f"URL must be the workspace-relative path to the committed file "
                    f"(e.g. /investigations/{inv}/studies/{study}/viz/<file>)."
                )

        # (1b) no committed viz figure may be a baked render-error stub. The
        # renderer writes a ``<p ...>Failed to render <code>NAME</code>: ...``
        # stub when a viz can't be dispatched, and once committed the publisher
        # copies it verbatim into the bundle, so the live study page shows a red
        # "Failed to render ...: KeyError: 'address'" block (the exact breakage
        # scaffold/stub visualizations with no `address` produced). A current
        # renderer SKIPS an unaddressable viz instead of stubbing it, so any such
        # file on disk is a STALE error baked by an older render — never
        # publishable. Delete it (a stub viz renders as its clean placeholder with
        # no committed html); fill in the viz's `address` if a real figure is
        # wanted.
        viz_dir = sy.parent / "viz"
        if viz_dir.is_dir():
            for html in sorted(viz_dir.rglob("*.html")):
                try:
                    head = html.read_text(encoding="utf-8", errors="replace")[:400]
                except OSError:
                    continue
                if head.lstrip().startswith("<p") and "Failed to render" in head:
                    fails.append(
                        f"{where.parent / 'viz' / html.relative_to(viz_dir)}: "
                        f"committed viz figure is a baked render-error stub "
                        f"(\"Failed to render\") — a stale render error that would "
                        f"publish as a red failure block. Delete it (an unaddressed "
                        f"stub viz renders as a clean placeholder) or give the viz "
                        f"an `address:` so it renders a real figure."
                    )

        # (2) composite-ref well-formedness / honest simulation-deferral.
        refs = _composite_refs(spec)
        if refs:
            sim = spec.get("simulator")
            if not isinstance(sim, dict) or not sim.get("package"):
                fails.append(
                    f"{where}: declares composite ref(s) {refs} but has no "
                    f"`simulator:` pin — an unresolved ref must be marked "
                    f"simulation-deferred by pinning the simulator that owns it."
                )
            for ref in refs:
                if not _REF_RE.match(ref):
                    fails.append(
                        f"{where}: malformed composite ref {ref!r} — expected a "
                        f"dotted identifier like pkg.composites.name."
                    )
            # Inconsistency: the same composite referenced both bare and fully
            # qualified (the bare name is the last segment of a dotted ref). This
            # renders as a duplicate "composite not found" banner.
            dotted = [r for r in refs if "." in r]
            bare = [r for r in refs if "." not in r]
            for b in bare:
                clash = [d for d in dotted if d.rsplit(".", 1)[-1] == b]
                if clash:
                    fails.append(
                        f"{where}: composite ref {b!r} is also declared fully "
                        f"qualified as {clash[0]!r} — use one canonical form "
                        f"(the fully-qualified one) for every reference."
                    )

    if n_studies == 0:
        fails.append("no studies found under investigations/*/studies/*/study.yaml")
    return fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", default=".", help="workspace root (default: .)")
    args = ap.parse_args(argv)

    ws_root = Path(args.workspace).resolve()
    fails = check_workspace(ws_root)
    if fails:
        print("READ-ONLY-WORKBENCH PUBLISHABILITY FAILURES:")
        for f in fails:
            print(" -", f)
        return 1
    n = len(list((ws_root / "investigations").glob("*/studies/*/study.yaml")))
    print(f"OK: {n} studies are read-only-workbench-publishable "
          f"(viz assets resolve; composite refs well-formed + simulation-deferred).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
