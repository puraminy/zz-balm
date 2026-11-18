"""Tiny engine checks, not scientific validation of the paper's methods."""
import os
import shutil
import subprocess

import pytest

from src.cli import probe_tool


def require_engine(name):
    if shutil.which(name) is None:
        if os.environ.get('ZZ_BALM_REQUIRE_ENGINES') == '1':
            pytest.fail(f'Required engine is missing: {name}')
        pytest.skip(f'{name} is not installed')
    report = probe_tool(name)
    assert report['status'] == 'ok', report


def test_xtb_single_point(tmp_path):
    require_engine('xtb')
    xyz = tmp_path / 'water.xyz'
    xyz.write_text('3\nWater smoke test\nO 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043\n')
    result = subprocess.run(
        ['xtb', str(xyz), '--gfn', '2', '--sp'], cwd=tmp_path,
        env={**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'},
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'TOTAL ENERGY' in result.stdout


def test_lammps_zero_step(tmp_path):
    require_engine('lmp')
    script = tmp_path / 'smoke.in'
    script.write_text('''units lj
atom_style atomic
lattice fcc 0.8442
region box block 0 2 0 2 0 2
create_box 1 box
create_atoms 1 box
mass 1 1.0
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5
run 0
''')
    result = subprocess.run(
        ['lmp', '-in', str(script), '-log', 'none'], cwd=tmp_path,
        env={**os.environ, 'OMP_NUM_THREADS': '1'},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Loop time' in result.stdout
