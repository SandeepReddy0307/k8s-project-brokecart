#!/usr/bin/env python3
"""Never promote an old image over newer source changes to the same service."""
import argparse
import json
from pathlib import Path
import subprocess
from select_services import ALL, ROOT, select


def check_promotion(source, matrix, directory=ROOT):
    # A rewritten main is not an eligible promotion target.
    subprocess.run(['git', 'merge-base', '--is-ancestor', source, 'HEAD'], cwd=directory, check=True)
    paths = subprocess.check_output(['git', 'diff', '--name-only', '-z', source, 'HEAD'], cwd=directory).decode().split('\0')[:-1]
    newer = {item['name'] for item in select(paths)}
    selected = {item['name'] for item in matrix['include']}
    if not selected <= set(ALL):
        raise ValueError('unknown service in build matrix')
    if newer & selected:
        raise ValueError('Newer source changes exist for ' + ', '.join(sorted(newer & selected)) + '. Run a fresh build instead of promoting stale images.')
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--matrix', required=True)
    args = parser.parse_args()
    try:
        check_promotion(args.source, json.loads(args.matrix))
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print('PASS: selected image builds still match current source')


if __name__ == '__main__':
    main()
