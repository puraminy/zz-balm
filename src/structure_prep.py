"""Prepare computational conformers from explicitly approved chemical identities."""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import shutil
from pathlib import Path

import yaml
from rdkit import Chem, rdBase
from rdkit.Chem import AllChem, rdMolDescriptors

from .qm import ROOT, text_present, write_report


class PreparationError(ValueError):
    """Invalid input or unsuccessful preparation."""


def validate_connectivity(mol):
    if mol is None or not mol.GetNumAtoms():
        raise PreparationError("Invalid or empty molecular structure.")
    if any(atom.GetAtomicNum() == 0 for atom in mol.GetAtoms()):
        raise PreparationError("Dummy atoms are unsupported.")
    if len(Chem.GetMolFrags(mol)) != 1:
        raise PreparationError("Expected one connected molecular component.")
    return mol


def load_smiles(smiles):
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.allowCXSMILES = False
    params.removeHs = False
    return validate_connectivity(Chem.MolFromSmiles(smiles, params))


def load_structure(path, *, data=None):
    """Load exactly one sanitized MOL or SDF record, retaining source hydrogens."""
    path = Path(path)
    data = path.read_bytes() if data is None else data
    if path.suffix.lower() == ".mol":
        mol = Chem.MolFromMolBlock(data.decode("utf-8"), removeHs=False)
    elif path.suffix.lower() == ".sdf":
        with Chem.ForwardSDMolSupplier(io.BytesIO(data), removeHs=False) as supplier:
            mol = next(supplier, None)
            if next(supplier, False) is not False:
                raise PreparationError("Expected exactly one SDF record.")
    else:
        raise PreparationError("Expected a .mol or .sdf input file.")
    return validate_connectivity(mol)


def stereochemistry(mol):
    """Report potential stereoelements using zero-based RDKit atom/bond indices."""
    return [
        dict(type=str(info.type), index=info.centeredOn,
             specification=str(info.specified), descriptor=str(info.descriptor))
        for info in Chem.FindPotentialStereo(mol)
    ]


def add_hydrogens(mol):
    return Chem.AddHs(mol)


def generate_conformers(mol, count, seed):
    if type(count) is not int or not 1 <= count <= 10:
        raise PreparationError("num_conformers must be an integer from 1 to 10.")
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise PreparationError("random_seed must be a nonnegative signed 32-bit integer.")
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    params.numThreads = 1
    params.maxIterations = 50
    params.enforceChirality = True
    params.trackFailures = True
    params.pruneRmsThresh = -1.0
    ids = list(AllChem.EmbedMultipleConfs(mol, count, params))
    counts = params.GetFailureCounts()
    failures = {cause.name: counts[index] for index, cause in
                AllChem.EmbedFailureCauses.values.items() if index < len(counts)}
    settings = dict(method="ETKDGv3", num_conformers=count, random_seed=seed,
                    num_threads=1, max_iterations=params.maxIterations,
                    enforce_chirality=True, prune_rms_threshold=-1.0,
                    use_random_coords=params.useRandomCoords,
                    use_exp_torsion_angle_prefs=params.useExpTorsionAnglePrefs,
                    use_basic_knowledge=params.useBasicKnowledge,
                    torsion_version=params.ETversion,
                    use_small_ring_torsions=params.useSmallRingTorsions,
                    use_macrocycle_torsions=params.useMacrocycleTorsions,
                    use_macrocycle_14_config=params.useMacrocycle14config,
                    embedded_conformers=len(ids), failure_counts=failures)
    if len(ids) != count:
        raise PreparationError(f"Incomplete embedding: {json.dumps(settings)}")
    return ids, settings


def has_mmff_parameters(mol):
    return AllChem.MMFFHasAllMoleculeParams(mol)


