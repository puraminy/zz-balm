"""QM preflight only. This module never launches a computational engine."""
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .qm_io import validate_xyz

ROOT = Path(__file__).resolve().parents[1]


def text_present(value):
    return isinstance(value, str) and bool(value.strip())


def validate_state(state, atomic_numbers):
    errors = []
    charge, multiplicity = state.get('charge'), state.get('multiplicity')
    if type(charge) is not int:
        errors.append('Molecular charge must be an explicit integer (not a boolean).')
    if type(multiplicity) is not int or multiplicity < 1:
        errors.append('Spin multiplicity must be an explicit integer >= 1.')
    for key in ('state_id', 'protonation_state_id', 'conformer_id'):
        if not text_present(state.get(key)):
            errors.append(f'Missing explicit {key}.')
    electrons = None
    if type(charge) is int and atomic_numbers is not None:
        electrons = sum(atomic_numbers) - charge
        if electrons <= 0:
            errors.append('Electron count must be positive.')
        if type(multiplicity) is int and multiplicity >= 1:
            unpaired = multiplicity - 1
            if unpaired > electrons or (electrons - unpaired) % 2:
                errors.append('Electron count and multiplicity are inconsistent (unpaired count/parity).')
    if type(multiplicity) is int and multiplicity != 1:
        errors.append('Only closed-shell singlets (multiplicity 1) are supported in this phase.')
    return dict(status='error' if errors else ('blocked' if atomic_numbers is None else 'ok'),
                electron_count=electrons, errors=errors, warnings=[])


def validate_identity(identity, molecule_id, protonation_state_id):
    errors = []
    if not isinstance(identity, dict):
        identity = {}
    for key in ('molecule_id', 'chemical_name', 'source', 'isomer_identifier',
                'connectivity_reference', 'protonation_description'):
        if not text_present(identity.get(key)):
            errors.append(f'Missing chemical identity metadata: {key}.')
    if identity.get('molecule_id') != molecule_id:
        errors.append('Identity molecule_id must match the state molecule_id.')
    site = identity.get('protonation_site')
    if not text_present(site):
        errors.append('Explicit protonation_site required; neutral species may use not_applicable.')
    elif site == 'not_applicable' and protonation_state_id != 'neutral':
        errors.append('A non-neutral state requires an explicit site description.')
    return dict(status='error' if errors else 'ok', errors=errors,
                warnings=['Identity metadata is supplied evidence, not automated chemical identity verification.'])


def validate_protocol(config):
    errors = []
    if type(config.get('schema_version')) is not int or config['schema_version'] != 1:
        errors.append('QM schema_version must be 1.')
    if config.get('method') != 'GFN2-xTB':
        errors.append('Only explicit method GFN2-xTB is supported.')
    solvent = config.get('solvent')
    if not isinstance(solvent, dict):
        solvent = {}
    if solvent.get('model') == 'none':
        if solvent.get('solvent') is not None or solvent.get('reference_state') is not None:
            errors.append('Gas phase requires null solvent and reference_state.')
    elif solvent.get('model') == 'ALPB':
        if solvent.get('solvent') != 'water' or solvent.get('reference_state') not in ('gsolv', 'reference', 'bar1M'):
            errors.append('ALPB requires water and an explicit supported reference_state.')
    else:
        errors.append('Select explicit solvent model none or ALPB; no default is assumed.')
    settings = config.get('settings')
    if not isinstance(settings, dict):
        settings = {}
    if settings.get('optimization_level') not in ('crude', 'sloppy', 'loose', 'lax', 'normal', 'tight', 'vtight', 'extreme'):
        errors.append('Explicit supported optimization_level is required.')
    for key in ('accuracy', 'electronic_temperature_kelvin', 'timeout_seconds'):
        value = settings.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            errors.append(f'{key} must be an explicit positive finite number.')
    for key in ('max_scc_iterations', 'max_optimization_cycles', 'threads'):
        value = settings.get(key)
        if type(value) is not int or value <= 0:
            errors.append(f'{key} must be an explicit positive integer.')
    return errors


