"""Strict single-frame XYZ validation; no geometry repair or identity assignment."""
from __future__ import annotations

import math
from pathlib import Path

# Atomic-number order. Valid symbols are case sensitive; isotope aliases are excluded.
ELEMENTS = ('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe '
            'Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn '
            'Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W '
            'Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf '
            'Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og').split()
ATOMIC_NUMBERS = {symbol: i for i, symbol in enumerate(ELEMENTS, 1)}


def validate_xyz(path: Path | str, units: str | None) -> dict:
    """Units must be explicitly declared externally as ``angstrom``.

    Distances <0.4 Å are fatal, <0.7 Å warn. These conservative screening
    heuristics are not bond perception or chemical validation.
    """
    path = Path(path)
    report = dict(status='error', input_status='missing', errors=[], warnings=[],
                  symbols=[], coordinates=[], atomic_numbers=[],
                  units=units if isinstance(units, str) else None)
    errors = report['errors']
    if units != 'angstrom':
        errors.append('Coordinate units must be explicitly declared as angstrom.')
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
        report['input_status'] = 'readable'
    except (OSError, UnicodeError) as exc:
        report['input_status'] = 'missing' if isinstance(exc, FileNotFoundError) else 'unreadable'
        errors.append(f'Cannot read XYZ input: {exc}')
        return report
    try:
        count = int(lines[0].strip())
        if count <= 0:
            raise ValueError
    except (IndexError, ValueError):
        errors.append('XYZ must start with a positive integer atom count.')
        return report
    if len(lines) < 2:
        errors.append('XYZ requires a comment line, which may be empty.')
        return report
    body = lines[2:]
    # Ignore trailing whitespace only; embedded blank records remain invalid.
    while body and not body[-1].strip():
        body.pop()
    if len(body) != count:
        errors.append('Declared atom count differs from records; only single-frame XYZ is accepted.')
        return report
    for index, line in enumerate(body, 1):
        fields = line.split()
        if len(fields) != 4:
            errors.append(f'Atom {index}: expected element and exactly three coordinates.')
            continue
        symbol = fields[0]
        if symbol not in ATOMIC_NUMBERS:
            errors.append(f'Atom {index}: unsupported element symbol {symbol!r}.')
            continue
        try:
            xyz = [float(value) for value in fields[1:]]
            if not all(math.isfinite(value) for value in xyz):
                raise ValueError
        except ValueError:
            errors.append(f'Atom {index}: coordinates must be finite numerical values.')
            continue
        report['symbols'].append(symbol)
        report['coordinates'].append(xyz)
        report['atomic_numbers'].append(ATOMIC_NUMBERS[symbol])
    if len(report['symbols']) != count:
        return report
    for i, first in enumerate(report['coordinates']):
        for j in range(i):
            distance = math.dist(first, report['coordinates'][j])
            if distance < 1e-8:
                errors.append(f'Atoms {j + 1}/{i + 1}: coincident atoms.')
            elif distance < 0.4:
                errors.append(f'Atoms {j + 1}/{i + 1}: implausible distance {distance:.6g} angstrom (<0.4).')
            elif distance < 0.7:
                report['warnings'].append(f'Atoms {j + 1}/{i + 1}: short distance {distance:.6g} angstrom; review required.')
    if count > 1:
        for i, first in enumerate(report['coordinates']):
            if all(math.dist(first, other) > 3.0 for j, other in enumerate(report['coordinates']) if i != j):
                report['warnings'].append(f'Atom {i + 1}: no neighbour within 3 angstrom; review fragmentation.')
    report['warnings'].append('XYZ validation does not establish connectivity, stereochemistry, or chemical identity.')
    report['status'] = 'error' if errors else 'ok'
    return report
