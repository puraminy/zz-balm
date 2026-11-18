# QM preflight (schema version 1)

`python -m src.cli qm --preflight` validates inputs and atomically writes
`results/qm/preflight.json`. It never invokes engines, prepares geometries,
optimizes structures, or parses computational results. `qm` without
`--preflight` remains unimplemented. Exit 0 means all mandatory checks pass;
fatal errors return 1. Warnings require scientific review but do not change
the exit status. Input consistency is not scientific validation.

## Required inputs

`config/qm.yaml` intentionally contains unresolved null values and fails
preflight. Null is never an engine default. All six configured study molecules
need records; there is no automatic neutral/protonated expansion or job creation.
Multiple records per molecule are allowed with unique molecule/state ID pairs.

Each record requires:

- `molecule_id` matching `paper.yaml`; explicit `state_id`, `protonation_state_id`,
  and `conformer_id` strings.
- `input_file`: repository-relative XYZ path (absolute paths also accepted).
  Inputs remain unchanged and atom order is preserved.
- `coordinate_units: angstrom`: an external declaration, not inferred from XYZ
  or converted. The file's comment line is not a unit authority.
- Integer `charge` and integer `multiplicity >= 1`. Neither has a default;
  booleans, numeric strings, and floats are rejected. Only closed-shell singlets
  are accepted in this phase.
- `identity` containing nonempty `molecule_id`, `chemical_name`, `source`,
  `isomer_identifier`, `connectivity_reference`, `protonation_description`,
  and `protonation_site`. Identity molecule ID must match the record.

Use retrievable provenance and reviewed SDF/MOL or equivalent connectivity
references. Site descriptions should identify atoms using original input
numbering. For neutral species use `protonation_state_id: neutral` and, where
appropriate, `protonation_site: not_applicable`. All other state IDs require an
explicit site description. If stereochemistry is inapplicable, explain that
explicitly in the isomer identifier. Do not replace unknown metadata with
arbitrary text to bypass validation.

Presence of metadata is checked; truth of chemical identity, referenced
connectivity, stereochemistry, and protonation assignments is not automatically
verified. XYZ alone never establishes identity. No study molecule is supplied.

Charge/spin validation checks `Ne = sum(Zi) - charge > 0`,
`u = multiplicity - 1`, `0 <= u <= Ne`, and even `Ne - u`. It does not establish
a ground spin state. Geometry failures block electron-count validation.

## Protocol schema

Method must be `GFN2-xTB`. Explicit solvent choices are `model: none` with null
`solvent` and `reference_state`, or `model: ALPB`, `solvent: water`, and reference
state `gsolv`, `reference`, or `bar1M`. ALPB is not Gaussian PCM or a model of
1 M HCl. No solvent choice is made in the template.

Future settings require an explicit optimization level
(crude/sloppy/loose/lax/normal/tight/vtight/extreme), positive finite `accuracy`,
`electronic_temperature_kelvin`, `timeout_seconds`, and positive integer
`max_scc_iterations`, `max_optimization_cycles`, `threads`. These settings are
validated only, never applied. All require approval before future execution.

## Geometry checks and report

Only single-frame XYZ is accepted: positive atom count, comment line (possibly
empty), exactly the declared atom records, and case-sensitive periodic-table
symbols followed by exactly three finite numbers. Extra columns, atom-count
mismatches, NaN/infinity, and extra frames are fatal. Trailing blank lines are
allowed. Isotope aliases and atomic-number notation are unsupported. GFN2-xTB
preflight rejects atomic numbers above 86.

Distances below 1e-8 angstrom are coincident; distances below 0.4 angstrom are
fatal. Distances from 0.4 to below 0.7 angstrom warn. Atoms without a neighbour
within 3 angstrom warn about possible fragmentation. These conservative screening
heuristics are implementation choices, not paper parameters or bond perception.
They can miss chemically invalid structures and warn on legitimate unusual
systems. Geometries are never repaired.

The report contains schema version, UTC timestamp, configuration and overall
status, molecule/state IDs, input paths, geometry/input status, parsed atom data,
charge/spin status and electron count, identity metadata status, errors, and
warnings. A blocked check cannot make overall validation succeed. Configuration
status covers global protocol/schema and molecule coverage; per-state errors
also fail the overall status. No placeholder energies or scientific results are
created. JSON rejects nonfinite values and is written to a temporary file in
the destination directory, flushed, and atomically replaced. The previous
report survives serialization/write failure.

## Manual Docker commands

Use the existing working image without rebuilding by mounting updated source
and tests. Existing Compose config/structures/results mounts remain in use:

```bash
docker compose run --rm -v "$PWD/src:/work/src:ro" reproduce qm --preflight
```

The current template is expected to exit 1 and report missing inputs. After
source is included in an image, the equivalent command is:

```bash
docker compose run --rm reproduce qm --preflight
```

Focused tests with no engine calculations:

```bash
docker compose run --rm \
  -v "$PWD/src:/work/src:ro" -v "$PWD/tests:/work/tests:ro" \
  --entrypoint python reproduce -m pytest -q -p no:cacheprovider \
  tests/test_qm_preflight.py tests/test_audit.py tests/test_config.py
```

Do not use the full `test` command for lightweight-only validation: it includes
real engine smoke calculations. No Docker build or dependency changes are
needed for these source-mount commands.
