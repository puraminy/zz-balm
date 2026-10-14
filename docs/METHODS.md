# Methods plan

This document distinguishes source-reported methods from the proposed open-source implementation.

## Stage A — data and method audit
- Inventory article tables, figure data, molecular species, and settings.
- Preserve source page/table/figure references for each transcribed value.
- Produce a machine-readable list of unresolved details.

## Stage B — molecular structures and quantum calculations
- Establish structures and protonation sites from documented sources.
- Use command-line xTB as an initial open-source screening method.
- Record charge, multiplicity, solvent treatment, convergence, and software version.
- Do not compare xTB orbital energies directly with B3LYP values as if they were the same method.
- If method-matched DFT is needed, evaluate command-line quantum packages separately and document method and licensing.

## Stage C — surface adsorption
- Construct and validate Fe(110) slab geometry with ASE.
- Verify lattice constants, cell dimensions, vacuum, slab constraints, and charge/spin assumptions.
- Document the sampling algorithm and energy definition. An open-source search is not automatically equivalent to Adsorption Locator.

## Stage D — molecular dynamics
- LAMMPS is available as a headless MD engine, but availability of the engine does not validate a force field.
- COMPASS is proprietary; do not invent missing Fe/inhibitor/water parameters.
- Validate parameterization before production MD and label surrogate models clearly.

## Stage E — analysis and validation
- Use Python to calculate properties and save plots using a noninteractive backend.
- Export tables to CSV and run summaries to JSON.
- Compare quantities only when units, reference states, and model definitions match.
