#!/usr/bin/env python3
"""Render every backend release and verify dependency/identity isolation."""
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = 'catalog pricing identity cart checkout orders inventory payments payment-provider shipping returns notifications search reporting'.split()
EVENT_SERVICES = set('catalog inventory orders payments shipping returns notifications search reporting'.split())


def main():
    for service in SERVICES:
        values = yaml.safe_load((ROOT / f'infra/values/{service}.yaml').read_text())
        assert values['kafka']['enabled'] == (service in EVENT_SERVICES), service
        config = values['config']
        assert config['PORT'] == '8080'
        assert config['PUBLIC_ORIGIN'] == 'https://brokecart.com:8443'
        for peer in SERVICES:
            if peer != service:
                assert config[peer.upper().replace('-', '_') + '_URL'] == f'http://{peer}.brokecart-{peer}.svc.cluster.local'
        if service == 'pricing':
            assert config['CATALOG_BASE_URL'] == config['CATALOG_URL']
        output = subprocess.check_output([
            'helm', 'template', service, str(ROOT / 'infra/charts/application'),
            '-n', f'brokecart-{service}', '-f', str(ROOT / f'infra/values/{service}.yaml'),
        ], text=True)
        documents = [d for d in yaml.safe_load_all(output) if d]
        secrets = {d['spec']['target']['name']: d for d in documents if d['kind'] == 'ExternalSecret'}
        for suffix in ['database-credentials', 'application-security']:
            assert f'{service}-{suffix}' in secrets
        security = secrets[f'{service}-application-security']['spec']['data']
        assert any(k['secretKey'] == 'jwt-private-key' for k in security) == (service == 'identity')
        assert (f'{service}-kafka-credentials' in secrets) == (service in EVENT_SERVICES)
        assert ('cart-redis-credentials' in secrets) == (service == 'cart')
        assert ('search-elasticsearch-credentials' in secrets) == (service == 'search')
        deployment = next(d for d in documents if d['kind'] == 'Deployment')
        pod = deployment['spec']['template']['spec']
        assert pod['automountServiceAccountToken'] is False
        labels = deployment['spec']['template']['metadata']['labels']
        assert deployment['spec']['selector']['matchLabels'].items() <= labels.items()
        assert 'replicas' not in deployment['spec'], 'HPA must own replica count'
        resources_by_kind = {}
        for document in documents:
            resources_by_kind.setdefault(document['kind'], []).append(document)
            assert document['metadata'].get('namespace') == 'brokecart-' + service
        for kind in ['Service', 'PodDisruptionBudget']:
            selector = resources_by_kind[kind][0]['spec']['selector']
            if kind == 'PodDisruptionBudget':
                selector = selector['matchLabels']
            assert selector.items() <= labels.items(), (service, kind)
        hpa = resources_by_kind['HorizontalPodAutoscaler'][0]['spec']
        assert hpa['scaleTargetRef']['name'] == service
        assert hpa['minReplicas'] == 1 and hpa['maxReplicas'] == 2
        configmaps = {d['metadata']['name'] for d in resources_by_kind['ConfigMap']}
        volumes = {v['name']: v for v in pod['volumes']}
        for volume in volumes.values():
            if 'configMap' in volume:
                assert volume['configMap']['name'] in configmaps
        for container in pod.get('initContainers', []) + pod['containers']:
            for mount in container.get('volumeMounts', []):
                assert mount['name'] in volumes
        policy = resources_by_kind['NetworkPolicy'][0]['spec']
        assert policy['podSelector']['matchLabels'].items() <= labels.items()
        assert set(policy['policyTypes']) == {'Ingress', 'Egress'}
        allowed_ports = {port['port'] for rule in policy['egress'] for port in rule['ports']}
        assert {53, 5432, 8080, 4318} <= allowed_ports
        assert (9092 in allowed_ports) == (service in EVENT_SERVICES)
        assert (6379 in allowed_ports) == (service == 'cart')
        assert (9200 in allowed_ports) == (service == 'search')
        application = next(c for c in pod['containers'] if c['name'] == 'application')
        for env in application.get('env', []):
            reference = env.get('valueFrom', {}).get('secretKeyRef')
            if reference:
                assert reference['name'] in secrets, (service, reference)
        env = {item['name']: item for item in application.get('env', [])}
        assert ('JWT_PRIVATE_KEY' in env) == (service == 'identity')
        if service == 'cart':
            assert 'REDIS_URL' in env and env['REDIS_PASSWORD']['valueFrom']['secretKeyRef']['name'] == 'cart-redis-credentials'
        if service == 'search':
            assert 'ELASTICSEARCH_PASSWORD' in env
            assert 'javax.net.ssl.trustStore' in env['JAVA_TOOL_OPTIONS']['value']
            assert pod.get('initContainers'), 'Elasticsearch HTTPS requires the Java CA truststore'
        routes = [d for d in documents if d['kind'] == 'HTTPRoute']
        assert bool(routes) == (service != 'payment-provider')
        for route in routes:
            for rule in route['spec']['rules']:
                for match in rule['matches']:
                    assert match['path']['value'].startswith('/api/'), (service, match)
        print(f'PASS: {service} render, namespace peer URLs, credential references, JWT isolation and dependency settings')


if __name__ == '__main__':
    main()
