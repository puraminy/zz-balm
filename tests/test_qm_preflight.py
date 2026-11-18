"""Synthetic validation fixtures only; no study structures or engine calls."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from src import cli, qm
from src.qm_io import validate_xyz


@pytest.fixture
def xyz(tmp_path):
    path = tmp_path / 'synthetic.xyz'
    path.write_text('2\nSynthetic hydrogen fixture, not a study molecule\nH 0 0 0\nH 0 0 0.74\n')
    return path


def test_xyz_valid_and_order(xyz):
    original = xyz.read_bytes()
    result = validate_xyz(xyz, 'angstrom')
    assert result['status'] == 'ok'
    assert result['symbols'] == ['H', 'H']
    assert result['coordinates'] == [[0., 0., 0.], [0., 0., 0.74]]
    assert result['atomic_numbers'] == [1, 1]
    assert xyz.read_bytes() == original


@pytest.mark.parametrize('content,message', [
    ('', 'positive integer'),
    ('0\ncomment\n', 'positive integer'),
    ('-1\ncomment\n', 'positive integer'),
    ('2\ncomment\nH 0 0 0\n', 'atom count'),
    ('1\ncomment\nH 0 0 0\nH 0 0 1\n', 'atom count'),
    ('1\ncomment\nH x 0 0\n', 'numerical'),
    ('1\ncomment\nH 0 0\n', 'exactly three'),
    ('1\ncomment\nH 0 0 0 9\n', 'exactly three'),
    ('1\ncomment\nXx 0 0 0\n', 'element'),
    ('1\ncomment\nh 0 0 0\n', 'element'),
    ('1\ncomment\nH nan 0 0\n', 'finite'),
    ('1\ncomment\nH inf 0 0\n', 'finite'),
    ('1\ncomment\nH -inf 0 0\n', 'finite'),
    ('1\ncomment\nH 0 0 0\n1\nframe2\nH 0 0 1\n', 'single-frame'),
    ('2\ncomment\nH 0 0 0\nH 0 0 0\n', 'coincident'),
    ('2\ncomment\nH 0 0 0\nH 0 0 0.2\n', 'implausible'),
])
def test_xyz_errors(tmp_path, content, message):
    path = tmp_path / 'bad.xyz'
    path.write_text(content)
    result = validate_xyz(path, 'angstrom')
    assert result['status'] == 'error'
    assert message in ' '.join(result['errors'])


@pytest.mark.parametrize('units', [None, 'bohr', '', True])
def test_units_mandatory(xyz, units):
    assert validate_xyz(xyz, units)['status'] == 'error'


def test_missing_xyz(tmp_path):
    result = validate_xyz(tmp_path / 'missing.xyz', 'angstrom')
    assert result['input_status'] == 'missing'
    assert result['status'] == 'error'


@pytest.mark.parametrize('distance,message', [(0.6, 'short distance'), (8, 'fragmentation')])
def test_distance_warnings(xyz, distance, message):
    xyz.write_text(f'2\nSynthetic\nH 0 0 0\nH 0 0 {distance}\n')
    result = validate_xyz(xyz, 'angstrom')
    assert result['status'] == 'ok'
    assert message in ' '.join(result['warnings'])


@pytest.fixture
def state(xyz):
    return dict(molecule_id='synthetic', state_id='neutral_test', input_file=str(xyz),
                coordinate_units='angstrom', charge=0, multiplicity=1,
                protonation_state_id='neutral', conformer_id='fixture',
                identity=dict(molecule_id='synthetic', chemical_name='Synthetic H2 fixture',
                              source='Unit-test fixture; no scientific provenance claim',
                              isomer_identifier='not_applicable: diatomic fixture',
                              connectivity_reference='fixture specification H-H',
                              protonation_description='Neutral synthetic fixture',
                              protonation_site='not_applicable'))


@pytest.mark.parametrize('key,value,message', [
    ('charge', None, 'charge'), ('charge', 0.0, 'charge'),
    ('charge', True, 'charge'), ('charge', '0', 'charge'),
    ('charge', 2, 'positive'), ('charge', 1, 'parity'),
    ('multiplicity', None, 'multiplicity'), ('multiplicity', 0, 'multiplicity'),
    ('multiplicity', -1, 'multiplicity'), ('multiplicity', True, 'multiplicity'),
    ('multiplicity', 1.0, 'multiplicity'), ('multiplicity', 2, 'parity'),
    ('multiplicity', 3, 'singlets'), ('multiplicity', 5, 'unpaired'),
    ('protonation_state_id', None, 'protonation_state_id'),
    ('conformer_id', '', 'conformer_id'), ('state_id', None, 'state_id'),
])
def test_state_errors(state, key, value, message):
    state[key] = value
    result = qm.validate_state(state, [1, 1])
    assert result['status'] == 'error'
    assert message in ' '.join(result['errors'])


def test_charge_and_spin_valid_and_blocked(state):
    assert qm.validate_state(state, [1, 1])['electron_count'] == 2
    assert qm.validate_state(state, None)['status'] == 'blocked'


@pytest.mark.parametrize('key', ['source', 'chemical_name', 'molecule_id', 'isomer_identifier',
                                     'connectivity_reference', 'protonation_description', 'protonation_site'])
def test_identity_required(state, key):
    del state['identity'][key]
    assert qm.validate_identity(state['identity'], 'synthetic', 'neutral')['status'] == 'error'


def test_identity_missing_and_protonation_site(state):
    assert qm.validate_identity(None, 'synthetic', 'neutral')['status'] == 'error'
    assert qm.validate_identity(state['identity'], 'synthetic', 'protonated')['status'] == 'error'
    state['identity']['molecule_id'] = 'different'
    assert qm.validate_identity(state['identity'], 'synthetic', 'neutral')['status'] == 'error'


@pytest.fixture
def configuration(tmp_path, state):
    config = dict(schema_version=1, method='GFN2-xTB',
                  solvent=dict(model='none', solvent=None, reference_state=None),
                  settings=dict(optimization_level='tight', accuracy=0.2,
                                electronic_temperature_kelvin=300, max_scc_iterations=250,
                                max_optimization_cycles=250, timeout_seconds=10, threads=1),
                  states=[state])
    config_path, paper_path = tmp_path / 'qm.yaml', tmp_path / 'paper.yaml'
    paper_path.write_text(yaml.safe_dump(dict(molecules=['synthetic'])))
    return config, config_path, paper_path


def check(configuration):
    config, config_path, paper_path = configuration
    config_path.write_text(yaml.safe_dump(config))
    return qm.preflight(config_path, paper_path, config_path.parent)


def test_complete_preflight(configuration, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Preflight must not invoke engines')
    monkeypatch.setattr(cli.subprocess, 'run', forbidden)
    report = check(configuration)
    assert report['status'] == 'ok'
    assert report['configuration_status'] == 'ok'
    assert report['states'][0]['geometry']['status'] == 'ok'
    assert report['states'][0]['identity']['status'] == 'ok'
    assert report['states'][0]['charge_spin']['status'] == 'ok'
    assert 'energy' not in report


@pytest.mark.parametrize('change', ['no_states', 'unknown', 'duplicate', 'no_identity', 'no_file', 'missing_molecule', 'bad_entry'])
def test_failed_preflight(configuration, change):
    config = configuration[0]
    if change == 'no_states':
        config['states'] = []
    elif change == 'unknown':
        config['states'][0]['molecule_id'] = 'unlisted'
    elif change == 'duplicate':
        config['states'].append(copy.deepcopy(config['states'][0]))
    elif change == 'no_identity':
        del config['states'][0]['identity']
    elif change == 'no_file':
        config['states'][0]['input_file'] = 'absent.xyz'
    elif change == 'missing_molecule':
        configuration[2].write_text(yaml.safe_dump(dict(molecules=['synthetic', 'missing'])))
    else:
        config['states'] = [None]
    assert check(configuration)['status'] == 'error'


@pytest.mark.parametrize('field,value', [('accuracy', float('nan')), ('threads', True),
                                        ('timeout_seconds', 0), ('optimization_level', None)])
def test_protocol_errors(configuration, field, value):
    configuration[0]['settings'][field] = value
    assert check(configuration)['configuration_status'] == 'error'


def test_solvent_and_method(configuration):
    config = configuration[0]
    config['solvent'] = dict(model='ALPB', solvent='water', reference_state='gsolv')
    assert check(configuration)['status'] == 'ok'
    config['solvent']['reference_state'] = None
    assert check(configuration)['status'] == 'error'
    config['method'] = 'B3LYP'
    assert 'GFN2-xTB' in ' '.join(check(configuration)['errors'])


@pytest.mark.parametrize('content', ['[', '[]', 'null', 'states: []'])
def test_malformed_config(configuration, content):
    _, path, paper = configuration
    path.write_text(content)
    assert qm.preflight(path, paper)['status'] == 'error'


def test_report_atomic_and_finite(tmp_path, monkeypatch):
    path = tmp_path / 'report.json'
    qm.write_report({'status': 'error', 'value': None}, path)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        qm.write_report({'bad': float('nan')}, path)
    assert path.read_bytes() == before
    def fail(*args):
        raise OSError('synthetic replacement failure')
    monkeypatch.setattr(qm.os, 'replace', fail)
    with pytest.raises(OSError):
        qm.write_report({'status': 'ok'}, path)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    assert json.loads(before)['value'] is None


@pytest.mark.parametrize('success', [True, False])
def test_cli_exit_and_report(configuration, monkeypatch, success, capsys):
    report = check(configuration)
    if not success:
        report['status'] = 'error'
        report['errors'].append('Synthetic failure')
    monkeypatch.setattr(qm, 'preflight', lambda: report)
    monkeypatch.setattr(qm, 'ROOT', configuration[1].parent)
    monkeypatch.setattr('sys.argv', ['cli', 'qm', '--preflight'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == (0 if success else 1)
    saved = json.loads((qm.ROOT / 'results/qm/preflight.json').read_text())
    assert saved['status'] == report['status']
    assert 'QM preflight:' in capsys.readouterr().out


def test_cli_scaffold_unchanged(monkeypatch):
    monkeypatch.setattr('sys.argv', ['cli', 'qm'])
    with pytest.raises(SystemExit, match='scaffolded'):
        cli.main()


def test_template_is_not_executable():
    report = qm.preflight()
    assert report['status'] == 'error'
    assert len(report['states']) == 6
    assert all(s['geometry']['input_status'] == 'missing' for s in report['states'])
    assert all(s['charge_spin']['status'] == 'error' for s in report['states'])


def test_atom_order_different_elements(xyz):
    xyz.write_text('3\nSynthetic ordering fixture\nHe 0 0 0\nH 0 0 2\nH 0 0 3\n')
    result = validate_xyz(xyz, 'angstrom')
    assert result['status'] == 'ok'
    assert result['symbols'] == ['He', 'H', 'H']
    assert result['atomic_numbers'] == [2, 1, 1]


def test_duplicate_and_unknown_molecules(configuration):
    config, _, _ = configuration
    config['states'].append(copy.deepcopy(config['states'][0]))
    assert any('Duplicate' in e for e in check(configuration)['states'][1]['errors'])
    config['states'][0]['molecule_id'] = 'unknown'
    assert any('paper.yaml' in e for e in check(configuration)['states'][0]['errors'])


@pytest.mark.parametrize('states', [[], None, 'invalid', [None]])
def test_bad_state_collection(configuration, states):
    configuration[0]['states'] = states
    assert check(configuration)['status'] == 'error'


def test_missing_configuration(tmp_path):
    report = qm.preflight(tmp_path / 'absent.yaml')
    assert report['status'] == 'error'
    assert 'Cannot load' in report['errors'][0]


def test_cli_never_calls_engine(configuration, monkeypatch):
    report = check(configuration)
    monkeypatch.setattr(qm, 'preflight', lambda: report)
    monkeypatch.setattr(qm, 'ROOT', configuration[1].parent)
    def forbidden(*args, **kwargs):
        pytest.fail('Preflight must never start engines')
    monkeypatch.setattr(cli.subprocess, 'run', forbidden)
    monkeypatch.setattr('sys.argv', ['cli', 'qm', '--preflight'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    written = json.loads((qm.ROOT / 'results/qm/preflight.json').read_text())
    assert written['states'][0]['charge'] == 0
    assert written['states'][0]['multiplicity'] == 1


def test_write_failure_returns_nonzero(configuration, monkeypatch, capsys):
    report = check(configuration)
    monkeypatch.setattr(qm, 'preflight', lambda: report)
    def fail(*args):
        raise OSError('synthetic write failure')
    monkeypatch.setattr(qm, 'write_report', fail)
    assert qm.run_preflight() == 1
    assert 'Cannot write' in capsys.readouterr().out
