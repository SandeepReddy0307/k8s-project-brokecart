#!/usr/bin/env python3
"""Select build targets from changed paths; infrastructure changes never build images."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKENDS = ('catalog', 'pricing', 'identity', 'cart', 'checkout', 'orders', 'inventory',
            'payments', 'payment-provider', 'shipping', 'returns', 'notifications', 'search', 'reporting')
ALL = (*BACKENDS, 'maintenance', 'frontend')


def target(name):
    path = 'frontend' if name == 'frontend' else ('services/maintenance-worker' if name == 'maintenance' else f'services/{name}-service')
    return {'name': name, 'path': path, 'dockerfile': f'{path}/Dockerfile',
            'context': 'frontend' if name == 'frontend' else '.', 'values': f'infra/values/{name}.yaml'}


def select(paths):
    selected = set()
    for path in paths:
        if path in ('pom.xml', 'mvnw', 'mvnw.cmd', '.dockerignore') or path.startswith(('libraries/', '.mvn/')):
            selected.update(ALL[:-1])
        if path.startswith(('.github/workflows/build-images.yaml', '.github/workflows/service-build.yaml', 'scripts/ci/')):
            selected.update(ALL)
        for name in ALL:
            if path.startswith(target(name)['path'] + '/'):
                selected.add(name)
    return [target(name) for name in ALL if name in selected]


def changes(base, head):
    return subprocess.check_output(['git', 'diff', '--name-only', '-z', base, head], cwd=ROOT).decode().split('\0')[:-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--services', default='')
    args = parser.parse_args()
    if args.services:
        names = list(ALL) if args.services == 'all' else [n.strip() for n in args.services.split(',')]
        if not names or any(n not in ALL for n in names):
            parser.error('services must be all or a comma-separated list of known service names')
        selected = [target(name) for name in ALL if name in names]
    elif args.base and set(args.base) != {'0'}:
        selected = select(changes(args.base, args.head))
    else:
        selected = [target(name) for name in ALL]
    print(json.dumps({'include': selected}, separators=(',', ':')))


if __name__ == '__main__':
    main()
