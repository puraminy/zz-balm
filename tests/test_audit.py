import json
import subprocess

import pytest

from src import cli


@pytest.mark.parametrize(
    'tool,stdout,stderr,version,argv',
    [
        ('xtb', '-----------------\n* xtb version 6.7.1 (abc)\n', '', '6.7.1', ['xtb', '--version']),
        ('xtb', '', '* xtb version 6.6.1\n', '6.6.1', ['xtb', '--version']),
        ('lmp', '\nLarge-scale Atomic/Molecular Massively Parallel Simulator - 22 Jul 2025 - Update 1\n', '', '22 Jul 2025 - Update 1', ['lmp', '-help']),
    ],
)
def test_tool_versions(monkeypatch, tool, stdout, stderr, version, argv):
    def run(args, **kwargs):
        assert args == argv
        assert kwargs['timeout'] == 10
        assert kwargs['stdin'] == subprocess.DEVNULL
        return subprocess.CompletedProcess(args, 0, stdout, stderr)
    monkeypatch.setattr(cli.subprocess, 'run', run)
    report = cli.probe_tool(tool)
    assert report['status'] == 'ok'
    assert report['version'] == version
    assert report['returncode'] == 0


@pytest.mark.parametrize('returncode,stdout,stderr', [
    (1, '', "GLIBC_2.38 not found"),
    (1, '* xtb version 6.7.1', 'failed'),
    (0, '-----------------', ''),
])
def test_bad_probes_are_errors(monkeypatch, returncode, stdout, stderr):
    monkeypatch.setattr(cli.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, returncode, stdout, stderr))
    report = cli.probe_tool('xtb')
    assert report['status'] == 'error'
    assert report['version'] is None
    assert report['returncode'] == returncode
    assert report['stderr'] == stderr


@pytest.mark.parametrize('exc,status', [
    (FileNotFoundError('missing'), 'missing'),
    (subprocess.TimeoutExpired('xtb', 10), 'timeout'),
    (PermissionError('denied'), 'error'),
])
def test_probe_exceptions(monkeypatch, exc, status):
    def run(*args, **kwargs):
        raise exc
    monkeypatch.setattr(cli.subprocess, 'run', run)
    report = cli.probe_tool('xtb')
    assert report['status'] == status
    assert report['returncode'] is None
    assert report['error']


@pytest.mark.parametrize('status,exit_code', [('ok', 0), ('missing', 1)])
def test_audit_writes_reports_even_on_failure(monkeypatch, tmp_path, status, exit_code):
    monkeypatch.setattr(cli, 'RESULTS', tmp_path)
    monkeypatch.setattr(cli, 'probe_tool', lambda tool: {'status': status, 'version': None})
    assert cli.audit() == exit_code
    manifest = json.loads((tmp_path / 'software_manifest.json').read_text())
    assert manifest['status'] == ('ok' if status == 'ok' else 'error')
    assert manifest['schema_version'] == 2
    assert json.loads((tmp_path / 'config_snapshot.json').read_text()) == cli.load_config()
