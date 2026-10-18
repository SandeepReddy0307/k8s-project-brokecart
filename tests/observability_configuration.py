#!/usr/bin/env python3
"""Validate dashboard JSON and alert integration without a running cluster."""
from pathlib import Path
import json
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / 'infra/charts/observability-config'
output = subprocess.check_output(['helm', 'template', 'observability-config', str(CHART), '-n', 'observability'], text=True)
resources = [d for d in yaml.safe_load_all(output) if d]
cm = next(d for d in resources if d['kind'] == 'ConfigMap')
assert cm['metadata']['labels']['grafana_dashboard'] == '1'
assert cm['metadata']['namespace'] == 'observability'
dashboard = json.loads(cm['data']['brokecart-overview.json'])
assert dashboard['uid'] == 'brokecart-overview'
assert len({p['id'] for p in dashboard['panels']}) == len(dashboard['panels'])
variables = {v['name']: v for v in dashboard['templating']['list']}
for source in ['prometheus', 'loki', 'tempo']:
    assert variables[source]['type'] == 'datasource' and variables[source]['query'] == source
assert variables['namespace']['allValue'] == 'brokecart-.*'
logs = next(p for p in dashboard['panels'] if p['type'] == 'logs')
assert 'cluster="brokecart"' in logs['targets'][0]['expr']
assert 'namespace=~"$namespace"' in logs['targets'][0]['expr']
fluent = (ROOT / 'infra/platform/fluent-bit-values.yaml').read_text()
assert 'cluster=brokecart' in fluent and "namespace=$kubernetes['namespace_name']" in fluent
queries = '\n'.join(t.get('expr', '') for p in dashboard['panels'] for t in p.get('targets', []))
assert 'http_server_requests_seconds_sum' in queries and 'http_server_requests_seconds_count' in queries
assert '_bucket' not in queries, 'Histogram buckets are not enabled by the application'
assert 'outbox' not in queries and 'kafka_' not in queries, 'No custom outbox meters or Kafka exporter are configured'
for p in dashboard['panels']:
    if p.get('datasource'):
        assert p['datasource']['uid'] in ['${prometheus}', '${loki}', '${tempo}']
rule_resource = next(d for d in resources if d['kind'] == 'PrometheusRule')
assert rule_resource['metadata']['labels']['release'] == 'monitoring'
rules = {r['alert']: r for g in rule_resource['spec']['groups'] for r in g['rules']}
assert set(rules) == {'BrokeCartHTTP5xx', 'BrokeCartHTTPLatency', 'BrokeCartDeploymentUnavailable', 'BrokeCartPodRestarts'}
for name in ['BrokeCartHTTP5xx', 'BrokeCartHTTPLatency']:
    assert '> 0.1)' in rules[name]['expr'], 'HTTP alerts need a traffic floor'
    assert 'uri!~"/actuator.*"' in rules[name]['expr']
app = yaml.safe_load((ROOT / 'infra/argocd/applications/observability-config.yaml').read_text())
assert app['spec']['source']['path'] == 'infra/charts/observability-config'
assert app['spec']['destination']['namespace'] == 'observability'
print('PASS: dashboard JSON, datasource independence, real source labels, default metric families, and alert integration')
print('NOTE: Live metric delivery, Grafana query behavior and alert evaluation require the deployed stack.')
