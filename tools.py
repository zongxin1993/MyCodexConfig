#!/usr/bin/env python3
"""Bounded native-shell helpers: no MCP permission bypass or generic command runner."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def source(root, name):
    root = Path(root).resolve(strict=True)
    path = Path(name)
    if path.is_absolute() or '..' in path.parts: raise ValueError('Use worktree-relative paths')
    candidate = root / path
    for p in (candidate, *candidate.parents):
        if p == root: break
        if p.is_symlink(): raise ValueError('Symlink source refused')
    actual = candidate.resolve(strict=True)
    if actual != root and root not in actual.parents: raise ValueError('Source escaped root')
    if any(p in ('.git', '.env', '.ssh', '.aws', 'node_modules', 'target') or p.startswith('.env.') for p in path.parts):
        raise ValueError('Private/generated path refused')
    return actual


def tool(name):
    value = shutil.which(name)
    if value: return value
    raise ValueError(name + ' is not available on PATH; do not install in the task repository')


def run(args, cwd):
    result = subprocess.run(args, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    output = result.stdout[:24000].decode('utf-8', errors='replace')
    return {'exit_code': result.returncode, 'output': output, 'limited': len(result.stdout) > 24000,
            'stderr': result.stderr[:2000].decode('utf-8', errors='replace')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    a = sub.add_parser('ast'); a.add_argument('--root', required=True); a.add_argument('--language', required=True)
    a.add_argument('--pattern', required=True); a.add_argument('--bin', default=str(Path(__file__).resolve().parent / 'bin/ast-grep') if (Path(__file__).resolve().parent / 'bin/ast-grep').is_file() else 'ast-grep'); a.add_argument('files', nargs='+')
    a = sub.add_parser('worktree'); a.add_argument('--root', required=True)
    args = p.parse_args()
    try:
        root = Path(args.root).resolve(strict=True)
        if args.action == 'ast':
            if not 1 <= len(args.files) <= 64: raise ValueError('Select 1..64 explicit files')
            files = [source(root, name) for name in args.files]
            if not all(f.is_file() for f in files): raise ValueError('Explicit files only')
            binary = str(Path(args.bin).resolve(strict=True)) if Path(args.bin).is_absolute() else tool(args.bin)
            value = run([binary, 'run', '--lang', args.language, '--pattern', args.pattern, '--json=compact', '--', *map(str, files)], root)
            if value['exit_code'] not in (0, 1): raise ValueError(value['stderr'])
        else:
            output = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--path-format=absolute', '--git-dir', '--git-common-dir', '--show-toplevel'], text=True).splitlines()
            parent = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-superproject-working-tree'], text=True).strip()
            git_dir, common, checkout = map(Path, output)
            linked = not parent and git_dir != common and common / 'worktrees' in git_dir.parents
            value = {'root': str(checkout), 'isolated': linked,
                     'branch': subprocess.check_output(['git', '-C', str(root), 'branch', '--show-current'], text=True).strip()}
        print(json.dumps(value, ensure_ascii=False)); return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)})); return 2


if __name__ == '__main__': raise SystemExit(main())
