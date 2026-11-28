"""Tests for scripts/check_publishable.py — the pre-publish read-only-workbench lint.

The lint guards the framework-only published snapshot against the two breakages
that slip past a sim-less render: viz assets that 404 (wrong staging path) and
composite refs that aren't honestly simulation-deferred. These tests pin both the
pass path (a well-formed study) and each failure the lint must catch — including
the exact two regressions it was written for (the ``/workspace/studies/...`` embed
URL that 404s, and the bare-vs-qualified composite ref that double-banners).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

_LINT = Path(__file__).resolve().parents[1] / "scripts" / "check_publishable.py"
_spec = importlib.util.spec_from_file_location("check_publishable", _LINT)
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)


def _write_study(ws: Path, inv: str, slug: str, spec: dict, viz: dict | None = None):
    sdir = ws / "investigations" / inv / "studies" / slug
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "study.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    for name, body in (viz or {}).items():
        vdir = sdir / "viz"
        vdir.mkdir(exist_ok=True)
        (vdir / name).write_text(body, encoding="utf-8")
    return sdir


def _good_spec(inv: str, slug: str) -> dict:
    return {
        "name": slug,
        "simulator": {"package": "viva-demo", "ref": "0.1.0", "registry": "git"},
        "conditions": {
            "baseline": {"name": slug, "composite": "pbg_demo.composites.demo"},
        },
        "simulation_set": [
            {"name": f"{slug}-baseline", "base_model": "pbg_demo.composites.demo"},
        ],
        "embed_visualizations": [
            {"name": "fig", "url": f"/investigations/{inv}/studies/{slug}/viz/fig.html"},
        ],
    }


def test_clean_study_passes(tmp_path):
    _write_study(tmp_path, "demo", "demo-study", _good_spec("demo", "demo-study"),
                 viz={"fig.html": "<html>ok</html>"})
    assert cp.check_workspace(tmp_path) == []


def test_missing_viz_asset_wrong_prefix_fails(tmp_path):
    # The exact symptom #2 regression: a /workspace/studies/... embed URL whose
    # file actually lives under investigations/<inv>/studies/<slug>/viz/.
    spec = _good_spec("demo", "demo-study")
    spec["embed_visualizations"][0]["url"] = "/workspace/studies/demo-study/viz/fig.html"
    _write_study(tmp_path, "demo", "demo-study", spec, viz={"fig.html": "<html>ok</html>"})
    fails = cp.check_workspace(tmp_path)
    assert any("viz asset not found" in f and "/workspace/studies/" in f for f in fails), fails


def test_bare_slash_studies_prefix_also_fails(tmp_path):
    # The fenics-style /studies/<slug>/viz/... prefix is likewise unstageable.
    spec = _good_spec("demo", "demo-study")
    spec["embed_visualizations"][0]["url"] = "/studies/demo-study/viz/fig.html"
    _write_study(tmp_path, "demo", "demo-study", spec, viz={"fig.html": "<html>ok</html>"})
    fails = cp.check_workspace(tmp_path)
    assert any("viz asset not found" in f for f in fails), fails


def test_bare_vs_qualified_composite_ref_double_banner_fails(tmp_path):
    # The exact symptom #1 regression: simulation_set mixes the fully-qualified
    # ref with a bare one -> two "composite not found" banners.
    spec = _good_spec("demo", "demo-study")
    spec["simulation_set"].append({"name": "variant", "base_model": "demo"})
    _write_study(tmp_path, "demo", "demo-study", spec, viz={"fig.html": "<html>ok</html>"})
    fails = cp.check_workspace(tmp_path)
    assert any("is also declared fully qualified" in f for f in fails), fails


def test_composite_ref_without_simulator_pin_fails(tmp_path):
    spec = _good_spec("demo", "demo-study")
    del spec["simulator"]
    _write_study(tmp_path, "demo", "demo-study", spec, viz={"fig.html": "<html>ok</html>"})
    fails = cp.check_workspace(tmp_path)
    assert any("no `simulator:` pin" in f for f in fails), fails


def test_malformed_composite_ref_fails(tmp_path):
    spec = _good_spec("demo", "demo-study")
    spec["conditions"]["baseline"]["composite"] = "pbg demo/composites bad"
    _write_study(tmp_path, "demo", "demo-study", spec, viz={"fig.html": "<html>ok</html>"})
    fails = cp.check_workspace(tmp_path)
    assert any("malformed composite ref" in f for f in fails), fails


def test_hyphenated_composite_ref_is_well_formed(tmp_path):
    # Registry ids from a <name>.composite.yaml filename legally contain hyphens.
    spec = _good_spec("demo", "demo-study")
    spec["conditions"]["baseline"]["composite"] = "pbg_demo.composites.bond-network-demo"
    spec["simulation_set"][0]["base_model"] = "pbg_demo.composites.bond-network-demo"
    _write_study(tmp_path, "demo", "demo-study", spec, viz={"fig.html": "<html>ok</html>"})
    assert cp.check_workspace(tmp_path) == []


def test_committed_render_error_stub_fails(tmp_path):
    # The exact symptom the user hit: a committed viz/<name>.html that is a baked
    # "Failed to render ...: KeyError: 'address'" stub (a stale error from an older
    # renderer) publishes as a red failure block on the live study page.
    stub = ('<p style="color:#991b1b">Failed to render '
            "<code>demo-study-world</code>: <code>KeyError: 'address'</code></p>")
    _write_study(tmp_path, "demo", "demo-study", _good_spec("demo", "demo-study"),
                 viz={"fig.html": "<html>ok</html>",
                      "demo-study-world.html": stub})
    fails = cp.check_workspace(tmp_path)
    assert any("baked render-error stub" in f and "demo-study-world.html" in f
               for f in fails), fails


def test_real_figure_mentioning_failed_to_render_passes(tmp_path):
    # A real figure is not a stub just because its text contains the words — the
    # check keys on the error-stub shape (a leading <p> whose head says "Failed to
    # render"), so narrative prose about rendering must not trip it.
    fig = ("<html><body><h1>Render benchmark</h1>"
           "<p>None of the runs Failed to render.</p></body></html>")
    _write_study(tmp_path, "demo", "demo-study", _good_spec("demo", "demo-study"),
                 viz={"fig.html": fig})
    assert cp.check_workspace(tmp_path) == []


def test_empty_workspace_fails(tmp_path):
    (tmp_path / "investigations").mkdir()
    fails = cp.check_workspace(tmp_path)
    assert any("no studies found" in f for f in fails), fails


def test_real_workspace_is_publishable():
    # The committed showcase workspace must itself pass (guards against a future
    # study reintroducing either regression).
    ws = Path(__file__).resolve().parents[1]
    assert cp.check_workspace(ws) == []
