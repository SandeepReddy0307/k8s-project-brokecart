#!/usr/bin/env python3
"""Render every chart without contacting Kubernetes or requesting live Secrets."""
import argparse
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--dependencies', action='store_true', help='restore locked Helm dependencies')
args = parser.parse_args()

def run(*command):
    subprocess.run(command, cwd=ROOT, check=True)

for chart in sorted((ROOT / 'infra/charts').iterdir()):
    metadata = chart / 'Chart.yaml'
    if not metadata.exists():
        continue
    definition = yaml.safe_load(metadata.read_text())
    if args.dependencies and definition.get('dependencies'):
        for number, dependency in enumerate(definition['dependencies']):
            repository = dependency['repository']
            if not repository.startswith('https://'):
                raise ValueError('Only HTTPS chart repositories are allowed')
            run('helm', 'repo', 'add', f'brokecart-{chart.name}-{number}', repository)
        run('helm', 'dependency', 'build', str(chart), '--skip-refresh')
    if chart.name == 'application':
        values = [p for p in sorted((ROOT / 'infra/values').glob('*.yaml'))
                  if p.stem not in ('frontend', 'maintenance')]
    elif chart.name in ('frontend', 'maintenance'):
        values = [ROOT / f'infra/values/{chart.name}.yaml']
    else:
        values = [None]
    for values_file in values:
        name = values_file.stem if values_file else chart.name
        flags = ['-f', str(values_file)] if values_file else []
        run('helm', 'lint', str(chart), *flags)
        rendered = subprocess.check_output(['helm', 'template', name, str(chart), '-n', f'brokecart-{name}', *flags], cwd=ROOT, text=True)
        resources = [r for r in yaml.safe_load_all(rendered) if r]
        identities = [(r['apiVersion'], r['kind'], r['metadata'].get('namespace', ''), r['metadata']['name']) for r in resources]
        if len(identities) != len(set(identities)):
            raise ValueError(f'{name}: duplicate resource identities')
        print(f'PASS: {name}: {len(resources)} resources')
for application in sorted((ROOT / 'infra/argocd/applications').glob('*.yaml')):
    spec = yaml.safe_load(application.read_text())['spec']
    source = spec['source']
    assert (ROOT / source['path'] / 'Chart.yaml').is_file(), application
    for file in source.get('helm', {}).get('valueFiles', []):
        assert (ROOT / source['path'] / file).resolve().is_file(), (application, file)
print('PASS: all Helm charts and Argo CD source paths')
