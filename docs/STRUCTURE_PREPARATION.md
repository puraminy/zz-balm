# Molecular structure preparation

Use the project Python environment with RDKit. Run commands from the repository
root. Input structure paths are repository-relative (absolute paths also work).
Keep original source files under `structures/` or in a separate source archive.

## Verify and prepare a molecule

Copy the template and keep only the entries approved for that run.

```bash
cp -n config/structures.yaml config/structures.local.yaml
```

Supply a source database or publication, a source identifier, and verified
isomeric SMILES or a single-record MOL/SDF file. For a stereogenic 3D file,
also provide approved isomeric SMILES because RDKit can read stereochemistry
from coordinates. If both inputs are supplied, their canonical isomeric
representations must agree. Set `source_kind` to `experimental`, `database`,
`computational`, or `xtb_optimized` according to the provenance of the supplied
input. Record explicit stereochemical specifications, formal charge, protonation
state ID and description, and a conformer ID. Use a documented designation
for molecules without stereogenic elements. After reviewing this evidence, set
`identity_approved: true` and enter the approver in `identity_approved_by`.

```bash
python -m src.cli structures prepare --config config/structures.local.yaml --dry-run
python -m src.cli structures prepare --config config/structures.local.yaml
```

Dry-run checks metadata, source files, connectivity, charge, stereochemistry,
and output collisions. An unresolved stereoelement blocks preparation.
The workflow accepts one connected component and uses RDKit's potential
stereoelement detection. The approver is responsible for chemical identity,
including stereochemical features outside that detection and the selected
protonation state.

Each output directory is
`results/structures/<molecule_id>/<protonation_state_id>/<conformer_id>/`.
For multiple conformers the configured ID receives suffixes such as `-01`
and `-02`. Choose a new ID when rerunning. Outputs contain initial and
prepared SDF/XYZ pairs and an atomic `metadata.json` report. The input checksum
hashes the original file bytes or the exact UTF-8 SMILES string. XYZ coordinates
are in ångströms. Use the SDF for connectivity. Errors are reported in the CLI
JSON with a nonzero exit status. An incomplete embedding reports attempt
failure counts and produces no conformer files for that entry.

ETKDGv3 generates up to ten conformers, using one thread and an explicit seed.
Record and reuse the RDKit version and input atom order for reproducibility.
The source coordinate file remains untouched and the initial output contains
new ETKDG coordinates. The workflow assigns IDs in embedding order and leaves
scientific conformer selection to the researcher.

When enabled, MMFF94 refines a copy of each initial geometry. If parameters
are unavailable, the prepared files contain the ETKDG geometry and metadata
reports `parameters_unavailable`. An iteration limit retains the last MMFF94
iterate with a warning and explicit nonconvergence. MMFF94 energies use
kcal/mol and are unsuitable for direct comparisons across different molecular
compositions. Generated coordinates remain computational and carry no
scientific approval. GFN2-xTB optimization is a separate later step.

## Validate with QM Preflight

In `config/qm.yaml`, point the intended state's `input_file` to the chosen
`prepared.xyz` and set `coordinate_units: angstrom`. Use the actual output
conformer ID. Supply the reviewed identity metadata, charge, spin multiplicity,
protonation information, and protocol settings required by the existing
preflight schema. See [QM Preflight](QM_PREFLIGHT.md).

```bash
python -m src.cli qm --preflight
```

The report is written to `results/qm/preflight.json`. Preflight checks all
configured study molecules. Unresolved records or protocol settings will
keep the overall status nonzero even if the prepared structure passes its
individual checks.

Verified identities and source structures are pending for Caryophyllene,
Germacrene, Citral, Luteolin, Chlorogenic acid, and Rosmarinic acid.
