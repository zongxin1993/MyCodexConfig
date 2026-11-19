#!/usr/bin/env python3
"""Run real Cargo gates; retain original private logs and source-bound receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

COMMANDS = [
    ['cargo', 'fmt', '--all', '--', '--check'],
    ['cargo', 'build', '--workspace', '--all-targets', '--locked', '--offline'],
    ['cargo', 'clippy', '--workspace', '--all-targets', '--locked', '--offline', '--', '-D', 'warnings'],
    ['cargo', 'test', '--workspace', '--locked', '--offline'],
    ['cargo', 'test', '--workspace', '--doc', '--locked', '--offline'],
    ['cargo', 'test', '--workspace', '--release', '--locked', '--offline'],
]


def source_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()
            and not any(part in ('.git', 'target') for part in p.relative_to(root).parts)}


def check(root, evidence):
    root = root.resolve(strict=True); evidence = evidence.resolve()
    if evidence == root or root in evidence.parents:
        raise ValueError('Evidence must be outside the source tree')
    evidence.mkdir(parents=True, mode=0o700, exist_ok=False)
    before = source_hashes(root)
    env = os.environ.copy()
    env['CARGO_TARGET_DIR'] = str(evidence / 'target')
    versions = {}
    for args in (['rustc', '-Vv'], ['cargo', '-V'], ['cargo', 'clippy', '-V']):
        r = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=60, env=env)
        if r.returncode: raise RuntimeError('Missing toolchain: ' + ' '.join(args))
        versions[' '.join(args)] = r.stdout.strip()
    checks = []
    for index, args in enumerate(COMMANDS):
        r = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=180, env=env)
        log = evidence / f'{index:02d}-{args[1]}.log'
        log.write_text(r.stdout + r.stderr); log.chmod(0o600)
        checks.append({'command': args, 'cwd': str(root), 'exit_code': r.returncode, 'log': log.name})
    after = source_hashes(root)
    passed = before == after and all(c['exit_code'] == 0 for c in checks)
    receipt = {'status': 'PASS' if passed else 'BLOCKED', 'toolchain': versions,
               'source_hashes': after, 'source_unchanged': before == after, 'checks': checks}
    p = evidence / 'checks.json'; p.write_text(json.dumps(receipt, indent=2)); p.chmod(0o600)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path); p.add_argument('--evidence', required=True, type=Path)
    args = p.parse_args(); result = check(args.root, args.evidence)
    print(json.dumps(result, indent=2)); raise SystemExit(0 if result['status'] == 'PASS' else 1)
