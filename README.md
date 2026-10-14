# Lemon Balm Corrosion Inhibitor — Headless Reproducibility Pipeline

A Docker-first, command-line workflow for auditing and reimplementing computational methods from:

> Asadi et al. (2018), “Utilizing Lemon Balm extract as an effective green corrosion inhibitor for mild steel in 1M HCl solution: A detailed experimental, molecular dynamics, Monte Carlo and quantum mechanics study,” *Journal of the Taiwan Institute of Chemical Engineers*. https://doi.org/10.1016/j.jtice.2018.07.011

## Design goals

- **Headless only:** command-line tools; no GUI application is required.
- **Containerized:** Docker/Compose provides a reproducible runtime.
- **Auditable:** settings, software versions, logs, and generated outputs are kept separate.
- **Scientifically transparent:** open-source alternatives are not presented as numerically identical to the commercial software used in the paper.
- **Machine-readable outputs:** summaries are written as JSON and future numerical results as CSV; figures should be saved directly to files.

## Status

This repository is an **initial scaffold**, not a completed scientific reproduction. The `audit` and `test` commands are implemented. The `qm`, `surface`, `md`, `analysis`, and `all` stages are intentionally marked as not implemented until their scientific inputs and methods are validated.

## Quick start

From the repository root, with Docker Engine and Docker Compose installed:

```bash
docker compose build
docker compose run --rm reproduce audit
docker compose run --rm reproduce test
```

The audit writes:
- `results/software_manifest.json`: platform and detected tool versions
- `results/config_snapshot.json`: a snapshot of the active YAML configuration

The audit does **not** claim to reproduce scientific results.

Planned commands, once those stages are implemented and validated:

```bash
docker compose run --rm reproduce qm
docker compose run --rm reproduce surface
docker compose run --rm reproduce md
docker compose run --rm reproduce analysis
docker compose run --rm reproduce all
```

## Paper-specific scope

The article describes calculations on caryophyllene, germacrene, citral, luteolin, chlorogenic acid, and rosmarinic acid, including neutral and protonated forms. It reports quantum chemistry, Fukui indices, Fe(110) adsorption calculations, and molecular dynamics.

The paper reports Gaussian 09 and Materials Studio components (DMol3, Adsorption Locator, and Forcite/COMPASS). These are proprietary and are **not bundled** in this repository. The current plan uses command-line open-source tools such as xTB, ASE, and LAMMPS where scientifically appropriate. These alternatives are not automatically equivalent to the original methods.

In particular, installing LAMMPS is not enough to validate an MD simulation: the force-field parameters and cross-interactions for Fe, inhibitor molecules, water, and acidic solution must be justified before production runs.

## Layout

```text
config/          YAML configuration and documented assumptions
docs/            reproduction specification, methods, software/licensing notes
src/             headless command-line pipeline
structures/      molecular/surface inputs and provenance notes
paper_data/      transcribed or digitized paper data, with source notes
tests/           configuration and workflow tests
results/         generated outputs (not committed by default)
```

## Reproducibility rules

1. Keep source inputs unchanged; save transformed structures and datasets separately.
2. Record calculation settings and software versions.
3. Do not call an open-source surrogate the same method as a proprietary implementation.
4. Store random seeds for stochastic workflows where supported.
5. Compare only quantities with consistent definitions, units, reference states, charge, and protonation.
6. Keep large trajectories and intermediate files out of Git unless intentionally needed; use Git LFS or an external archive if necessary.
7. Document unresolved details rather than silently filling gaps with defaults.

## Documentation

- [Reproduction specification](docs/REPRODUCTION_SPEC.md)
- [Methods plan](docs/METHODS.md)
- [Software and licensing](docs/SOFTWARE.md)
- [Paper configuration](config/paper.yaml)

## Citation

Please cite the source article when using this workflow. Repository citation metadata is in [CITATION.cff](CITATION.cff).
