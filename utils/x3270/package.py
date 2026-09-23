#!/usr/bin/env python3
"""Build or verify only the x3270 community recipe ZIP (no binaries or signing)."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / 'APP_Source/Apps/x3270'
PACKAGE = ROOT / 'APP_Packages/Apps/x3270_community.zip'


def source_files():
    # Match the community packager's omission of hidden files; omit SDK scratch.
    return {
        p.relative_to(RECIPE).as_posix(): p
        for p in sorted(RECIPE.rglob('*'))
        if p.is_file() and not any(part.startswith('.') or part in
            {'igelpkg.output', 'igelpkg.tmp', 'tmp', '__pycache__'}
            for part in p.relative_to(RECIPE).parts)
        and p.name != 'igelpkg.log'
    }


def verify():
    files = source_files()
    with zipfile.ZipFile(PACKAGE) as archive:
        assert archive.testzip() is None, 'ZIP CRC error'
        assert set(archive.namelist()) == set(files), 'ZIP/source file list differs'
        for info in archive.infolist():
            assert archive.read(info.filename) == files[info.filename].read_bytes(), info.filename
            assert info.external_attr >> 16 & 0o777 == files[info.filename].stat().st_mode & 0o777, info.filename
            assert not info.flag_bits & 8 and info.extract_version < 45, 'ZIP64/data descriptor'
    print('Recipe ZIP matches all source files and permissions.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        with zipfile.ZipFile(PACKAGE, 'w', zipfile.ZIP_DEFLATED, allowZip64=False) as archive:
            for name, path in source_files().items():
                info = zipfile.ZipInfo(name, (2026, 9, 23, 0, 0, 0))
                info.create_system = 3
                info.external_attr = path.stat().st_mode << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    verify()


if __name__ == '__main__':
    main()