def preflight(config_path=ROOT / 'config/qm.yaml', paper_path=ROOT / 'config/paper.yaml', root=ROOT):
    """Collect all available errors; relative geometry paths are repository-relative."""
    report = dict(schema_version=1, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  status='error', configuration_status='error', errors=[], warnings=[], states=[])
    try:
        config = yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
        paper = yaml.safe_load(Path(paper_path).read_text(encoding='utf-8'))
        if not isinstance(config, dict) or not isinstance(paper, dict):
            raise ValueError('Configuration roots must be mappings.')
        molecules = paper.get('molecules')
        if not isinstance(molecules, list) or not all(text_present(x) for x in molecules):
            raise ValueError('Paper molecules must be a list of identifiers.')
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
        report['errors'].append(f'Cannot load configuration: {exc}')
        return report
    report['errors'].extend(validate_protocol(config))
    states = config.get('states')
    if not isinstance(states, list) or not states:
        report['errors'].append('states must be a nonempty list; no executable species are inferred.')
        return report
    seen, covered = set(), set()
    for index, state in enumerate(states):
        if not isinstance(state, dict):
            report['errors'].append(f'State entry {index + 1} must be a mapping.')
            continue
        molecule = state.get('molecule_id')
        entry = dict(molecule_id=molecule if text_present(molecule) else None,
                     state_id=state.get('state_id') if text_present(state.get('state_id')) else None,
                     input_file=state.get('input_file') if text_present(state.get('input_file')) else None,
                     charge=state.get('charge') if type(state.get('charge')) is int else None,
                     multiplicity=state.get('multiplicity') if type(state.get('multiplicity')) is int else None,
                     protonation_state_id=state.get('protonation_state_id') if text_present(state.get('protonation_state_id')) else None,
                     conformer_id=state.get('conformer_id') if text_present(state.get('conformer_id')) else None,
                     errors=[], warnings=[])
        errors = entry['errors']
        if not text_present(molecule) or molecule not in molecules:
            errors.append('molecule_id must match a molecule in paper.yaml.')
        else:
            covered.add(molecule)
        state_id = state.get('state_id')
        if text_present(molecule) and text_present(state_id):
            key = (molecule, state_id)
            if key in seen:
                errors.append('Duplicate molecule_id/state_id pair.')
            seen.add(key)
        input_file = state.get('input_file')
        if text_present(input_file):
            geometry = validate_xyz(Path(root) / input_file, state.get('coordinate_units'))
        else:
            geometry = dict(status='error', input_status='missing', errors=['Missing molecular input_file.'], warnings=[])
        identity = validate_identity(state.get('identity'), molecule, state.get('protonation_state_id'))
        numbers = geometry.get('atomic_numbers') if geometry['status'] == 'ok' else None
        spin = validate_state(state, numbers)
        if numbers and any(z > 86 for z in numbers):
            errors.append('GFN2-xTB preflight supports atomic numbers 1 through 86 only.')
        for component in (geometry, spin, identity):
            errors.extend(component['errors'])
            entry['warnings'].extend(component['warnings'])
        entry.update(geometry=geometry, charge_spin=spin, identity=identity,
                     status='error' if errors else 'ok')
        report['states'].append(entry)
    for molecule in molecules:
        if molecule not in covered:
            report['errors'].append(f'No state record for configured molecule {molecule}.')
    report['configuration_status'] = 'error' if report['errors'] else 'ok'
    report['status'] = 'error' if report['errors'] or any(s['status'] != 'ok' for s in report['states']) else 'ok'
    report['warnings'].append('Preflight checks input consistency only; no calculation or chemical identity assignment is performed.')
    return report


def write_report(report, path):
    """Serialize before replacing, keeping any previous report intact on failure."""
    data = json.dumps(report, indent=2, allow_nan=False) + '\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_preflight():
    report = preflight()
    path = ROOT / 'results/qm/preflight.json'
    try:
        write_report(report, path)
    except (OSError, ValueError, TypeError) as exc:
        print(f'Cannot write QM preflight report: {exc}')
        return 1
    print(f"QM preflight: {report['status']} (configuration: {report['configuration_status']})")
    for error in report['errors']:
        print(f'  ERROR: {error}')
    for entry in report['states']:
        print(f"  {entry['molecule_id']} / {entry['state_id']}: {entry['status']}")
        for error in entry['errors']:
            print(f'    ERROR: {error}')
        for warning in entry['warnings']:
            print(f'    WARNING: {warning}')
    for warning in report['warnings']:
        print(f'  WARNING: {warning}')
    print(f'Wrote {path}')
    return 0 if report['status'] == 'ok' else 1
