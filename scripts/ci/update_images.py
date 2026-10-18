#!/usr/bin/env python3
"""Update only image fields while preserving hand-written values and comments."""
import argparse
import json
from pathlib import Path
import re
import yaml
from select_services import ALL, ROOT


def update(path, repository, tag):
    contents = path.read_text()
    parsed = yaml.safe_load(contents)
    if not isinstance(parsed, dict) or not isinstance(parsed.get('image'), dict):
        raise ValueError(f'{path}: expected top-level image mapping')
    # All application values intentionally have a top-level block-style image mapping.
    pattern = r'(?ms)^image:\s*\n(?P<body>(?:[ \t]+[^\n]*\n|\n)+)'
    match = re.search(pattern, contents)
    if not match:
        raise ValueError(f'{path}: image must use block YAML syntax')
    body = match.group('body')
    for key, value in [('repository', repository), ('tag', tag)]:
        body, count = re.subn(rf'(?m)^  {key}:.*$', f'  {key}: {json.dumps(value)}', body)
        if count != 1:
            raise ValueError(f'{path}: expected exactly one image.{key}')
    result = contents[:match.start('body')] + body + contents[match.end('body'):]
    check = yaml.safe_load(result)
    assert check['image']['repository'] == repository and check['image']['tag'] == tag
    path.write_text(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--matrix', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,38}', args.username):
        parser.error('invalid Docker Hub username')
    if not re.fullmatch(r'[a-f0-9]{40}', args.sha):
        parser.error('expected full Git commit SHA')
    selected = json.loads(args.matrix)['include']
    for service in selected:
        name = service['name']
        if name not in ALL or service['values'] != f'infra/values/{name}.yaml':
            parser.error('unexpected build target')
        update(ROOT / service['values'], f'docker.io/{args.username}/brokecart-{name}', args.sha)
        print(f'Updated {name} image to commit {args.sha[:12]}')


if __name__ == '__main__':
    main()
