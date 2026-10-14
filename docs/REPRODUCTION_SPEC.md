# Reproduction specification and unresolved items

## Source article
Asadi et al. (2018), DOI: 10.1016/j.jtice.2018.07.011.

## Molecular quantum chemistry reported in the paper
- Compounds: caryophyllene, germacrene, citral, luteolin, chlorogenic acid, and rosmarinic acid.
- Neutral and protonated forms are considered.
- Initial geometry: HF/6-31G**; DFT: B3LYP/6-311G**.
- Frequency calculations and implicit water via PCM/SCRF are reported.
- Properties include HOMO/LUMO, energy gap, and ChelpG partial charges.
- The article states optimized structures have no imaginary frequencies.

## Fukui indices reported in the paper
- Materials Studio DMol3, GGA/PBE, DNP basis.
- Convergence: energy 2×10⁻⁵ Ha, maximum force 4×10⁻³ Ha/Å, maximum displacement 5×10⁻³ Å.

## Monte Carlo adsorption reported in the paper
- Fe(110) surface; reported slab thickness 15 Å, replication 14×14, vacuum about 30 Å.
- Materials Studio Adsorption Locator.
- Exact settings and adsorption-energy convention must be checked before claiming quantitative agreement.

## Molecular dynamics reported in the paper
- Materials Studio Forcite, COMPASS force field.
- 600 water molecules at density 1 g/cm³.
- NVT at room temperature, Nose–Hoover thermostat.
- 1 fs time step; 1 ns (1000 ps) duration.
- Electrostatics: Ewald; van der Waals: atom-based cutoff.
- Exact cutoff, water model, equilibration/production split, constraints, and Fe–molecule cross-interactions need verification.

## Reproduction tiers
1. Paper-data audit: transcribe reported values with page/figure/table provenance.
2. Headless open-source workflow: run command-line calculations with documented alternative methods.
3. Method-matched reproduction: only if licensed software, exact parameters, and compatible inputs are available.
4. Validation: compare like-for-like quantities and classify agreement by quantity.

## Unresolved — do not guess
- Molecular coordinates and protonation sites.
- Exact Fe slab lattice parameter, dimensions, fixed layers, and boundary conditions.
- Adsorption-energy sign convention and components.
- Adsorption Locator search settings and number of trial configurations.
- COMPASS atom typing/parameters for Fe, inhibitor, acid species, and water.
- Water model, cutoff, equilibration details, and trajectory sampling.
- Original numerical table/figure values to use as validation targets.
- Supplementary information or author-provided inputs.

Record each resolved item with its source citation; do not silently fill gaps with defaults.
