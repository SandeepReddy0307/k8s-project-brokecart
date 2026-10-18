"""Exercise service selection and ensure image promotion cannot rewrite other values."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/ci'))
from select_services import ALL, select
from update_images import update
from check_promotion import check_promotion


def names(paths):
    return {s['name'] for s in select(paths)}

assert names(['services/catalog-service/src/main/java/Example.java']) == {'catalog'}
assert names(['services/orders-service/Dockerfile', 'services/payment-provider-service/pom.xml']) == {'orders', 'payment-provider'}
assert names(['frontend/src/main.tsx']) == {'frontend'}
assert names(['services/maintenance-worker/pom.xml']) == {'maintenance'}
assert names(['libraries/commerce-common/src/main/java/Shared.java']) == set(ALL) - {'frontend'}
assert names(['pom.xml']) == set(ALL) - {'frontend'}
assert names(['infra/values/catalog.yaml', 'infra/charts/kafka/values.yaml', 'docs/architecture.md']) == set()
assert names(['scripts/ci/select_services.py']) == set(ALL)
assert names(['services/catalog-service-extra/foo.java']) == set()

# Image builds compile only the target module, while sharing dependencies safely.
for dockerfile in (ROOT / 'services').glob('*/Dockerfile'):
    module = dockerfile.parent.relative_to(ROOT).as_posix()
    contents = dockerfile.read_text()
    expected = f'RUN --mount=type=cache,target=/root/.m2,sharing=locked mvn -B -pl {module} -am package -DskipTests'
    assert expected in contents, dockerfile
    assert 'mvn -B package -DskipTests' not in contents, dockerfile


with tempfile.TemporaryDirectory(prefix='brokecart-ci-') as tmp:
    file = Path(tmp) / 'values.yaml'
    file.write_text('# keep this comment\nimage:\n  repository: old/repo\n  tag: old\n  pullPolicy: IfNotPresent\n\nsecurity:\n  enabled: true\n')
    update(file, 'docker.io/example/brokecart-catalog', 'a' * 40)
    contents = file.read_text()
    assert contents.startswith('# keep this comment')
    parsed = yaml.safe_load(contents)
    assert parsed['security'] == {'enabled': True}
    assert parsed['image'] == {'repository': 'docker.io/example/brokecart-catalog', 'tag': 'a' * 40, 'pullPolicy': 'IfNotPresent'}
    file.write_text('image: {repository: old, tag: old}\n')
    try:
        update(file, 'repo', 'tag')
    except ValueError:
        pass
    else:
        raise AssertionError('flow-style values must fail instead of corrupting YAML')

# Simulate main advancing while a build is running. Only selected source matters.
with tempfile.TemporaryDirectory(prefix='brokecart-promotion-') as tmp:
    directory = Path(tmp)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=directory, stderr=subprocess.DEVNULL, text=True).strip()
    git('init', '-b', 'main')
    git('config', 'user.name', 'CI Test')
    git('config', 'user.email', 'ci@example.invalid')
    def commit_file(path, content):
        destination = directory / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        git('add', '--', path)
        git('commit', '-m', 'test fixture change')
    commit_file('services/catalog-service/source.txt', 'built version')
    source = git('rev-parse', 'HEAD')
    matrix = {'include': [{'name': 'catalog'}]}
    assert check_promotion(source, matrix, directory) == {'catalog'}
    commit_file('docs/notes.md', 'new documentation')
    assert check_promotion(source, matrix, directory) == {'catalog'}
    commit_file('services/orders-service/source.txt', 'unrelated service changed')
    assert check_promotion(source, matrix, directory) == {'catalog'}
    commit_file('infra/values/catalog.yaml', 'replicas: 2')
    assert check_promotion(source, matrix, directory) == {'catalog'}
    commit_file('services/catalog-service/source.txt', 'newer unbuilt version')
    try:
        check_promotion(source, matrix, directory)
    except ValueError as error:
        assert 'catalog' in str(error)
    else:
        raise AssertionError('stale catalog build must not be promoted')
    # A shared Java library change invalidates the selected backend too.
    source = git('rev-parse', 'HEAD')
    commit_file('libraries/commerce-common/source.txt', 'new common code')
    try:
        check_promotion(source, matrix, directory)
    except ValueError:
        pass
    else:
        raise AssertionError('stale common-library build must not be promoted')
    # Selecting an unknown target fails closed.
    try:
        check_promotion(source, {'include': [{'name': '../unexpected'}]}, directory)
    except ValueError:
        pass
    else:
        raise AssertionError('unknown promotion target must fail')
    git('checkout', '--detach', source + '^')
    try:
        check_promotion(source, matrix, directory)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('a build from outside current main history must fail')

workflows = {p.name: yaml.load(p.read_text(), Loader=yaml.BaseLoader) for p in (ROOT / '.github/workflows').glob('*.yaml')}
for workflow in workflows.values():
    assert 'pull_request_target' not in workflow['on']
    assert 'pull_request' not in workflow['on']
    for job in workflow['jobs'].values():
        if 'runs-on' in job:
            assert 'self-hosted' in job['runs-on'] and 'brokecart' in job['runs-on']
        for step in job.get('steps', []):
            action = step.get('uses', '')
            if action:
                assert action in {
                    'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                    'actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020',
                }
            if 'run' in step:
                subprocess.run(['bash', '-n'], input=step['run'], text=True, check=True)
assert workflows['build-images.yaml']['jobs']['promote']['permissions'] == {'contents': 'write'}
assert workflows['service-build.yaml']['jobs']['build']['environment'] == 'learning'
node_setup = next(s for s in workflows['service-build.yaml']['jobs']['build']['steps']
                  if s.get('uses', '').startswith('actions/setup-node@'))
assert node_setup['if'] == "inputs.service == 'frontend'"
assert node_setup['with']['node-version'] == '22'
assert node_setup['with']['cache-dependency-path'] == 'frontend/package-lock.json'
assert workflows['build-images.yaml']['jobs']['promote']['environment'] == 'learning'
all_steps = '\n'.join(s.get('run', '') for w in workflows.values() for j in w['jobs'].values() for s in j.get('steps', []))
assert 'helm upgrade' not in all_steps and 'kubectl apply' not in all_steps
assert 'docker login' in all_steps and '--password-stdin' in all_steps
assert 'docker push' in all_steps
print('PASS: selective CI targets, comment-preserving image updates, workflow permissions and shell syntax')