def refine_geometry(mol, conformer_id, enabled, max_iterations):
    """Refine a copy. Missing parameters retain the ETKDG geometry."""
    prepared = Chem.Mol(mol)
    report = dict(enabled=enabled, variant="MMFF94" if enabled else None,
                  max_iterations=max_iterations, status="disabled", converged=None,
                  parameters_available=None, energy=None, energy_units="kcal/mol")
    if not enabled:
        return prepared, report
    report["parameters_available"] = has_mmff_parameters(prepared)
    if not report["parameters_available"]:
        report["status"] = "parameters_unavailable"
        return prepared, report
    properties = AllChem.MMFFGetMoleculeProperties(prepared, mmffVariant="MMFF94")
    field = AllChem.MMFFGetMoleculeForceField(prepared, properties, confId=conformer_id)
    if field is None:
        raise PreparationError("Could not construct the MMFF94 force field.")
    status = field.Minimize(maxIts=max_iterations)
    if status not in (0, 1):
        raise PreparationError(f"MMFF94 minimization failed with status {status}.")
    report.update(status="converged" if status == 0 else "iteration_limit",
                  converged=status == 0, energy=field.CalcEnergy())
    return prepared, report


def export_geometry(mol, conformer_id, stem):
    """Write one conformer in RDKit atom order, using ångström coordinates."""
    coordinates = mol.GetConformer(conformer_id).GetPositions()
    if not all(math.isfinite(value) for row in coordinates for value in row):
        raise PreparationError("Conformer has nonfinite coordinates.")
    with Chem.SDWriter(str(stem.with_suffix(".sdf"))) as writer:
        writer.write(mol, confId=conformer_id)
    stem.with_suffix(".xyz").write_text(
        Chem.MolToXYZBlock(mol, confId=conformer_id, precision=10), encoding="utf-8"
    )


def validate_input(record, root):
    if not isinstance(record, dict):
        raise PreparationError("Structure entry must be a mapping.")
    identifiers = ("molecule_id", "protonation_state_id", "conformer_id")
    fields = (*identifiers, "chemical_name", "source", "source_identifier",
              "source_kind", "stereochemical_specification", "protonation_description",
              "identity_approved_by")
    errors = [f"Missing {key}" for key in fields if not text_present(record.get(key))]
    for key in identifiers:
        value = record.get(key)
        if text_present(value) and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
            errors.append(f"Invalid path identifier {key}")
    if type(record.get("charge")) is not int:
        errors.append("charge must be an explicit integer")
    if record.get("identity_approved") is not True:
        errors.append("Explicit user identity approval is required")
    if record.get("source_kind") not in (
        "experimental", "database", "computational", "xtb_optimized"
    ):
        errors.append("Invalid source_kind")
    smiles, reference = record.get("isomeric_smiles"), record.get("structure_file")
    if not text_present(smiles) and not text_present(reference):
        errors.append("Supply isomeric_smiles or a structure_file")
    if any(value is not None and not text_present(value) for value in (smiles, reference)):
        errors.append("isomeric_smiles and structure_file must be nonempty strings when provided")
    path = root / reference if text_present(reference) else None
    if path is not None and not path.is_file():
        errors.append(f"Missing input structure: {path}")
    if errors:
        raise PreparationError(". ".join(errors))
    data = path.read_bytes() if path else smiles.encode("utf-8")
    mol = load_structure(path, data=data) if path else load_smiles(smiles)
    stereo = stereochemistry(mol)
    unresolved = [item for item in stereo if item["specification"] != "Specified"]
    if unresolved:
        raise PreparationError(f"Unresolved stereochemistry: {unresolved}")
    if mol.GetStereoGroups():
        raise PreparationError("Enhanced stereochemical groups are unsupported; supply one absolute identity.")
    canonical = Chem.MolToSmiles(Chem.RemoveHs(mol))
    if path and smiles:
        if Chem.MolToSmiles(Chem.RemoveHs(load_smiles(smiles))) != canonical:
            raise PreparationError("Structure file and approved isomeric SMILES disagree.")
    if path and stereo and any(conf.Is3D() for conf in mol.GetConformers()) and not smiles:
        raise PreparationError("A stereogenic 3D input file requires approved isomeric SMILES.")
    charge = Chem.GetFormalCharge(mol)
    if charge != record["charge"]:
        raise PreparationError(f"Declared charge differs from formal charge {charge}.")
    identity = {key: record.get(key) for key in (*fields, "identity_approved", "charge",
                                                 "isomeric_smiles", "structure_file")}
    metadata = dict(schema_version=1, identity=identity, rdkit_version=rdBase.rdkitVersion,
                    input_sha256=hashlib.sha256(data).hexdigest(),
                    input_checksum_basis="structure_file_bytes" if path else "utf8_smiles",
                    canonical_isomeric_smiles=canonical, stereochemistry=stereo,
                    molecular_formula=rdMolDescriptors.CalcMolFormula(mol), formal_charge=charge,
                    coordinate_units="angstrom", scientific_approval=False, errors=[])
    return mol, metadata


