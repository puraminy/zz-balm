# Environment review — 2026-11-17

## Scope and outcome

Project changes address the observed LAMMPS loader incompatibility and incorrect xTB version reporting. Local unit tests pass. Docker access now works using the existing docker group via `sg docker`; the tool shell retained its old supplementary groups. Docker Hub access returned HTTP 403. The official GHCR replacement tag was verified, but its pull and the rebuild were stopped at the user’s request because downloads were taking time. The proposed Ubuntu 24.04 runtime is not yet validated.

No scientific settings, molecular inputs, or unfinished scientific workflows were changed. No host packages, networking, Docker daemon settings, volumes, or unrelated images were changed. Nothing was committed or pushed.

## Findings

The previous generated container manifest recorded Python 3.11.18 and glibc 2.35. Its LAMMPS entry was:

```text
lmp: /lib/x86_64-linux-gnu/libm.so.6: version `GLIBC_2.38' not found (required by /opt/conda/bin/../lib/liblammps.so.0)
```

The installed LAMMPS library therefore required a newer glibc than the Ubuntu 22.04 runtime supplied. This occurs before simulation inputs are processed. The exact installed Conda build was not recorded in the old manifest and cannot be inspected without Docker access.

The xTB entry contained only a separator line. The audit selected the first output line rather than finding the version in the banner. This establishes a reporting defect, not a failed xTB calculation.

The old audit ignored exit codes and used the same `--version` argument for every tool. LAMMPS documents `-help` for displaying its banner and compiled capabilities: <https://docs.lammps.org/stable/Run_options.html>.

## Changes

- `Dockerfile`: switch from `mambaorg/micromamba:2.9.0-ubuntu22.04` to `ghcr.io/mamba-org/micromamba:2.9.0-ubuntu24.04`, whose glibc 2.39 satisfies the observed GLIBC_2.38 requirement. Use strict channel priority. Run the complete test suite during image construction with `ZZ_BALM_REQUIRE_ENGINES=1`; missing engines or failed version/smoke checks must fail the build. Preserve the Python entrypoint and existing headless defaults.
- `environment.yml`: add `nodefaults` to keep dependencies in the declared conda-forge channel. Preserve Python 3.11 and the existing scientific dependencies. No speculative package-version pins or glibc overrides were introduced. This is not a fully locked environment; actual package selection remains subject to the solver.
- `src/cli.py`: probe xTB with `--version` and LAMMPS with `-help`; extract recognizable version text from both output streams. Distinguish missing executables, timeouts, nonzero exits, OS errors, and unrecognized output. Save bounded diagnostic output for failed subprocesses. Write both reports even when tools fail, and return exit code 1 for an unsuccessful audit.
- `tests/test_audit.py`: cover banner parsing, stderr versions, nonzero exits even with a recognizable banner, malformed output, missing binaries, permission errors, timeouts, and successful/failed report generation.
- `tests/test_engines.py`: require parseable engine versions and run a small GFN2-xTB water single-point calculation and a zero-step LAMMPS Lennard-Jones system in temporary directories. These are installation checks, not validation of the paper's methods or force fields. Missing engines skip on a development host; `ZZ_BALM_REQUIRE_ENGINES=1` makes them mandatory in the image build.
- `results/software_manifest.json` and `results/config_snapshot.json`: regenerated inside the cached project container using the current audit source. These files remain ignored by Git. The manifest records Python 3.11.18, glibc 2.35, xTB 6.7.1 with status `ok`, and the LAMMPS GLIBC_2.38 loader failure with overall status `error`. This is a diagnostic report from the old image, not a validation of the proposed image. The scientific configuration snapshot is unchanged in content.

The existing uncommitted `docker-compose.yml` setting `user: "1000:1000"` was preserved without edits.

## Audit format

The manifest now has `schema_version: 2` and an overall `status` (`ok` or `error`). Each `tools` value is a structured object rather than the old string, with command, status, version, and return code. Failed probes include an error and, where available, captured diagnostics. Consumers of the old string values must migrate to `tools.<name>.version` and check status. Audit exit code 0 means every required version probe succeeded; it does not certify scientific correctness.

## Validation performed

Earlier host validation: `python3 -m pytest -q` reported **12 passed, 2 skipped** (engines absent on host).

Actual Docker validation on 2026-11-17:

- Docker daemon accessible with `sg docker -c 'docker info'` (server 29.9.2); no host settings changed.
- `docker pull mambaorg/micromamba:2.9.0-ubuntu24.04` and the first `docker compose build --progress=plain` failed with HTTP 403 from Docker Hub. This is an access failure, not evidence that the tag does not exist.
- The official Micromamba repository lists GHCR as an image source: <https://github.com/mamba-org/micromamba-docker>. `docker manifest inspect ghcr.io/mamba-org/micromamba:2.9.0-ubuntu24.04` succeeded, including Linux amd64 support. BuildKit resolved index digest `sha256:bfc0f36a36c69c2e6c7b6e57a264820cb978ce086b5790d7f0c86299372f67a5`; amd64 manifest digest is `sha256:d2e0e61f931418c4242b8da2e9284a18f2cedcfeeab888dcef72a13be445aebd`.
- GHCR pull downloaded several layers. The second `docker compose build --progress=plain` resolved the base image but was still acquiring layers when stopped at the user's request. Package installation and build-time tests were not reached. Full pull completion is not verified.
- Cached project image tested: `sha256:977d0bb8749ab7b4a86a941e03e116626d3fbb4e6071d2b39ff28ede5c46dc8e`. Current `src/` and `tests/` were mounted read-only at `/work/src` and `/work/tests` to test the existing changes against its actual installed engines.
- Container audit: exit **1**, both reports successfully written through the results bind mount. xTB version correctly parsed as **6.7.1**, probe exit **0**. LAMMPS probe exit **1**, version unavailable due to `GLIBC_2.38 not found` in the old glibc 2.35 runtime.
- Full container suite with `ZZ_BALM_REQUIRE_ENGINES=1`: **13 passed, 1 failed**. Only the LAMMPS smoke test failed. Two harmless pytest cache permission warnings occurred because `/work` in the old image is not writable by UID 1000.
- Separate minimal engine tests with pytest cache disabled: **1 passed, 1 failed**. GFN2-xTB water single-point calculation succeeded and emitted `TOTAL ENERGY`; LAMMPS failed at its loader/version probe before its zero-step calculation.
- `docker compose config --quiet` and `git diff --check`: passed.

No scientific configuration, molecular input, or unfinished workflow was changed. No host packages, networking, Docker daemon configuration, or unrelated Docker resources were changed. Nothing was committed or pushed.

## Complete locally

The user requested that time-consuming installation be left to them. Run from the project directory in the shell where Docker already works:

```bash
docker pull ghcr.io/mamba-org/micromamba:2.9.0-ubuntu24.04
docker compose build --progress=plain
```

Continue only if the build succeeds. The Dockerfile runs the full suite, including both mandatory engine smoke tests, during the build. Then run:

```bash
docker compose run --rm -e ZZ_BALM_REQUIRE_ENGINES=1 -e PYTEST_ADDOPTS="-p no:cacheprovider" reproduce test
docker compose run --rm -e ZZ_BALM_REQUIRE_ENGINES=1 --entrypoint python reproduce -m pytest -q -p no:cacheprovider tests/test_engines.py
docker compose run --rm reproduce audit
cat results/software_manifest.json
```

If the current shell still lacks the active group, wrap each Docker command with `sg docker -c 'COMMAND'`. Do not run validation against the old cached image after a failed build and treat it as validation of the new image.

Acceptance requires a successful build, all 14 tests passing, both engine smoke tests passing, and audit exit 0 with recognized xTB and LAMMPS versions. The audit regenerates both JSON reports inside the container. Update this review with the final runtime versions and results after completion. LAMMPS execution on Ubuntu 24.04 and complete GHCR pull/build remain unverified.
