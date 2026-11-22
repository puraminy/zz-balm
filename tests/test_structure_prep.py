import json
from pathlib import Path

import pytest
import yaml
from rdkit import Chem

from src import cli, structure_prep as prep
from src.qm_io import validate_xyz


@pytest.fixture
def record():
    return dict(molecule_id="synthetic", chemical_name="Ethanol", source="Test fixture",
                source_identifier="fixture-1", source_kind="computational",
                stereochemical_specification="No stereogenic elements", charge=0,
                protonation_state_id="neutral", protonation_description="Neutral alcohol",
                conformer_id="test", identity_approved=True, identity_approved_by="Test fixture",
                isomeric_smiles="CCO")


@pytest.fixture
def config(tmp_path, record):
    path = tmp_path / "structures.yaml"
    config = dict(schema_version=1, settings=dict(num_conformers=2, random_seed=123,
                  mmff94=True, mmff_max_iterations=100), structures=[record])
    path.write_text(yaml.safe_dump(config))
    return path


def test_smiles_and_hydrogens():
    mol = prep.load_smiles("CCO")
    assert mol.GetNumAtoms() == 3
    assert prep.add_hydrogens(mol).GetNumAtoms() == 9


@pytest.mark.parametrize("smiles", ["C(", "C.C", "*", "C(F)(F)(F)(F)F"])
def test_invalid_smiles(smiles):
    with pytest.raises(prep.PreparationError):
        prep.load_smiles(smiles)


@pytest.mark.parametrize("extension", ["sdf", "mol"])
def test_structure_loading(tmp_path, extension):
    path = tmp_path / f"input.{extension}"
    mol = prep.load_smiles("CCO")
    if extension == "sdf":
        with Chem.SDWriter(str(path)) as writer:
            writer.write(mol)
    else:
        Chem.MolToMolFile(mol, str(path))
    assert Chem.MolToSmiles(prep.load_structure(path)) == "CCO"


def test_missing_input(tmp_path, record):
    with pytest.raises(prep.PreparationError, match="Missing input structure"):
        prep.validate_input(dict(record, structure_file="missing.sdf"), tmp_path)


@pytest.mark.parametrize("smiles", ["CC(O)F", "FC=CF"])
def test_unspecified_stereochemistry(tmp_path, record, smiles):
    with pytest.raises(prep.PreparationError, match="Unresolved stereochemistry"):
        prep.validate_input(dict(record, isomeric_smiles=smiles), tmp_path)


def test_explicit_stereo_and_approval(tmp_path, record):
    _, meta = prep.validate_input(dict(record, isomeric_smiles="C[C@H](O)F"), tmp_path)
    assert meta["stereochemistry"][0]["specification"] == "Specified"
    with pytest.raises(prep.PreparationError, match="approval"):
        prep.validate_input(dict(record, identity_approved=False), tmp_path)


def test_deterministic_embedding_and_mmff():
    first, second = [prep.add_hydrogens(prep.load_smiles("CCO")) for _ in range(2)]
    assert prep.generate_conformers(first, 2, 42) == prep.generate_conformers(second, 2, 42)
    assert Chem.MolToXYZBlock(first, confId=1) == Chem.MolToXYZBlock(second, confId=1)
    assert prep.has_mmff_parameters(first)
    before = Chem.MolToXYZBlock(first, confId=1)
    _, mmff = prep.refine_geometry(first, 1, True, 100)
    assert mmff["energy_units"] == "kcal/mol" and mmff["energy"] is not None
    assert Chem.MolToXYZBlock(first, confId=1) == before


def test_mmff_fallback():
    mol = prep.add_hydrogens(prep.load_smiles("B"))
    assert not prep.has_mmff_parameters(mol)
    copy, report = prep.refine_geometry(mol, 0, True, 100)
    assert report["status"] == "parameters_unavailable"
    assert report["energy"] is None
    assert Chem.MolToSmiles(copy) == Chem.MolToSmiles(mol)


def test_metadata_serialization_and_no_overwrite(tmp_path, config):
    assert prep.run_config(config, True, root=tmp_path)["status"] == "dry_run"
    assert not (tmp_path / "results").exists()
    report = prep.run_config(config, root=tmp_path)
    assert report["status"] == "ok", report
    assert len(report["outputs"]) == 2
    destination = Path(report["outputs"][0]["path"])
    metadata_path = destination / "metadata.json"
    saved = metadata_path.read_bytes()
    metadata = json.loads(saved)
    assert metadata["molecular_formula"] == "C2H6O"
    assert metadata["atom_count"] == 9
    assert metadata["etkdg"]["failure_counts"]
    assert metadata["scientific_approval"] is False
    for stem in ("initial", "prepared"):
        assert validate_xyz(destination / f"{stem}.xyz", "angstrom")["status"] == "ok"
        assert prep.load_structure(destination / f"{stem}.sdf").GetNumAtoms() == 9
    assert prep.run_config(config, root=tmp_path)["status"] == "error"
    assert metadata_path.read_bytes() == saved


def test_export_failure(tmp_path, config, monkeypatch):
    def fail(*args):
        raise OSError("test write failure")

    monkeypatch.setattr(prep, "export_geometry", fail)
    report = prep.run_config(config, root=tmp_path)
    assert report["status"] == "error"
    assert "test write failure" in report["errors"][0]
    assert not list(tmp_path.glob("results/structures/*/*/test-*"))


@pytest.mark.parametrize("args", [["prepare"], ["unknown"], ["prepare", "--config", "missing.yaml"]])
def test_cli_argument_validation(monkeypatch, args):
    monkeypatch.setattr("sys.argv", ["cli", "structures", *args])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == (1 if "--config" in args else 2)