def prepare(mol, metadata, settings, destinations):
    mol = add_hydrogens(mol)
    mol.RemoveAllConformers()
    ids, embedding = generate_conformers(mol, settings["num_conformers"], settings["random_seed"])
    created = []
    reports = []
    try:
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.mkdir()
            created.append(destination)
        for conf_id, destination in zip(ids, destinations, strict=True):
            prepared, refinement = refine_geometry(
                mol, conf_id, settings["mmff94"], settings["mmff_max_iterations"]
            )
            export_geometry(mol, conf_id, destination / "initial")
            export_geometry(prepared, conf_id, destination / "prepared")
            report = dict(
                metadata, conformer_id=destination.name, rdkit_conformer_id=conf_id,
                atom_count=mol.GetNumAtoms(), etkdg=embedding, force_field=refinement,
                initial_geometry="rdkit_etkdg",
                prepared_geometry="rdkit_mmff94" if refinement["converged"] is not None else "rdkit_etkdg",
                preparation_status="complete" if refinement["status"] in ("disabled", "converged")
                else "complete_with_warning",
            )
            write_report(report, destination / "metadata.json")
            reports.append(dict(path=str(destination), status=report["preparation_status"],
                                mmff94=refinement["status"], etkdg=embedding))
    except (OSError, ValueError, RuntimeError):
        for destination in created:
            shutil.rmtree(destination)
        raise
    return reports


def run_config(config_path, dry_run=False, *, root=ROOT):
    """Validate all configured identities and paths before starting any embedding."""
    report = dict(status="error", errors=[], outputs=[])
    try:
        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
            raise PreparationError("Expected structure configuration schema version 1.")
        settings = config.get("settings")
        if not isinstance(settings, dict):
            raise PreparationError("settings must be a mapping.")
        count = settings.get("num_conformers")
        seed = settings.get("random_seed")
        iterations = settings.get("mmff_max_iterations")
        if type(count) is not int or not 1 <= count <= 10:
            raise PreparationError("num_conformers must be an integer from 1 to 10.")
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            raise PreparationError("random_seed must be a nonnegative signed 32-bit integer.")
        if type(settings.get("mmff94")) is not bool or type(iterations) is not int or not 1 <= iterations <= 1000:
            raise PreparationError("Supply a boolean mmff94 and mmff_max_iterations from 1 to 1000.")
        records = config.get("structures")
        if not isinstance(records, list) or not records:
            raise PreparationError("structures must be a nonempty list.")
        jobs = []
        seen = set()
        for index, record in enumerate(records, 1):
            try:
                mol, metadata = validate_input(record, root)
                base = root / "results/structures" / record["molecule_id"] / record["protonation_state_id"]
                prefix = record["conformer_id"]
                destinations = [base / (prefix if count == 1 else f"{prefix}-{i:02d}")
                                for i in range(1, count + 1)]
                for path in destinations:
                    if path in seen or path.exists() or path.is_symlink():
                        raise PreparationError(f"Output already exists or is duplicated: {path}")
                    if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
                        raise PreparationError(f"Symlink in output path: {path}")
                    seen.add(path)
                jobs.append((mol, metadata, destinations))
            except (OSError, ValueError, RuntimeError) as exc:
                report["errors"].append(f"Structure entry {index}: {exc}")
        if report["errors"]:
            return report
        for mol, metadata, destinations in jobs:
            if dry_run:
                report["outputs"].extend(dict(path=str(path), status="validated") for path in destinations)
                continue
            try:
                report["outputs"].extend(prepare(mol, metadata, settings, destinations))
            except (OSError, ValueError, RuntimeError) as exc:
                report["errors"].append(f"{destinations[0]}: {exc}")
        if not report["errors"]:
            report["status"] = "dry_run" if dry_run else "ok"
    except (OSError, ValueError, yaml.YAMLError) as exc:
        report["errors"].append(str(exc))
    return report
