#!/usr/bin/env python3
"""Backup-first Codex-only installer. No OpenCode or authentication writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
try:
    import tomllib
except ImportError:
    raise SystemExit("MyCodexConfig requires Python 3.11 or newer")

ROOT = Path(__file__).resolve().parent
START = '# BEGIN MyCodexConfig managed'
END = '# END MyCodexConfig managed'
MARKER = 'Managed-By: MyCodexConfig'
DISABLED = ('quality-planning', 'quality-review', 'local-execution', 'ast-grep', 'rust-diagnostics')


def sha(data): return hashlib.sha256(data).hexdigest()


def safe(path):
    for p in (path, *path.parents):
        if p.is_symlink(): raise ValueError('Refuse symlink destination: ' + str(p))


def atomic(path, data):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.mycodex-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), 0o600); out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def managed(text, body):
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError('Ambiguous managed block')
    if START in text:
        a, b = text.index(START), text.index(END) + len(END)
        if b < a: raise ValueError('Invalid managed block order')
        text = text[:a] + text[b:]
    return text.rstrip() + '\n\n' + START + '\n' + body.rstrip() + '\n' + END + '\n'


def payload(ast_grep=None):
    paths = [ROOT / 'tools.py']
    for directory in ('workflow', 'schemas', 'examples', 'resources', 'skills'):
        paths.extend(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and not any(part in ('__pycache__', 'target', '.private', '.git') for part in p.relative_to(ROOT).parts) and p.suffix != '.pyc')
    result = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(paths)}
    if ast_grep is not None:
        binary = Path(ast_grep).resolve(strict=True)
        if not binary.is_file() or not os.access(binary, os.X_OK): raise ValueError('ast-grep must be executable')
        result['bin/ast-grep'] = binary.read_bytes()
    return dict(sorted(result.items()))


def config_block(home, release, python, context7):
    quote = json.dumps
    lines = ['[mcp_servers.quality]', 'command = ' + quote(python),
             'args = ' + quote(['-m', 'workflow.server', '--settings', str(home / '.config/mycodexconfig/settings.json')]),
             'cwd = ' + quote(str(release)), 'startup_timeout_sec = 20', 'tool_timeout_sec = 60',
             'enabled_tools = ["quality_info", "quality_resource", "quality_onboard", "quality_prepare", "quality_gate"]']
    if context7:
        lines += ['', '[mcp_servers.context7]', 'url = "https://mcp.context7.com/mcp/oauth"',
                  'startup_timeout_sec = 30', 'tool_timeout_sec = 60',
                  'enabled_tools = ["resolve-library-id", "query-docs"]']
    for name in DISABLED:
        lines += ['', '[[skills.config]]', 'path = ' + quote(str(home / '.agents/skills' / name / 'SKILL.md')), 'enabled = false']
    return '\n'.join(lines)


def install(home, context7=True, ast_grep=None):
    home = Path(home).absolute(); safe(home)
    config = home / '.codex/config.toml'; guidance = home / '.codex/AGENTS.md'
    safe(config); safe(guidance)
    old_config = config.read_text() if config.exists() else ''
    # Refuse collisions outside the owned block, rather than editing foreign MCP definitions.
    foreign = old_config
    if START in foreign:
        managed(foreign, '')  # validate before splitting
        foreign = foreign[:foreign.index(START)] + foreign[foreign.index(END) + len(END):]
    parsed = tomllib.loads(foreign)
    for name in ('quality', 'context7') if context7 else ('quality',):
        if name in parsed.get('mcp_servers', {}):
            raise ValueError('Foreign MCP collision: ' + name)
    files = payload(ast_grep)
    identity = sha(b''.join(k.encode() + b'\0' + v for k, v in files.items()))[:20]
    files['release.json'] = (json.dumps({'files': {k: sha(v) for k, v in files.items()}}, sort_keys=True) + '\n').encode()
    release = home / '.local/share/mycodexconfig/releases' / identity
    safe(release)
    if release.exists():
        for relative, data in files.items():
            p = release / relative; safe(p)
            if not p.is_file() or p.read_bytes() != data: raise ValueError('Modified installed release')
    python = str(Path(sys.executable).resolve())
    desired = {config: managed(old_config, config_block(home, release, python, context7)).encode()}
    tomllib.loads(desired[config].decode())  # validate the full merged configuration before any write
    body = (ROOT / 'guidance.md').read_text().replace('@RUNTIME@', str(release)).replace('@SETTINGS@', str(home / '.config/mycodexconfig/settings.json'))
    desired[guidance] = managed(guidance.read_text() if guidance.exists() else '', body).encode()
    for name in sorted((ROOT / 'skills').iterdir()):
        if not name.is_dir(): continue
        destination = home / '.codex/skills' / name.name
        safe(destination)
        if destination.exists() and (not (destination / 'SKILL.md').is_file() or MARKER not in (destination / 'SKILL.md').read_text()):
            raise ValueError('Foreign skill collision: ' + name.name)
        for p in name.rglob('*'):
            if p.is_file(): desired[destination / p.relative_to(name)] = p.read_text().replace('@RUNTIME@', str(release)).encode()
    settings = home / '.config/mycodexconfig/settings.json'; safe(settings)
    if not settings.exists(): desired[settings] = b'{"projects": []}\n'
    changes = {p: v for p, v in desired.items() if not p.exists() or p.read_bytes() != v}
    if not changes:
        if release.exists(): return {'status': 'UNCHANGED', 'release': str(release)}
        deploy_release(release, files)
        return {'status': 'RUNTIME_RESTORED', 'release': str(release)}
    backup = home / '.codex/backups/mycodexconfig' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    safe(backup); backup.mkdir(parents=True, mode=0o700)
    manifest = {'version': 1, 'files': {}, 'release': str(release)}
    for p, data in changes.items():
        relative = str(p.relative_to(home)); old = p.read_bytes() if p.exists() else None
        entry = {'before': sha(old) if old is not None else None, 'after': sha(data)}
        if old is not None: atomic(backup / 'files' / relative, old)
        manifest['files'][relative] = entry
    atomic(backup / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    if not release.exists(): deploy_release(release, files)
    applied = []
    try:
        for p, data in changes.items(): atomic(p, data); applied.append(p)
    except Exception:
        for p in reversed(applied):
            relative = str(p.relative_to(home)); entry = manifest['files'][relative]
            if entry['before'] is None: p.unlink()
            else: atomic(p, (backup / 'files' / relative).read_bytes())
        raise
    return {'status': 'INSTALLED', 'release': str(release), 'backup': str(backup), 'changed_files': len(changes)}


def deploy_release(release, files):
    staging = release.parent / ('.stage-' + uuid.uuid4().hex)
    for relative, data in files.items(): atomic(staging / relative, data)
    if 'bin/ast-grep' in files: (staging / 'bin/ast-grep').chmod(0o755)
    os.replace(staging, release)


def rollback(home, backup):
    home = Path(home).absolute(); backup = Path(backup).absolute(); safe(home); safe(backup)
    expected_root = home / '.codex/backups/mycodexconfig'
    if backup.parent != expected_root: raise ValueError('Backup must belong to this Codex home')
    manifest = json.loads((backup / 'manifest.json').read_text())
    for relative, entry in manifest['files'].items():
        p = home / relative; safe(p)
        if Path(relative).is_absolute() or '..' in Path(relative).parts: raise ValueError('Unsafe backup path')
        if not p.is_file() or sha(p.read_bytes()) != entry['after']: raise ValueError('Concurrent change; refusing rollback: ' + relative)
        if entry['before'] is not None:
            old = backup / 'files' / relative; safe(old)
            if sha(old.read_bytes()) != entry['before']: raise ValueError('Backup integrity failure')
    for relative, entry in manifest['files'].items():
        p = home / relative
        if entry['before'] is None: p.unlink()
        else: atomic(p, (backup / 'files' / relative).read_bytes())
    return {'status': 'ROLLED_BACK', 'files': len(manifest['files'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--without-context7', action='store_true')
    parser.add_argument('--rollback', type=Path)
    parser.add_argument('--ast-grep', type=Path, help='Copy a verified existing ast-grep executable into the independent runtime')
    args = parser.parse_args()
    try:
        result = rollback(args.home, args.rollback) if args.rollback else install(args.home, not args.without_context7, args.ast_grep)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__': raise SystemExit(main())
