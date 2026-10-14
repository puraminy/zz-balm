# Software and licensing notes

The container is designed for command-line/headless use. No graphical desktop, GUI application, or visualization workflow is required.

| Component | Role | Notes |
|---|---|---|
| Docker / Compose | Reproducible runtime | Docker Engine required on host |
| Python, NumPy, SciPy, pandas | Workflow and analysis | Open-source |
| ASE | Atomistic structures/workflow | Does not provide a validated Fe force field by itself |
| xTB | Semiempirical quantum chemistry | CLI; screening surrogate, not equivalent to B3LYP/6-311G** |
| LAMMPS | Molecular dynamics | Use only with a validated force field |
| MDAnalysis | Trajectory analysis | Headless |
| Matplotlib | Save figures to files | Uses noninteractive Agg backend |

## Paper software not bundled
The paper reports Gaussian 09 and Materials Studio tools (DMol3, Adsorption Locator, Forcite/COMPASS). These are proprietary and are not downloaded, installed, or redistributed here. If you hold suitable licenses, they can be run separately; their outputs may be imported for validation.

## Reproducibility cautions
- A runnable engine does not guarantee scientifically valid parameterization.
- Fe, protonated organic molecules, water, and acidic-solution interactions are major modeling issues.
- Archive software versions and input settings for every production run.
