# viva-showcase

[![workspace-ci](https://github.com/vivarium-collective/viva-showcase/actions/workflows/workspace-ci.yml/badge.svg)](https://github.com/vivarium-collective/viva-showcase/actions/workflows/workspace-ci.yml)

Showcase of the viva ecosystem's simulators — one investigation per simulator
demonstrating basic functionality.

Each simulator is a standalone **engine-provider** package that lives in its own
repository. This workspace holds only the **investigation content** — one
investigation per simulator, each with one or more studies that exercise that
simulator's composites. Every `study.yaml` pins the simulator it ran against
(`simulator: {package, ref, registry}`), and the simulators are installed from
those pins (PyPI or git tag), so every result is reproducible against an exact
simulator version.

## Investigations (one per simulator)

| Investigation | Simulator | Pin | What it shows |
|---|---|---|---|
| `tellurium` | [viva-tellurium](https://github.com/vivarium-collective/viva-tellurium) (`viva_tellurium`) | `==0.2.4` (PyPI) | SBML / RoadRunner ODE simulation — decay and steady-state |
| `lammps` | [viva-lammps](https://github.com/vivarium-collective/viva-lammps) (`pbg_lammps`) | `0.1.1` (git) | Lennard-Jones NVE molecular dynamics |
| `readdy` | [viva-readdy](https://github.com/vivarium-collective/viva-readdy) (`pbg_readdy`) | `0.1.0` (git) | Particle reaction–diffusion |
| `mem3dg` | [viva-mem3dg](https://github.com/vivarium-collective/viva-mem3dg) (`pbg_mem3dg`) | `0.1.1` (git) | Membrane mechanics — demo, deflation, patch |
| `grammar` | [viva-grammar](https://github.com/vivarium-collective/viva-grammar) (`viva_grammar`) | `0.1.0` (git) | Cell-behavior grammar as a pluggable rule engine (hypoxia → motility) |

## Layout

```
investigations/
  <sim>/
    investigation.yaml
    studies/
      <slug>/
        study.yaml        # pins the simulator under `simulator:`
        viz/...           # rendered visualizations + report cards
```

This is the workbench's native nested layout — studies at
`investigations/<sim>/studies/<slug>/` are discovered automatically; no `layout:`
map is needed in `workspace.yaml`.

## Run / browse

```bash
uv sync                 # installs the pinned simulators + workbench + discovery-engine
vivarium-workbench serve --workspace .   # browse the investigations, studies, and results
```

Some simulators wrap heavy native engines (LAMMPS, ReaDDy, Mem3DG). Their Python
packages install and their composites resolve from the pins above; **running** a
study additionally needs that simulator's engine installed (see each simulator's
repo for engine setup).

## Relationship to the simulators

Each simulator package is reused across the ecosystem and is kept 100% intact; only
its demo studies/investigations moved here (the inverted sim/studies split, as with
`viva-munk` / `viva-munk-studies` and `viva-cpm` / `viva-cpm-studies`). The
simulators stay the engine-providers; this workspace *uses* them, pinned per study.
